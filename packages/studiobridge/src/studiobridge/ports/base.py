"""Abstract MIDI port interface, port descriptors, and runtime telemetry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from studiobridge.core.errors import PortError


@dataclass(frozen=True, slots=True)
class MidiPortInfo:
    """Metadata describing an enumerated MIDI input or output port."""

    direction: Literal["in", "out"]
    index: int
    name: str
    api: str  # e.g. "winmm", "fake"
    manufacturer: str | None = None
    driver_version: str | None = None

    def __iter__(self):
        yield self.direction
        yield self.index
        yield self.name
        yield self.api
        yield self.manufacturer
        yield self.driver_version


@dataclass
class PortStats:
    """Runtime telemetry and transfer counters for a MIDI port."""

    bytes_sent: int = 0
    bytes_recv: int = 0
    frames_sent: int = 0
    frames_recv: int = 0
    dropped: int = 0
    long_errors: int = 0

    @property
    def bytes_received(self) -> int:
        """Alias for bytes_recv."""
        return self.bytes_recv

    @property
    def frames_received(self) -> int:
        """Alias for frames_recv."""
        return self.frames_recv

    @property
    def dropped_frames(self) -> int:
        """Alias for dropped."""
        return self.dropped

    def reset(self) -> None:
        """Reset all statistical counters to zero."""
        self.bytes_sent = 0
        self.bytes_recv = 0
        self.frames_sent = 0
        self.frames_recv = 0
        self.dropped = 0
        self.long_errors = 0


@runtime_checkable
class MidiPort(Protocol):
    """Abstract interface protocol for MIDI port transports."""

    def list_ports(self) -> list[MidiPortInfo]:
        """Enumerate all visible MIDI input and output ports."""
        ...

    def open(
        self,
        in_name: str,
        out_name: str,
        *,
        sysex_buf: int = 16384,
        nbufs: int = 8,
    ) -> None:
        """Open input and output endpoints by name.

        Args:
            in_name: Name of the input MIDI endpoint.
            out_name: Name of the output MIDI endpoint.
            sysex_buf: Size in bytes for each prepared input SysEx buffer.
            nbufs: Number of prepared ring buffers to allocate.

        Raises:
            PortError: If an endpoint cannot be resolved or opened.
        """
        ...

    def send_sysex(self, data: bytes) -> None:
        """Send a raw SysEx message. Blocks until transmission completes or fails.

        Args:
            data: SysEx byte sequence starting with 0xF0 and ending with 0xF7.

        Raises:
            PortError: On transmission error or timeout.
        """
        ...

    def on_sysex(self, cb: Callable[[bytes], None]) -> None:
        """Register a callback for incoming SysEx messages.

        Callbacks are dispatched on a background worker thread.
        """
        ...

    def on_error(self, cb: Callable[[PortError], None]) -> None:
        """Register a callback for asynchronous port errors or unexpected disconnects."""
        ...

    def close(self) -> None:
        """Close input and output endpoints and release all resources."""
        ...

    @property
    def is_open(self) -> bool:
        """Return True if both input and output endpoints are currently open."""
        ...

    @property
    def stats(self) -> PortStats:
        """Return runtime transfer statistics."""
        ...

    @property
    def in_name(self) -> str | None:
        """Return the active input port name, or None if closed."""
        ...

    @property
    def out_name(self) -> str | None:
        """Return the active output port name, or None if closed."""
        ...
