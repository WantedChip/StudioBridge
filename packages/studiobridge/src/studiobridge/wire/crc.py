"""Pure-Python CRC-16/CCITT-FALSE implementation and 7-bit septet packing routines.

Implements CRC-16/CCITT-FALSE:
- Polynomial: 0x1021 (x^16 + x^12 + x^5 + 1)
- Initial value: 0xFFFF
- RefIn: False
- RefOut: False
- XorOut: 0x0000 (no final XOR)
- Check value for ASCII "123456789": 0x29B1

Packing into 3 MIDI-safe 7-bit septets (2 + 7 + 7 bits):
  b0 = (crc >> 14) & 0x03
  b1 = (crc >> 7) & 0x7F
  b2 = crc & 0x7F

Strictly Python 3.9 compatible with zero external imports.
"""

from __future__ import annotations

from collections.abc import Sequence

# Protocol polynomial and initial register value
CRC_POLY = 0x1021
CRC_INIT = 0xFFFF
CRC_CHECK_INPUT = b"123456789"
CRC_CHECK_VALUE = 0x29B1


def _generate_crc_table() -> tuple[int, ...]:
    """Generate 256-entry lookup table for CCITT-FALSE (poly 0x1021, MSB-first)."""
    table: list[int] = []
    for byte in range(256):
        curr = byte << 8
        for _ in range(8):
            curr = ((curr << 1) ^ CRC_POLY) & 0xFFFF if (curr & 0x8000) else (curr << 1) & 0xFFFF
        table.append(curr)
    return tuple(table)


_TABLE: tuple[int, ...] = _generate_crc_table()

# Type alias for acceptable byte buffers
ByteData = bytes | bytearray | memoryview | Sequence[int]


def crc16_bitwise(data: ByteData, init: int = CRC_INIT) -> int:
    """Compute CRC-16/CCITT-FALSE using the reference bitwise algorithm.

    Matches reference bitwise implementation.
    """
    crc = init & 0xFFFF
    for b in data:
        crc ^= (b & 0xFF) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def crc16(data: ByteData, init: int = CRC_INIT) -> int:
    """Compute CRC-16/CCITT-FALSE over input bytes using table acceleration.

    Produces identical results to crc16_bitwise at significantly higher throughput.
    """
    crc = init & 0xFFFF
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _TABLE[(crc >> 8) ^ (b & 0xFF)]
    return crc & 0xFFFF


def pack_crc(crc: int) -> bytes:
    """Pack a 16-bit integer into 3 7-bit MIDI-safe septets (2 + 7 + 7 bits).

    b0 = (crc >> 14) & 0x03
    b1 = (crc >> 7) & 0x7F
    b2 = crc & 0x7F
    """
    if crc < 0 or crc > 0xFFFF:
        raise ValueError(f"CRC value must be in range 0..0xFFFF (got {crc})")
    b0 = (crc >> 14) & 0x03
    b1 = (crc >> 7) & 0x7F
    b2 = crc & 0x7F
    return bytes([b0, b1, b2])


def unpack_crc(raw: ByteData) -> int:
    """Unpack 3 7-bit septets back into a 16-bit CRC integer.

    Raises ValueError if raw length < 3 or if septet values violate range bounds.
    """
    if len(raw) < 3:
        raise ValueError(f"unpack_crc requires at least 3 bytes (got {len(raw)})")
    b0 = raw[0]
    b1 = raw[1]
    b2 = raw[2]
    if b0 > 0x03 or b1 > 0x7F or b2 > 0x7F:
        raise ValueError(
            f"Invalid CRC septet bytes: [0x{b0:02X}, 0x{b1:02X}, 0x{b2:02X}] "
            "(must be <= [0x03, 0x7F, 0x7F])"
        )
    return ((b0 & 0x03) << 14) | ((b1 & 0x7F) << 7) | (b2 & 0x7F)


def pack_septets_14(val: int) -> bytes:
    """Pack a 14-bit unsigned integer into 2 7-bit septets (big-endian)."""
    if val < 0 or val > 0x3FFF:
        raise ValueError(f"14-bit value out of range 0..0x3FFF (got {val})")
    b0 = (val >> 7) & 0x7F
    b1 = val & 0x7F
    return bytes([b0, b1])


def unpack_septets_14(b0: int, b1: int) -> int:
    """Unpack 2 7-bit septets into a 14-bit unsigned integer (big-endian)."""
    if b0 > 0x7F or b1 > 0x7F or b0 < 0 or b1 < 0:
        raise ValueError(f"Septet bytes out of 7-bit range: [0x{b0:02X}, 0x{b1:02X}]")
    return ((b0 & 0x7F) << 7) | (b1 & 0x7F)


def pack_septets_21(val: int) -> bytes:
    """Pack a 21-bit unsigned integer into 3 7-bit septets (big-endian)."""
    if val < 0 or val > 0x1FFFFF:
        raise ValueError(f"21-bit value out of range 0..0x1FFFFF (got {val})")
    b0 = (val >> 14) & 0x7F
    b1 = (val >> 7) & 0x7F
    b2 = val & 0x7F
    return bytes([b0, b1, b2])


def unpack_septets_21(b0: int, b1: int, b2: int) -> int:
    """Unpack 3 7-bit septets into a 21-bit unsigned integer (big-endian)."""
    if b0 > 0x7F or b1 > 0x7F or b2 > 0x7F or b0 < 0 or b1 < 0 or b2 < 0:
        raise ValueError(f"Septet bytes out of 7-bit range: [0x{b0:02X}, 0x{b1:02X}, 0x{b2:02X}]")
    return ((b0 & 0x7F) << 14) | ((b1 & 0x7F) << 7) | (b2 & 0x7F)
