"""SysEx Frame serialization, deserialization, and header validation.

Implements the StudioBridge SysEx frame layout per spec 03_l0a_wire_protocol.md §3:
  Offset  Len  Field     Meaning
  0       1    0xF0      SysEx start
  1       1    0x7D      Manufacturer ID (non-commercial / research)
  2       2    0x53 0x42 Magic "SB" (constant protocol identifier)
  4       1    VER       Protocol version (0x01)
  5       1    KIND      0x01 REQ, 0x02 RES, 0x03 EVT, 0x04 CTL
  6       1    FLAGS     bit0 reserved, bit1 ENC_JSON (0x02), bits2-6 reserved
  7       2    SID       Session ID (14-bit unsigned, 2 septets)
  9       3    MID       Message ID (21-bit unsigned, 3 septets)
  12      2    CIDX      Chunk index (0-based, 14-bit unsigned, 2 septets)
  14      2    CCNT      Chunk count (>= 1, 14-bit unsigned, 2 septets)
  16      2    PLEN      Payload length (14-bit unsigned, 2 septets)
  18      N    PAYLOAD   7-bit clean ASCII bytes
  18+N    3    CRC       CRC-16/CCITT-FALSE over [VER ... last payload byte] (2+7+7 bits)
  21+N    1    0xF7      SysEx end

Total overhead: 22 bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.crc import (
    crc16,
    pack_crc,
    pack_septets_14,
    pack_septets_21,
    unpack_crc,
    unpack_septets_14,
    unpack_septets_21,
)

# Wire protocol framing constants
SYSEX_START = 0xF0
SYSEX_END = 0xF7
MANUFACTURER_ID = 0x7D
MAGIC = b"SB"
PROTOCOL_VERSION = 0x01

# Frame structure sizing
HEADER_LEN = 18
TAIL_LEN = 4  # 3 bytes CRC + 1 byte 0xF7
FRAME_OVERHEAD = HEADER_LEN + TAIL_LEN  # 22 bytes

DEFAULT_MAX_FRAME = 512
MAX_FRAME_LIMIT = 1022
MAX_PAYLOAD_DEFAULT = DEFAULT_MAX_FRAME - FRAME_OVERHEAD  # 490 bytes
MAX_PAYLOAD_LIMIT = MAX_FRAME_LIMIT - FRAME_OVERHEAD  # 1000 bytes


class FrameKind(IntEnum):
    """Enumeration of frame types recognized by StudioBridge wire protocol."""

    REQ = 0x01  # Client request
    RES = 0x02  # Device response
    EVT = 0x03  # Device asynchronous event
    CTL = 0x04  # Wire control (nack, ack, busy)


class FrameFlags(IntFlag):
    """Bit flags embedded in SysEx frame header."""

    NONE = 0x00
    ENC_JSON = 0x02  # bit 1: Payload is JSON-encoded text


@dataclass
class Frame:
    """Discrete SysEx frame representation.

    Attributes:
        kind: Frame type (REQ=1, RES=2, EVT=3, CTL=4).
        flags: 7-bit flag byte (bit1 = ENC_JSON).
        sid: 14-bit session ID.
        mid: 21-bit message ID.
        cidx: 14-bit chunk index (0-based).
        ccnt: 14-bit chunk count (>= 1).
        payload_len: 14-bit payload length in bytes.
        payload: 7-bit clean ASCII bytes.
        crc: 16-bit CRC checksum computed over [VER ... last payload byte].
    """

    kind: int | FrameKind
    flags: int = 0
    sid: int = 0
    mid: int = 0
    cidx: int = 0
    ccnt: int = 1
    payload_len: int = 0
    payload: bytes | bytearray | memoryview | str = b""
    crc: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.payload, str):
            self.payload = self.payload.encode("ascii")
        elif isinstance(self.payload, (bytearray, memoryview)):
            self.payload = bytes(self.payload)
        if self.payload_len == 0 and len(self.payload) > 0:
            self.payload_len = len(self.payload)

    @property
    def is_req(self) -> bool:
        """True if frame is a client request."""
        return self.kind == FrameKind.REQ

    @property
    def is_res(self) -> bool:
        """True if frame is a device response."""
        return self.kind == FrameKind.RES

    @property
    def is_evt(self) -> bool:
        """True if frame is an asynchronous event."""
        return self.kind == FrameKind.EVT

    @property
    def is_ctl(self) -> bool:
        """True if frame is a wire control frame."""
        return self.kind == FrameKind.CTL

    def encode(self, *, max_frame_size: int | None = None) -> bytes:
        """Encode this frame into wire-format SysEx bytes."""
        return encode_frame(self, max_frame_size=max_frame_size)

    @classmethod
    def decode(cls, raw: bytes, *, max_frame_size: int | None = None) -> Frame:
        """Decode wire-format SysEx bytes into a Frame instance."""
        return decode_frame(raw, max_frame_size=max_frame_size)


def encode_frame(frame: Frame, *, max_frame_size: int | None = None) -> bytes:
    """Encode a Frame dataclass into raw SysEx bytes.

    Computes CRC-16 over [VER ... payload] and packs into 3 septets.
    Updates frame.crc and frame.payload_len on the instance.

    Raises:
        ProtocolError: If frame fields violate range bounds or payload contains non-7-bit bytes.
    """
    # 1. Validate kind
    kind_int = int(frame.kind)
    if kind_int < 0 or kind_int > 0x7F:
        raise ProtocolError(
            f"Frame kind out of 7-bit range: {kind_int}",
            code="E_PROTO",
            details={"kind": kind_int},
        )

    # 2. Validate flags
    if frame.flags < 0 or frame.flags > 0x7F:
        raise ProtocolError(
            f"Frame flags out of 7-bit range: {frame.flags}",
            code="E_PROTO",
            details={"flags": frame.flags},
        )

    # 3. Validate integer ranges
    if frame.sid < 0 or frame.sid > 0x3FFF:
        raise ProtocolError(
            f"Session ID (SID) out of 14-bit range: {frame.sid}",
            code="E_PROTO",
            details={"sid": frame.sid},
        )
    if frame.mid < 0 or frame.mid > 0x1FFFFF:
        raise ProtocolError(
            f"Message ID (MID) out of 21-bit range: {frame.mid}",
            code="E_PROTO",
            details={"mid": frame.mid},
        )
    if frame.cidx < 0 or frame.cidx > 0x3FFF:
        raise ProtocolError(
            f"Chunk index (CIDX) out of 14-bit range: {frame.cidx}",
            code="E_PROTO",
            details={"cidx": frame.cidx},
        )
    if frame.ccnt < 1 or frame.ccnt > 0x3FFF:
        raise ProtocolError(
            f"Chunk count (CCNT) must be between 1 and 16383, got {frame.ccnt}",
            code="E_PROTO",
            details={"ccnt": frame.ccnt},
        )
    if frame.cidx >= frame.ccnt:
        raise ProtocolError(
            f"Chunk index ({frame.cidx}) must be strictly less than chunk count ({frame.ccnt})",
            code="E_PROTO",
            details={"cidx": frame.cidx, "ccnt": frame.ccnt},
        )

    # 4. Validate payload
    payload = frame.payload
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    elif isinstance(payload, (bytearray, memoryview)):
        payload = bytes(payload)

    plen = len(payload)
    if plen > 0x3FFF:
        raise ProtocolError(
            f"Payload length {plen} exceeds 14-bit limit",
            code="E_TOOBIG",
            details={"len": plen},
        )

    if frame.payload_len != 0 and frame.payload_len != plen:
        raise ProtocolError(
            f"Specified payload_len ({frame.payload_len}) does not match payload size ({plen})",
            code="E_PROTO",
            details={"payload_len": frame.payload_len, "actual_len": plen},
        )

    for idx, b in enumerate(payload):
        if b >= 0x80:
            raise ProtocolError(
                f"Non-7-bit byte in payload at offset {idx}: 0x{b:02X} >= 0x80",
                code="E_PROTO",
                details={"offset": idx, "byte": b},
            )

    total_len = FRAME_OVERHEAD + plen
    if max_frame_size is not None and total_len > max_frame_size:
        raise ProtocolError(
            f"Total frame length {total_len} exceeds maximum allowed size {max_frame_size}",
            code="E_TOOBIG",
            details={"frame_len": total_len, "max_frame_size": max_frame_size},
        )

    # 5. Build raw frame buffer
    buf = bytearray()
    buf.append(SYSEX_START)
    buf.append(MANUFACTURER_ID)
    buf.extend(MAGIC)
    buf.append(PROTOCOL_VERSION)
    buf.append(kind_int)
    buf.append(frame.flags)
    buf.extend(pack_septets_14(frame.sid))
    buf.extend(pack_septets_21(frame.mid))
    buf.extend(pack_septets_14(frame.cidx))
    buf.extend(pack_septets_14(frame.ccnt))
    buf.extend(pack_septets_14(plen))
    buf.extend(payload)

    # 6. Checksum from VER (index 4) through end of payload
    crc = crc16(buf[4:])
    buf.extend(pack_crc(crc))
    buf.append(SYSEX_END)

    frame.crc = crc
    frame.payload_len = plen
    return bytes(buf)


def decode_frame(raw: bytes, *, max_frame_size: int | None = None) -> Frame:
    """Decode raw SysEx bytes into a Frame dataclass.

    Validates header magic, framing delimiters, 7-bit cleanliness,
    chunk constraints, and CRC checksum.

    Raises:
        ProtocolError: If frame is truncated, corrupted, non-7-bit clean, or CRC fails.
    """
    raw_len = len(raw)

    # 1. Minimum length check
    if raw_len < FRAME_OVERHEAD:
        raise ProtocolError(
            f"Truncated SysEx frame: length {raw_len} < minimum {FRAME_OVERHEAD} bytes",
            code="E_PROTO",
            details={"len": raw_len, "min_len": FRAME_OVERHEAD},
        )

    # 2. Maximum length check (optional limit)
    if max_frame_size is not None and raw_len > max_frame_size:
        raise ProtocolError(
            f"Frame size {raw_len} exceeds limit of {max_frame_size} bytes",
            code="E_TOOBIG",
            details={"len": raw_len, "limit": max_frame_size},
        )

    # 3. Delimiter checks
    if raw[0] != SYSEX_START:
        raise ProtocolError(
            f"Invalid SysEx start byte: 0x{raw[0]:02X} (expected 0x{SYSEX_START:02X})",
            code="E_PROTO",
            details={"start": raw[0]},
        )
    if raw[-1] != SYSEX_END:
        raise ProtocolError(
            f"Invalid SysEx end byte: 0x{raw[-1]:02X} (expected 0x{SYSEX_END:02X})",
            code="E_PROTO",
            details={"end": raw[-1]},
        )

    # 4. Validate 7-bit clean constraint on all interior bytes [1 .. -1]
    for idx in range(1, raw_len - 1):
        b = raw[idx]
        if b >= 0x80:
            raise ProtocolError(
                f"Interior byte at offset {idx} is not 7-bit clean: 0x{b:02X} >= 0x80",
                code="E_PROTO",
                details={"offset": idx, "byte": b},
            )

    # 5. Manufacturer ID & Magic checks
    if raw[1] != MANUFACTURER_ID:
        raise ProtocolError(
            f"Invalid manufacturer ID: 0x{raw[1]:02X} (expected 0x{MANUFACTURER_ID:02X})",
            code="E_PROTO",
            details={"mfg_id": raw[1]},
        )
    if raw[2:4] != MAGIC:
        raise ProtocolError(
            f"Invalid magic bytes: {bytes(raw[2:4])!r} (expected {MAGIC!r})",
            code="E_PROTO",
            details={"magic": bytes(raw[2:4]).hex()},
        )

    # 6. Version check
    if raw[4] != PROTOCOL_VERSION:
        raise ProtocolError(
            f"Unsupported protocol version: 0x{raw[4]:02X} (expected 0x{PROTOCOL_VERSION:02X})",
            code="E_VERSION",
            details={"version": raw[4]},
        )

    # 7. Unpack header fields
    kind = raw[5]
    flags = raw[6]
    sid = unpack_septets_14(raw[7], raw[8])
    mid = unpack_septets_21(raw[9], raw[10], raw[11])
    cidx = unpack_septets_14(raw[12], raw[13])
    ccnt = unpack_septets_14(raw[14], raw[15])
    plen = unpack_septets_14(raw[16], raw[17])

    # 8. Validate chunk and length logic
    if ccnt < 1:
        raise ProtocolError(
            f"Invalid chunk count {ccnt}: must be >= 1",
            code="E_PROTO",
            details={"ccnt": ccnt},
        )
    if cidx >= ccnt:
        raise ProtocolError(
            f"Chunk index {cidx} out of range for chunk count {ccnt}",
            code="E_PROTO",
            details={"cidx": cidx, "ccnt": ccnt},
        )

    expected_len = FRAME_OVERHEAD + plen
    if raw_len != expected_len:
        raise ProtocolError(
            f"Frame length mismatch: header specifies PLEN={plen} "
            f"(expected {expected_len} bytes), got {raw_len} bytes",
            code="E_PROTO",
            details={"expected_len": expected_len, "actual_len": raw_len, "plen": plen},
        )

    # 9. Extract payload and CRC
    payload = bytes(raw[18 : 18 + plen])
    crc_offset = 18 + plen
    try:
        received_crc = unpack_crc(raw[crc_offset : crc_offset + 3])
    except ValueError as e:
        raise ProtocolError(f"Malformed CRC septets in frame: {e}", code="E_PROTO") from e

    # 10. Check CRC integrity over [VER ... last payload byte]
    crc_data = raw[4:crc_offset]
    computed_crc = crc16(crc_data)
    if computed_crc != received_crc:
        raise ProtocolError(
            f"CRC mismatch (E_CRC): computed 0x{computed_crc:04X} != received 0x{received_crc:04X}",
            code="E_PROTO",
            details={"computed_crc": computed_crc, "received_crc": received_crc},
        )

    return Frame(
        kind=kind,
        flags=flags,
        sid=sid,
        mid=mid,
        cidx=cidx,
        ccnt=ccnt,
        payload_len=plen,
        payload=payload,
        crc=received_crc,
    )


def try_decode_frame(raw: bytes, *, max_frame_size: int | None = None) -> Frame | None:
    """Attempt to decode a SysEx frame, returning None if frame is malformed.

    Per [WIRE-07], devices and robust receivers silently drop corrupted frames.
    """
    try:
        return decode_frame(raw, max_frame_size=max_frame_size)
    except ProtocolError:
        return None
