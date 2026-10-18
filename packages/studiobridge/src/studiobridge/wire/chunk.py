"""Payload chunking, splitting, and multi-chunk reassembly buffer.

Implements message chunking and out-of-order reassembly with duplicate tolerance
and two-stage timeout expiry per spec 03_l0a_wire_protocol.md §4.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from studiobridge.core.errors import ProtocolError

if TYPE_CHECKING:
    from studiobridge.wire.frame import Frame

# Default maximum payload per frame in bytes (512 max frame - 22 overhead)
DEFAULT_MAX_PAYLOAD: int = 490

# Inbound message limits per [WIRE-13]
MAX_DEVICE_INBOUND: int = 96 * 1024  # 96 KiB = 98,304 bytes
MAX_CLIENT_INBOUND: int = 4 * 1024 * 1024  # 4 MiB = 4,194,304 bytes

# Default buffer reassembly timeout in milliseconds per [WIRE-12]
DEFAULT_TIMEOUT_MS: float = 2000.0

# Out-of-order tolerance window per [WIRE-11]
DEFAULT_WINDOW_SIZE: int = 8


def chunk_payload(
    payload: bytes,
    max_payload: int = DEFAULT_MAX_PAYLOAD,
    max_message_size: int = MAX_DEVICE_INBOUND,
) -> list[bytes]:
    """Split a serialized payload into numbered chunks.

    Args:
        payload: Raw payload bytes to divide into frame-sized chunks.
        max_payload: Maximum bytes per chunk (default 490).
        max_message_size: Upper limit for inbound message length (default 96 KiB).

    Returns:
        A list of byte chunks. For an empty payload, returns ``[b""]`` so CCNT is at least 1.

    Raises:
        ProtocolError: If payload length exceeds ``max_message_size`` (code ``E_TOOBIG``).
        ValueError: If ``max_payload`` is less than or equal to 0.
    """
    if max_payload <= 0:
        raise ValueError(f"max_payload must be positive integer, got {max_payload}")

    payload_len = len(payload)
    if payload_len > max_message_size:
        raise ProtocolError(
            f"Payload length ({payload_len} bytes) exceeds maximum message limit "
            f"({max_message_size} bytes)",
            code="E_TOOBIG",
            details={"payload_len": payload_len, "max_message_size": max_message_size},
        )

    if payload_len == 0:
        return [b""]

    return [payload[i : i + max_payload] for i in range(0, payload_len, max_payload)]


@dataclass(slots=True, frozen=True)
class ReassemblyExpiry:
    """Represents an expiration event for an in-flight message reassembly buffer."""

    key: tuple[int, int, int]
    action: str  # "nack" (first timeout) or "discard" (second timeout)
    missing: list[int]


@dataclass(slots=True)
class _MessageBuffer:
    """Internal state tracking chunks received for a specific (kind, sid, mid)."""

    kind: int
    sid: int
    mid: int
    ccnt: int
    chunks: dict[int, bytes] = field(default_factory=dict)
    total_bytes: int = 0
    created_at: float = 0.0
    last_active_at: float = 0.0
    expiry_count: int = 0


class Reassembler:
    """Manages multi-chunk message reconstitution across out-of-order frames.

    Keyed by ``(KIND, SID, MID)`` per ``[WIRE-11]``. Tolerates out-of-order chunk arrival
    (optionally constrained by a sliding window), ignores duplicate chunks, enforces
    message length bounds, and supports two-stage timeout expiry per ``[WIRE-12]``.
    """

    def __init__(
        self,
        timeout_ms: float = DEFAULT_TIMEOUT_MS,
        max_message_size: int = MAX_DEVICE_INBOUND,
        window_size: int | None = None,
    ) -> None:
        """Initialize reassembler.

        Args:
            timeout_ms: Incomplete message expiry timeout in milliseconds (default 2000 ms).
            max_message_size: Maximum reassembled message size in bytes (default 96 KiB).
            window_size: Optional sliding window constraint for out-of-order chunks.
                If None, any out-of-order index in range [0, ccnt) is tolerated.
        """
        self.timeout_ms = timeout_ms
        self.max_message_size = max_message_size
        self.window_size = window_size
        self._buffers: dict[tuple[int, int, int], _MessageBuffer] = {}
        self._completed: dict[tuple[int, int, int], None] = {}
        self._max_completed_cache: int = 256

    @property
    def active_count(self) -> int:
        """Return number of messages currently pending reassembly."""
        return len(self._buffers)

    def feed(self, frame: Frame, now_ms: float | None = None) -> bytes | None:
        """Feed a decoded Frame into the reassembler.

        Args:
            frame: A decoded wire Frame.
            now_ms: Optional millisecond timestamp (defaults to monotonic time).

        Returns:
            The complete reassembled payload bytes if this frame completed a message,
            or None if the message remains incomplete.
        """
        raw_payload = frame.payload
        if isinstance(raw_payload, str):
            payload_bytes = raw_payload.encode("ascii")
        elif not isinstance(raw_payload, bytes):
            payload_bytes = bytes(raw_payload)
        else:
            payload_bytes = raw_payload

        return self.add_chunk(
            kind=int(frame.kind),
            sid=frame.sid,
            mid=frame.mid,
            cidx=frame.cidx,
            ccnt=frame.ccnt,
            payload=payload_bytes,
            now_ms=now_ms,
        )

    def add_chunk(
        self,
        kind: int,
        sid: int,
        mid: int,
        cidx: int,
        ccnt: int,
        payload: bytes,
        now_ms: float | None = None,
    ) -> bytes | None:
        """Add a single chunk to the reassembly buffer.

        Args:
            kind: Frame kind (e.g. REQ=1, RES=2, EVT=3, CTL=4).
            sid: Session identifier.
            mid: Message identifier.
            cidx: 0-based chunk index.
            ccnt: Total chunk count (>= 1).
            payload: Chunk payload bytes.
            now_ms: Optional millisecond timestamp for timeout tracking.

        Returns:
            The complete reassembled payload bytes if this chunk completed the message,
            or None if more chunks are needed or chunk was ignored.

        Raises:
            ProtocolError: On protocol violations (code E_PROTO) or size limits (code E_TOOBIG).
        """
        if ccnt < 1:
            raise ProtocolError(
                f"Invalid chunk count {ccnt}: must be >= 1",
                code="E_PROTO",
                details={"kind": kind, "sid": sid, "mid": mid, "ccnt": ccnt},
            )

        if cidx < 0 or cidx >= ccnt:
            raise ProtocolError(
                f"Chunk index {cidx} out of range [0, {ccnt})",
                code="E_PROTO",
                details={"cidx": cidx, "ccnt": ccnt},
            )

        key = (kind, sid, mid)

        # Ignore late arriving duplicate chunks for already completed messages
        if key in self._completed:
            return None

        # Single chunk fast path
        if ccnt == 1:
            if len(payload) > self.max_message_size:
                raise ProtocolError(
                    f"Payload size {len(payload)} exceeds maximum message limit "
                    f"({self.max_message_size} bytes)",
                    code="E_TOOBIG",
                    details={"size": len(payload), "max_size": self.max_message_size},
                )
            # If there was an existing buffer for this key, clear it
            self._buffers.pop(key, None)
            self._record_completed(key)
            return payload

        now = (time.monotonic() * 1000.0) if now_ms is None else float(now_ms)

        buf = self._buffers.get(key)
        if buf is None:
            if len(payload) > self.max_message_size:
                raise ProtocolError(
                    f"Initial chunk size {len(payload)} exceeds maximum message limit "
                    f"({self.max_message_size} bytes)",
                    code="E_TOOBIG",
                )
            buf = _MessageBuffer(
                kind=kind,
                sid=sid,
                mid=mid,
                ccnt=ccnt,
                created_at=now,
                last_active_at=now,
            )
            self._buffers[key] = buf
        else:
            if buf.ccnt != ccnt:
                raise ProtocolError(
                    f"Mismatched ccnt {ccnt} != {buf.ccnt} for message {key}",
                    code="E_PROTO",
                    details={"key": key, "existing_ccnt": buf.ccnt, "chunk_ccnt": ccnt},
                )
            buf.last_active_at = now

        # Duplicate check: ignore silently per [WIRE-11]
        if cidx in buf.chunks:
            return None

        # Optional sliding window check: tolerate up to window_size ahead of lowest missing
        if self.window_size is not None and self.window_size > 0:
            min_missing = next(i for i in range(buf.ccnt) if i not in buf.chunks)
            if cidx - min_missing >= self.window_size:
                # Outside sliding window tolerance: drop chunk
                return None

        # Total message size check
        if buf.total_bytes + len(payload) > self.max_message_size:
            del self._buffers[key]
            raise ProtocolError(
                f"Reassembled message exceeds max size ({self.max_message_size} bytes)",
                code="E_TOOBIG",
                details={
                    "total_bytes": buf.total_bytes + len(payload),
                    "max_size": self.max_message_size,
                },
            )

        buf.chunks[cidx] = payload
        buf.total_bytes += len(payload)

        # Completion check
        if len(buf.chunks) == buf.ccnt:
            complete = b"".join(buf.chunks[i] for i in range(buf.ccnt))
            del self._buffers[key]
            self._record_completed(key)
            return complete

        return None

    def _record_completed(self, key: tuple[int, int, int]) -> None:
        """Record completed message key in bounded cache to filter late duplicate chunks."""
        self._completed[key] = None
        while len(self._completed) > self._max_completed_cache:
            first_key = next(iter(self._completed))
            del self._completed[first_key]

    def get_missing(self, kind: int, sid: int, mid: int) -> list[int]:
        """Return list of missing chunk indices for a message in progress."""
        buf = self._buffers.get((kind, sid, mid))
        if buf is None:
            return []
        return [i for i in range(buf.ccnt) if i not in buf.chunks]

    def check_timeouts(self, now_ms: float | None = None) -> list[ReassemblyExpiry]:
        """Check all active buffers against timeout_ms and return expiry actions.

        Per [WIRE-12]:
        - On first expiry, emits 'nack' action with missing chunk indices and increments count.
        - On second expiry, emits 'discard' action and purges the buffer.
        """
        now = (time.monotonic() * 1000.0) if now_ms is None else float(now_ms)
        expiries: list[ReassemblyExpiry] = []
        to_delete: list[tuple[int, int, int]] = []

        for key, buf in self._buffers.items():
            if now - buf.last_active_at >= self.timeout_ms:
                missing = [i for i in range(buf.ccnt) if i not in buf.chunks]
                if buf.expiry_count == 0:
                    buf.expiry_count = 1
                    buf.last_active_at = now
                    expiries.append(ReassemblyExpiry(key=key, action="nack", missing=missing))
                else:
                    to_delete.append(key)
                    expiries.append(ReassemblyExpiry(key=key, action="discard", missing=missing))

        for key in to_delete:
            del self._buffers[key]

        return expiries

    def cancel(self, kind: int, sid: int, mid: int) -> bool:
        """Cancel and purge a specific message buffer. Returns True if found."""
        return self._buffers.pop((kind, sid, mid), None) is not None

    def clear(self) -> None:
        """Purge all active reassembly buffers and completed message cache."""
        self._buffers.clear()
        self._completed.clear()
