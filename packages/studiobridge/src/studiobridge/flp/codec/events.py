"""Binary FLP event representation, event ID classification, and varint encoding.

Implements clean-room event structures per 07_l0e_flp_engine.md §3.1 and [FLP-01].
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from studiobridge.core.errors import FlpParseError

MIN_BYTE_EVENT_ID: int = 0
MAX_BYTE_EVENT_ID: int = 63

MIN_WORD_EVENT_ID: int = 64
MAX_WORD_EVENT_ID: int = 127

MIN_DWORD_EVENT_ID: int = 128
MAX_DWORD_EVENT_ID: int = 191

MIN_VAR_EVENT_ID: int = 192
MAX_VAR_EVENT_ID: int = 255


class EventKind(str, enum.Enum):
    """Classification of FLP event ID payload sizes [FLP-01]."""

    BYTE = "byte"  # 0–63 (1-byte payload)
    WORD = "word"  # 64–127 (2-byte payload, uint16 little-endian)
    DWORD = "dword"  # 128–191 (4-byte payload, uint32 little-endian)
    VARIABLE = "variable"  # 192–255 (variable-length payload prefixed with 7-bit varint)


@dataclass(frozen=True, slots=True)
class LenEnc:
    """Variable-length integer encoding metadata [FLP-01].

    Preserves the exact byte sequence of variable-length quantity (varint)
    length headers, guaranteeing lossless roundtrips even when non-canonical
    padding bytes are present in the original binary file.
    """

    value: int
    raw: bytes

    def __bytes__(self) -> bytes:
        return self.raw

    def __len__(self) -> int:
        return len(self.raw)


def event_kind(event_id: int) -> EventKind:
    """Return the structural payload classification for an event ID [FLP-01]."""
    if MIN_BYTE_EVENT_ID <= event_id <= MAX_BYTE_EVENT_ID:
        return EventKind.BYTE
    if MIN_WORD_EVENT_ID <= event_id <= MAX_WORD_EVENT_ID:
        return EventKind.WORD
    if MIN_DWORD_EVENT_ID <= event_id <= MAX_DWORD_EVENT_ID:
        return EventKind.DWORD
    if MIN_VAR_EVENT_ID <= event_id <= MAX_VAR_EVENT_ID:
        return EventKind.VARIABLE
    raise ValueError(f"Invalid FLP event ID: {event_id} (must be in range 0–255)")


def event_fixed_size(event_id: int) -> int | None:
    """Return fixed payload size in bytes, or None for variable-length events."""
    if MIN_BYTE_EVENT_ID <= event_id <= MAX_BYTE_EVENT_ID:
        return 1
    if MIN_WORD_EVENT_ID <= event_id <= MAX_WORD_EVENT_ID:
        return 2
    if MIN_DWORD_EVENT_ID <= event_id <= MAX_DWORD_EVENT_ID:
        return 4
    if MIN_VAR_EVENT_ID <= event_id <= MAX_VAR_EVENT_ID:
        return None
    raise ValueError(f"Invalid FLP event ID: {event_id} (must be in range 0–255)")


def encode_varint(value: int) -> bytes:
    """Encode an integer into 7-bit little-endian groups with MSB continuation [FLP-01].

    In the FLP container specification, variable-length event payloads are
    prefixed with a 7-bit little-endian variable-length quantity. The 8th bit
    (0x80) indicates continuation.
    """
    if value < 0:
        raise ValueError(f"Varint value must be non-negative, got {value}")
    if value == 0:
        return b"\x00"

    out = bytearray()
    v = value
    while True:
        b = v & 0x7F
        v >>= 7
        if v > 0:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def decode_varint(
    data: bytes | memoryview,
    offset: int = 0,
    limit: int | None = None,
    *,
    base_offset: int = 0,
) -> tuple[int, LenEnc, int]:
    """Decode a 7-bit little-endian varint from data [FLP-01].

    Returns (value, LenEnc, next_offset).
    Raises FlpParseError with exact byte offset on truncation or integer overflow.
    """
    max_pos = len(data) if limit is None else limit
    if offset >= max_pos:
        raise FlpParseError(
            f"Unexpected end of data reading varint at offset {base_offset + offset}",
            offset=base_offset + offset,
            details={"offset": base_offset + offset},
        )

    pos = offset
    value = 0
    shift = 0

    while pos < max_pos:
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        shift += 7

        if (b & 0x80) == 0:
            raw_bytes = bytes(data[offset:pos])
            return value, LenEnc(value=value, raw=raw_bytes), pos

        if shift > 35:
            raise FlpParseError(
                f"Varint exceeds 35-bit representation limit at offset {base_offset + offset}",
                offset=base_offset + offset,
                details={"offset": base_offset + offset, "shift": shift},
            )

    raise FlpParseError(
        f"Unterminated variable-length integer encoding at offset {base_offset + offset}",
        offset=base_offset + offset,
        details={"offset": base_offset + offset, "bytes_read": pos - offset},
    )


class Event:
    """Binary FLP event representation [FLP-01].

    Attributes:
        id: Integer event tag (0–255).
        raw: Exact binary payload bytes (or lazily materialized on access).
        enc: Optional LenEnc recording original varint encoding bytes for
             variable-length events.
    """

    __slots__ = ("_raw", "enc", "id")

    def __init__(
        self,
        id: int,
        raw: bytes | Callable[[], bytes],
        enc: LenEnc | None = None,
    ) -> None:
        if not (0 <= id <= 255):
            raise ValueError(f"Event ID must be in range 0–255, got {id}")
        self.id = id
        self._raw = raw
        self.enc = enc

    @property
    def raw(self) -> bytes:
        """Exact payload bytes, materialized on first access if lazy."""
        if callable(self._raw):
            self._raw = self._raw()
        return self._raw

    @raw.setter
    def raw(self, value: bytes) -> None:
        self._raw = value

    @property
    def is_lazy(self) -> bool:
        """True if the event payload has not yet been materialized from disk/stream."""
        return callable(self._raw)

    @property
    def kind(self) -> EventKind:
        """Payload size classification for this event."""
        return event_kind(self.id)

    @property
    def is_byte(self) -> bool:
        """True if event has 1-byte fixed payload (IDs 0–63)."""
        return MIN_BYTE_EVENT_ID <= self.id <= MAX_BYTE_EVENT_ID

    @property
    def is_word(self) -> bool:
        """True if event has 2-byte fixed payload (IDs 64–127)."""
        return MIN_WORD_EVENT_ID <= self.id <= MAX_WORD_EVENT_ID

    @property
    def is_dword(self) -> bool:
        """True if event has 4-byte fixed payload (IDs 128–191)."""
        return MIN_DWORD_EVENT_ID <= self.id <= MAX_DWORD_EVENT_ID

    @property
    def is_variable(self) -> bool:
        """True if event has variable-length payload (IDs 192–255)."""
        return MIN_VAR_EVENT_ID <= self.id <= MAX_VAR_EVENT_ID

    def as_int(self, *, signed: bool = False) -> int:
        """Interpret fixed-size payload bytes as integer (little-endian)."""
        return int.from_bytes(self.raw, byteorder="little", signed=signed)

    def as_str(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Interpret variable-length payload as string helper [FLP-06]."""
        return self.raw.decode(encoding, errors=errors)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return False
        return self.id == other.id and self.raw == other.raw and self.enc == other.enc

    def __repr__(self) -> str:
        raw_repr = "<lazy>" if callable(self._raw) else repr(self._raw)
        return f"Event(id={self.id}, raw={raw_repr}, enc={self.enc})"
