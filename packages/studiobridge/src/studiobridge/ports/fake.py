"""In-memory loopback MIDI port implementation for testing and development."""

from __future__ import annotations

import contextlib
import queue
import random
import threading
import time
from collections.abc import Callable

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPortInfo, PortStats


class FakeMidiPort:
    """In-memory thread-safe loopback MIDI port.

    Simulates latency, dropped packets, and duplex send/receive across worker
    threads for testing without requiring real MIDI drivers or hardware.
    """

    _registered_ports: list[tuple[str, str]] = [
        ("Fake Loopback (A)", "Fake Loopback (A)"),
        ("Fake Loopback (B)", "Fake Loopback (B)"),
        ("StudioBridge Loopback (A)", "StudioBridge Loopback (A)"),
        ("StudioBridge Loopback (B)", "StudioBridge Loopback (B)"),
    ]

    def __init__(
        self,
        *,
        in_name: str | None = None,
        out_name: str | None = None,
        latency_ms: float = 0.0,
        drop_rate: float = 0.0,
    ) -> None:
        self._in_name: str | None = in_name
        self._out_name: str | None = out_name
        self.latency_ms: float = latency_ms
        self.drop_rate: float = drop_rate

        self._stats = PortStats()
        self._is_open = False
        self._peer: FakeMidiPort | None = None

        self._sysex_callbacks: list[Callable[[bytes], None]] = []
        self._error_callbacks: list[Callable[[PortError], None]] = []

        self._recv_queue: queue.Queue[tuple[bytes, float] | None] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._lock = threading.RLock()

        self.fail_next_send_error: PortError | None = None

    @classmethod
    def register_port(cls, in_name: str, out_name: str) -> None:
        """Register a virtual port name for list_ports enumeration."""
        pair = (in_name, out_name)
        if pair not in cls._registered_ports:
            cls._registered_ports.append(pair)

    @classmethod
    def create_pair(
        cls,
        name_a: str = "Fake Loopback (A)",
        name_b: str = "Fake Loopback (B)",
        *,
        latency_ms: float = 0.0,
        drop_rate: float = 0.0,
    ) -> tuple[FakeMidiPort, FakeMidiPort]:
        """Create a cross-wired duplex pair of FakeMidiPort instances.

        Messages sent from port A are delivered to port B's incoming callbacks,
        and vice-versa.
        """
        port_a = cls(in_name=name_a, out_name=name_a, latency_ms=latency_ms, drop_rate=drop_rate)
        port_b = cls(in_name=name_b, out_name=name_b, latency_ms=latency_ms, drop_rate=drop_rate)

        port_a.connect_peer(port_b)
        port_b.connect_peer(port_a)

        port_a._is_open = True
        port_b._is_open = True

        port_a._start_worker()
        port_b._start_worker()

        return port_a, port_b

    def connect_peer(self, peer: FakeMidiPort) -> None:
        """Cross-wire this port to another FakeMidiPort instance."""
        with self._lock:
            self._peer = peer

    def list_ports(self) -> list[MidiPortInfo]:
        """Enumerate available virtual fake MIDI endpoints."""
        ports: list[MidiPortInfo] = []
        with self._lock:
            registered = list(self._registered_ports)
            if self._in_name and (self._in_name, self._in_name) not in registered:
                registered.append((self._in_name, self._in_name))

        for idx, (in_name, out_name) in enumerate(registered):
            ports.append(
                MidiPortInfo(
                    direction="in",
                    index=idx,
                    name=in_name,
                    api="fake",
                    manufacturer="StudioBridge Virtual",
                    driver_version="1.0.0",
                )
            )
            ports.append(
                MidiPortInfo(
                    direction="out",
                    index=idx,
                    name=out_name,
                    api="fake",
                    manufacturer="StudioBridge Virtual",
                    driver_version="1.0.0",
                )
            )
        return ports

    def open(
        self,
        in_name: str,
        out_name: str,
        *,
        sysex_buf: int = 16384,
        nbufs: int = 8,
    ) -> None:
        """Open the fake MIDI endpoints and start the receiver worker thread."""
        with self._lock:
            if self._is_open:
                self.close()

            self._in_name = in_name
            self._out_name = out_name
            self._is_open = True
            self._start_worker()

    def _start_worker(self) -> None:
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name=f"FakeMidiPortWorker-{self._in_name or 'loopback'}",
                daemon=True,
            )
            self._worker_thread.start()

    def _worker_loop(self) -> None:
        while True:
            try:
                item = self._recv_queue.get()
            except Exception:
                break

            if item is None:
                self._recv_queue.task_done()
                break

            data, delay_ms = item
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            with self._lock:
                if not self._is_open:
                    self._recv_queue.task_done()
                    break

                self._stats.bytes_recv += len(data)
                self._stats.frames_recv += 1
                callbacks = list(self._sysex_callbacks)

            for cb in callbacks:
                try:
                    cb(data)
                except Exception as exc:
                    self._notify_error(
                        PortError(
                            f"Unhandled error in SysEx callback: {exc}",
                            code="E_FL",
                            details={"error": str(exc)},
                            remedy="Fix exception inside SysEx callback handler.",
                        )
                    )

            self._recv_queue.task_done()

    def _enqueue_incoming(self, data: bytes, delay_ms: float = 0.0) -> None:
        with self._lock:
            if not self._is_open:
                return
        self._recv_queue.put((data, delay_ms))

    def _should_drop(self) -> bool:
        if self.drop_rate <= 0.0:
            return False
        if self.drop_rate >= 1.0:
            return True
        return random.random() < self.drop_rate

    def send_sysex(self, data: bytes) -> None:
        """Send SysEx bytes to peer port or self (in standalone loopback mode)."""
        with self._lock:
            if not self._is_open:
                raise PortError(
                    "Cannot send SysEx: MIDI port is closed.",
                    code="E_ENV_PORT",
                    remedy="Open the MIDI port before attempting transmission.",
                )

            if self.fail_next_send_error is not None:
                err = self.fail_next_send_error
                self.fail_next_send_error = None
                raise err

            if not (data.startswith(b"\xf0") and data.endswith(b"\xf7")):
                raise PortError(
                    "Invalid SysEx frame: message must begin with 0xF0 and end with 0xF7.",
                    code="E_PROTO",
                    details={"length": len(data)},
                    remedy="Ensure packet framing adheres to MIDI SysEx standard.",
                )

            self._stats.bytes_sent += len(data)
            self._stats.frames_sent += 1

            if self._should_drop():
                self._stats.dropped += 1
                return

            delay = self.latency_ms
            target = self._peer if self._peer is not None else self

        target._enqueue_incoming(data, delay_ms=delay)

    def on_sysex(self, cb: Callable[[bytes], None]) -> None:
        """Register a callback for received SysEx messages."""
        with self._lock:
            if cb not in self._sysex_callbacks:
                self._sysex_callbacks.append(cb)

    def on_error(self, cb: Callable[[PortError], None]) -> None:
        """Register a callback for port errors and disconnection events."""
        with self._lock:
            if cb not in self._error_callbacks:
                self._error_callbacks.append(cb)

    def _notify_error(self, error: PortError) -> None:
        with self._lock:
            callbacks = list(self._error_callbacks)
        for cb in callbacks:
            with contextlib.suppress(Exception):
                cb(error)

    def simulate_error(self, error: PortError) -> None:
        """Manually trigger an asynchronous error event for registered listeners."""
        self._notify_error(error)

    def simulate_disconnect(self) -> None:
        """Simulate unexpected port disconnection by peer or driver."""
        self.close()
        self._notify_error(
            PortError(
                "MIDI endpoint disconnected unexpectedly.",
                code="E_DISCONNECTED",
                retryable=True,
                remedy="Re-enumerate ports and restart session connection.",
            )
        )

    def close(self) -> None:
        """Close endpoints, drain queues, and terminate the worker thread."""
        with self._lock:
            if not self._is_open and self._worker_thread is None:
                return
            self._is_open = False

        self._recv_queue.put(None)
        if self._worker_thread is not None and self._worker_thread.is_alive():
            if threading.current_thread() != self._worker_thread:
                self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

    @property
    def is_open(self) -> bool:
        """Return True if port is currently open."""
        with self._lock:
            return self._is_open

    @property
    def stats(self) -> PortStats:
        """Return port runtime telemetry statistics."""
        return self._stats

    @property
    def in_name(self) -> str | None:
        """Return the active input port name."""
        with self._lock:
            return self._in_name

    @property
    def out_name(self) -> str | None:
        """Return the active output port name."""
        with self._lock:
            return self._out_name
