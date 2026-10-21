"""Session lifecycle, connection management, handshake, and fingerprint tracking.

Implements Session and Status per spec 09_l1_sdk.md §2 and [SDK-02]:
- Connection management supporting both daemon mode (TCP via ensure_broker()) and embedded mode
  (EmbeddedBroker with real, fake, or direct handler).
- Session fingerprint (fp) pinning and handshake negotiation.
- Actionable ConnectionError subtypes (NoBrokerError, NoDeviceError, VersionMismatchError,
  DisconnectedError).
- Strongly typed Status dataclass.
"""

from __future__ import annotations

import contextlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from studiobridge._version import __version__
from studiobridge.broker.client import BrokerClient, ensure_broker
from studiobridge.broker.embedded import EmbeddedBroker
from studiobridge.core.capabilities import CapabilityRegistry, create_default_registry
from studiobridge.core.errors import (
    BrokerError,
    ConnectionError,
    DisconnectedError,
    LeaseError,
    NoBrokerError,
    NoDeviceError,
    ReadOnlyError,
    StudioBridgeError,
    UnavailableError,
    UnverifiedWriteError,
    VersionMismatchError,
)
from studiobridge.device.assets._sb_api import ALLOW
from studiobridge.ports.base import MidiPort
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.capabilities import check_operation_capability
from studiobridge.sdk.trace import StatsAccumulator, TraceRecord
from studiobridge.wire.session import is_mutating_operation as is_wire_mutating


def is_operation_mutating(op: str) -> bool:
    """Check if an operation modifies FL Studio state per spec [SAF-01]."""
    if is_wire_mutating(op):
        return True
    if "." in op:
        mod_name, func_name = op.split(".", 1)
        if mod_name in ALLOW and func_name in ALLOW[mod_name]:
            return bool(ALLOW[mod_name][func_name].get("mutating", False))
        lowered = func_name.lower()
        if any(
            lowered.startswith(prefix)
            for prefix in (
                "set",
                "add",
                "del",
                "remove",
                "mute",
                "solo",
                "arm",
                "trigger",
                "stop",
                "play",
                "record",
            )
        ):
            return True
    return False


@dataclass(frozen=True, slots=True)
class Status:
    """Strongly typed snapshot of active FL Studio and StudioBridge session state.

    Defined per spec 09_l1_sdk.md §2:
    Status(fl_version, api, project, mode, caps_summary, rtt, sid, fp, lease_holder, backend, ...)
    """

    fl_version: str
    api: int
    project: str | None
    mode: str
    caps_summary: dict[str, Any]
    rtt: float
    sid: int = 0
    fp: str | None = None
    lease_holder: str | None = None
    backend: str = "embedded"
    connected: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize Status to dictionary."""
        return {
            "fl_version": self.fl_version,
            "api": self.api,
            "project": self.project,
            "mode": self.mode,
            "caps_summary": self.caps_summary,
            "rtt": self.rtt,
            "sid": self.sid,
            "fp": self.fp,
            "lease_holder": self.lease_holder,
            "backend": self.backend,
            "connected": self.connected,
            **self.extra,
        }

    def __await__(self):
        """Allow Status instances to be transparently awaited for async compatibility."""

        async def _identity() -> Status:
            return self

        return _identity().__await__()


class Session:
    """Session managing broker communication, handshake negotiation, and operation dispatch."""

    def __init__(
        self,
        *,
        backend: str = "embedded",
        mode: str = "read_only",
        caps: CapabilityRegistry | None = None,
    ) -> None:
        self.backend: str = backend
        self.mode: str = mode
        self.caps: CapabilityRegistry = caps if caps is not None else create_default_registry()
        self.stats_accumulator: StatsAccumulator = StatsAccumulator()
        self.client_id: str = f"sdk_{secrets.token_hex(4)}"

        self.sid: int = 0
        self.fp: str | None = None
        self.fl_version: str = "24.1.0"
        self.api: int = 44
        self.project: str | None = None
        self.last_rtt: float = 0.0
        self.lease_holder: str | None = None

        self._is_connected: bool = False
        self._broker: EmbeddedBroker | None = None
        self._client: BrokerClient | None = None
        self._trace_listeners: list[Callable[[TraceRecord], None]] = []

    async def acquire_lease(
        self,
        ttl: float = 15.0,
        purpose: str = "sdk_session",
    ) -> dict[str, Any]:
        """Acquire writer lease for mutating operations."""
        if self.backend == "embedded":
            assert self._broker is not None
            lease_dict = await self._broker.lease_acquire(self.client_id, ttl=ttl, purpose=purpose)
        else:
            assert self._client is not None
            lease_dict = await self._client.lease_acquire(ttl=ttl, purpose=purpose)
        self.lease_holder = self.client_id
        return lease_dict

    async def release_lease(self) -> dict[str, Any]:
        """Release active writer lease."""
        if self.backend == "embedded":
            assert self._broker is not None
            res = await self._broker.lease_release(self.client_id)
        else:
            assert self._client is not None
            res = await self._client.lease_release()
        self.lease_holder = None
        return res

    @property
    def is_connected(self) -> bool:
        """Whether session is currently connected and authenticated."""
        return self._is_connected

    def register_trace_collector(self, collector: Callable[[TraceRecord], None]) -> None:
        """Register a callback for recording trace events."""
        if collector not in self._trace_listeners:
            self._trace_listeners.append(collector)

    def unregister_trace_collector(self, collector: Callable[[TraceRecord], None]) -> None:
        """Unregister a trace callback."""
        if collector in self._trace_listeners:
            self._trace_listeners.remove(collector)

    def _notify_trace(self, record: TraceRecord) -> None:
        for cb in list(self._trace_listeners):
            with contextlib.suppress(Exception):
                cb(record)

    @classmethod
    async def create_and_connect(
        cls,
        *,
        embedded: bool = False,
        port: MidiPort | str | None = None,
        broker: BrokerClient | EmbeddedBroker | None = None,
        secret: str | None = None,
        direct_handler: Callable[[str, dict[str, Any]], Any] | None = None,
        host: str = "127.0.0.1",
        port_number: int | None = None,
        token: str | None = None,
        timeout: float = 10.0,
        mode: str = "read_only",
        caps: CapabilityRegistry | None = None,
    ) -> Session:
        """Create and connect a new Session."""
        session = cls(
            backend="embedded" if embedded else "tcp",
            mode=mode,
            caps=caps,
        )
        await session._connect(
            embedded=embedded,
            port=port,
            broker=broker,
            secret=secret,
            direct_handler=direct_handler,
            host=host,
            port_number=port_number,
            token=token,
            timeout=timeout,
        )
        return session

    async def _connect(
        self,
        *,
        embedded: bool = False,
        port: MidiPort | str | None = None,
        broker: BrokerClient | EmbeddedBroker | None = None,
        secret: str | None = None,
        direct_handler: Callable[[str, dict[str, Any]], Any] | None = None,
        host: str = "127.0.0.1",
        port_number: int | None = None,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Internal asynchronous connection and handshake logic."""
        if embedded:
            self.backend = "embedded"
            if isinstance(broker, EmbeddedBroker):
                self._broker = broker
            else:
                resolved_port: MidiPort | None = None
                if isinstance(port, MidiPort):
                    resolved_port = port
                elif isinstance(port, str):
                    # Resolve fake port or string port name
                    fake_a, _ = FakeMidiPort.create_pair(name_a=port, name_b=f"{port}_Peer")
                    resolved_port = fake_a

                self._broker = EmbeddedBroker(
                    port=resolved_port,
                    secret=secret,
                    direct_handler=direct_handler,
                )

            await self._broker.start()

            # Handshake negotiation
            try:
                if self._broker.port is not None:
                    try:
                        hello_res = await self._broker.device_call(
                            "hello", timeout=min(timeout, 2.0)
                        )
                        if isinstance(hello_res, dict):
                            self.sid = int(hello_res.get("sid", self._broker.session.sid))
                            self.fp = hello_res.get("fp", self._broker.session.fp)
                            self._broker.session.sid = self.sid
                            self._broker.session.fp = self.fp or ""
                            if "fl" in hello_res and "api_version" in hello_res["fl"]:
                                self.api = int(hello_res["fl"]["api_version"])
                        else:
                            info = await self._broker.session_info()
                            self.sid = int(info.get("sid", 1))
                            self.fp = info.get("fp")
                            self._broker.session.sid = self.sid
                            self._broker.session.fp = self.fp or ""
                    except Exception:
                        info = await self._broker.session_info()
                        self.sid = int(info.get("sid", 1))
                        self.fp = info.get("fp")
                        self._broker.session.sid = self.sid
                        self._broker.session.fp = self.fp or ""
                else:
                    info = await self._broker.session_info()
                    self.sid = int(info.get("sid", 1))
                    self.fp = info.get("fp")
                    self._broker.session.sid = self.sid
                    self._broker.session.fp = self.fp or ""
            except Exception as exc:
                raise ConnectionError(
                    f"Embedded broker handshake failed: {exc}",
                    code="E_NOBROKER",
                    details={"error": str(exc)},
                ) from exc

            # Ping and measure RTT
            t0 = time.monotonic()
            await self._broker.ping()
            self.last_rtt = round(time.monotonic() - t0, 4)
            self.stats_accumulator.record_ping(self.last_rtt * 1000)
            self._is_connected = True

            if self.mode in {"write", "unsafe"}:
                await self.acquire_lease()

        else:
            self.backend = "tcp"
            if isinstance(broker, BrokerClient):
                self._client = broker
            else:
                # Ensure daemon is running via supervisor per [BRK-03], [BRK-06]
                if port_number is None:
                    try:
                        resolved_host, resolved_port_num = ensure_broker(host=host, timeout=timeout)
                        port_number = resolved_port_num
                        host = resolved_host
                    except BrokerError as exc:
                        raise NoBrokerError(
                            f"Could not connect to or auto-start StudioBridge broker daemon "
                            f"on {host}: {exc}",
                            code="E_NOBROKER",
                            details={"host": host, "error": str(exc)},
                            remedy=(
                                "Run 'sbridge broker start' or inspect logs in "
                                "%LOCALAPPDATA%\\studiobridge\\logs."
                            ),
                        ) from exc
                    except Exception as exc:
                        raise NoBrokerError(
                            f"Unexpected error starting broker daemon: {exc}",
                            code="E_NOBROKER",
                            details={"error": str(exc)},
                        ) from exc

                self._client = BrokerClient(
                    host=host,
                    port=port_number,
                    token=token,
                )

            # Connect TCP transport
            try:
                await self._client.connect()
            except BrokerError as exc:
                if exc.code == "E_AUTH":
                    raise ConnectionError(
                        f"Broker authentication failed: {exc}",
                        code="E_AUTH",
                        details=exc.details,
                        remedy=exc.remedy,
                    ) from exc
                raise NoBrokerError(
                    f"Connection to broker failed: {exc}",
                    code="E_NOBROKER",
                    details=exc.details,
                    remedy=exc.remedy,
                ) from exc
            except OSError as exc:
                raise NoBrokerError(
                    f"TCP connection refused on {host}:{port_number}: {exc}",
                    code="E_NOBROKER",
                    details={"host": host, "port": port_number},
                    remedy="Ensure broker is running on target host and port.",
                ) from exc

            # Handshake negotiation and version validation per [BRK-05], [SDK-02]
            try:
                info = await self._client.session_info()
                self.sid = int(info.get("sid", 1))
                self.fp = info.get("fp")

                broker_ver = str(info.get("version", ""))
                if broker_ver:
                    # Check minor version alignment
                    client_minor = __version__.split(".")[:2]
                    broker_minor = broker_ver.split(".")[:2]
                    if client_minor != broker_minor:
                        raise VersionMismatchError(
                            f"StudioBridge broker version ({broker_ver}) does not match "
                            f"client version ({__version__}).",
                            code="E_VERSION",
                            details={"broker_version": broker_ver, "client_version": __version__},
                            remedy="Upgrade studiobridge package or restart broker daemon.",
                        )

            except BrokerError as exc:
                if exc.code == "E_NODEVICE":
                    raise NoDeviceError(
                        f"Device script is not connected: {exc}",
                        code="E_NODEVICE",
                        details=exc.details,
                        remedy=exc.remedy,
                    ) from exc
                elif exc.code == "E_VERSION":
                    raise VersionMismatchError(
                        f"Version negotiation failed: {exc}",
                        code="E_VERSION",
                        details=exc.details,
                        remedy=exc.remedy,
                    ) from exc
                elif exc.code == "E_DISCONNECTED":
                    raise DisconnectedError(
                        f"Broker disconnected during handshake: {exc}",
                        code="E_DISCONNECTED",
                        details=exc.details,
                        remedy=exc.remedy,
                    ) from exc
                raise ConnectionError(
                    f"Broker handshake failed: {exc}",
                    code=exc.code,
                    details=exc.details,
                    remedy=exc.remedy,
                ) from exc

            # Ping and measure RTT
            t0 = time.monotonic()
            await self._client.ping()
            self.last_rtt = round(time.monotonic() - t0, 4)
            self.stats_accumulator.record_ping(self.last_rtt * 1000)
            self._is_connected = True

            if self.mode in {"write", "unsafe"}:
                await self.acquire_lease()

    async def call(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        opts: dict[str, Any] | None = None,
        priority: str | None = None,
        timeout: float = 5.0,
    ) -> Any:
        """Execute a device operation through active broker transport."""
        if not self._is_connected:
            raise DisconnectedError(
                "Cannot issue operation: Session is not connected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling operations.",
            )

        call_args = dict(args) if args else {}

        # 1. Capability preflight gating per [CAP-02]
        check_operation_capability(self.caps, op)

        # 2. Safety mode read-only guard per [SAF-01]
        if self.mode == "read_only" and is_operation_mutating(op):
            raise ReadOnlyError(
                f"Cannot execute mutating operation '{op}' in read-only mode.",
                code="E_READONLY",
                details={"operation": op, "mode": self.mode},
                remedy=(
                    "Acquire writer lease and set mode to 'write' via fl.safety.set_mode('write')."
                ),
            )

        # 3. Observability tracing and timing
        t0 = time.monotonic()
        self._notify_trace(
            TraceRecord(
                timestamp=t0,
                direction="send",
                op=op,
                data=call_args,
            )
        )

        try:
            if self.backend == "embedded":
                assert self._broker is not None
                res = await self._broker.device_call(
                    op,
                    call_args,
                    opts=opts,
                    client_id=self.client_id,
                    priority=priority,
                    timeout=timeout,
                )
            else:
                assert self._client is not None
                res = await self._client.device_call(
                    op,
                    call_args,
                    opts=opts,
                    priority=priority,
                    timeout=timeout,
                )

            duration_ms = round((time.monotonic() - t0) * 1000, 3)
            self.stats_accumulator.record_call(op, duration_ms, success=True)
            self._notify_trace(
                TraceRecord(
                    timestamp=time.monotonic(),
                    direction="recv",
                    op=op,
                    duration_ms=duration_ms,
                    data=res,
                )
            )
            return res

        except Exception as exc:
            duration_ms = round((time.monotonic() - t0) * 1000, 3)
            self.stats_accumulator.record_call(op, duration_ms, success=False)
            self._notify_trace(
                TraceRecord(
                    timestamp=time.monotonic(),
                    direction="recv",
                    op=op,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
            )

            # Map error taxonomy to actionable exceptions
            if isinstance(exc, StudioBridgeError):
                if exc.code == "E_NODEVICE":
                    raise NoDeviceError(str(exc), details=exc.details, remedy=exc.remedy) from exc
                elif exc.code == "E_VERSION":
                    raise VersionMismatchError(
                        str(exc), details=exc.details, remedy=exc.remedy
                    ) from exc
                elif exc.code == "E_DISCONNECTED":
                    raise DisconnectedError(
                        str(exc), details=exc.details, remedy=exc.remedy
                    ) from exc
                elif exc.code == "E_LEASE":
                    raise LeaseError(str(exc), details=exc.details, remedy=exc.remedy) from exc
                elif exc.code == "E_UNAVAILABLE":
                    raise UnavailableError(
                        str(exc),
                        details=exc.details,
                        remedy=exc.remedy,
                        alternatives=getattr(exc, "alternatives", []),
                    ) from exc
                elif exc.code == "E_UNVERIFIED":
                    raise UnverifiedWriteError(
                        str(exc), details=exc.details, remedy=exc.remedy
                    ) from exc
            raise

    async def batch(self, ops: list[dict[str, Any]], timeout: float = 15.0) -> list[Any]:
        """Execute a batch of operations in a single wire request."""
        if not self._is_connected:
            raise DisconnectedError(
                "Cannot issue batch: Session is not connected.",
                code="E_DISCONNECTED",
            )

        # Check safety mode
        if self.mode == "read_only" and any(
            is_operation_mutating(op.get("op", op.get("fn", ""))) for op in ops
        ):
            raise ReadOnlyError(
                "Cannot execute mutating operations in a batch while in read-only mode.",
                code="E_READONLY",
                remedy=(
                    "Acquire writer lease and set mode to 'write' via fl.safety.set_mode('write')."
                ),
            )

        t0 = time.monotonic()
        try:
            if self.backend == "embedded":
                assert self._broker is not None
                results = await self._broker.device_batch(
                    ops, client_id=self.client_id, timeout=timeout
                )
            else:
                assert self._client is not None
                results = await self._client.device_batch(ops, timeout=timeout)

            duration_ms = round((time.monotonic() - t0) * 1000, 3)
            self.stats_accumulator.record_batch(len(ops), duration_ms, success=True)
            return results
        except Exception:
            duration_ms = round((time.monotonic() - t0) * 1000, 3)
            self.stats_accumulator.record_batch(len(ops), duration_ms, success=False)
            raise

    async def ping(self) -> float:
        """Measure round-trip time and update heartbeat latency."""
        t0 = time.monotonic()
        if self.backend == "embedded":
            assert self._broker is not None
            await self._broker.ping()
        else:
            assert self._client is not None
            await self._client.ping()

        self.last_rtt = round(time.monotonic() - t0, 4)
        self.stats_accumulator.record_ping(self.last_rtt * 1000)
        return self.last_rtt

    def status(self) -> Status:
        """Return structured session status snapshot per 09_l1_sdk.md §2."""
        lease_holder: str | None = None
        if self.backend == "embedded" and self._broker is not None:
            lease_state = self._broker.lease_manager.get_state()
            lease_holder = lease_state.get("owner")

        return Status(
            fl_version=self.fl_version,
            api=self.api,
            project=self.project,
            mode=self.mode,
            caps_summary=self.caps.aggregate_status()["summary"],
            rtt=self.last_rtt,
            sid=self.sid,
            fp=self.fp,
            lease_holder=lease_holder,
            backend=self.backend,
            connected=self._is_connected,
        )

    async def close(self) -> None:
        """Close active session and release all held resources."""
        if not self._is_connected:
            return
        self._is_connected = False
        if self.lease_holder == self.client_id:
            with contextlib.suppress(Exception):
                await self.release_lease()
        if self._broker is not None:
            await self._broker.stop()
            self._broker = None
        if self._client is not None:
            await self._client.close()
            self._client = None


__all__ = [
    "Session",
    "Status",
]
