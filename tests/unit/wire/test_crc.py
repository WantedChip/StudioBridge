"""Unit tests for CRC-16/CCITT-FALSE and 7-bit septet packing routines.

Validates check value 0x29B1, reference vs table equivalence, packing roundtrips,
and edge case exception handling.
"""

from __future__ import annotations

import os

import pytest

from studiobridge.wire.crc import (
    CRC_CHECK_INPUT,
    CRC_CHECK_VALUE,
    CRC_INIT,
    CRC_POLY,
    crc16,
    crc16_bitwise,
    pack_crc,
    pack_septets_14,
    pack_septets_21,
    unpack_crc,
    unpack_septets_14,
    unpack_septets_21,
)


class TestCrc16Computation:
    """Test CRC-16/CCITT-FALSE computation accuracy and properties."""

    def test_canonical_check_value(self) -> None:
        """Check value for ASCII '123456789' MUST compute to exactly 0x29B1."""
        assert CRC_POLY == 0x1021
        assert crc16_bitwise(CRC_CHECK_INPUT) == CRC_CHECK_VALUE
        assert crc16(CRC_CHECK_INPUT) == CRC_CHECK_VALUE
        assert CRC_CHECK_VALUE == 0x29B1

    def test_empty_buffer(self) -> None:
        """Empty buffer returns initial register state (0xFFFF)."""
        assert crc16_bitwise(b"") == CRC_INIT
        assert crc16(b"") == CRC_INIT

    def test_single_byte_inputs(self) -> None:
        """Verify single byte calculations between bitwise and table implementations."""
        for b in range(256):
            data = bytes([b])
            bitwise = crc16_bitwise(data)
            table = crc16(data)
            assert bitwise == table
            assert 0 <= table <= 0xFFFF

    def test_custom_init_register(self) -> None:
        """Verify custom initial CRC register values propagate correctly."""
        assert crc16_bitwise(b"123456789", init=0x0000) == crc16(b"123456789", init=0x0000)
        assert crc16(b"test", init=0x1234) == crc16_bitwise(b"test", init=0x1234)

    def test_bitwise_and_table_parity_fuzz(self) -> None:
        """Fuzz with randomized buffers to guarantee bitwise and table equivalence."""
        for size in [1, 2, 7, 13, 35, 64, 128, 512, 1024]:
            payload = os.urandom(size)
            assert crc16(payload) == crc16_bitwise(payload)

    def test_bytearray_and_memoryview_support(self) -> None:
        """Verify crc16 works seamlessly with bytearray and memoryview inputs."""
        arr = bytearray(b"123456789")
        mv = memoryview(b"123456789")
        assert crc16(arr) == 0x29B1
        assert crc16(mv) == 0x29B1


class TestCrcSeptetPacking:
    """Test 3-septet packing (2 + 7 + 7 bits) for 16-bit CRC values."""

    def test_pack_crc_canonical_values(self) -> None:
        """Verify packing formula: b0=(crc>>14)&0x03, b1=(crc>>7)&0x7F, b2=crc&0x7F."""
        # 0x2017: (0x2017 >> 14) & 0x03 = 0, (0x2017 >> 7) & 0x7F = 0x40, 0x2017 & 0x7F = 0x17
        packed = pack_crc(0x2017)
        assert packed == bytes([0x00, 0x40, 0x17])
        assert unpack_crc(packed) == 0x2017

        # 0xA837: (0xA837 >> 14) & 0x03 = 2, (0xA837 >> 7) & 0x7F = 0x50, 0xA837 & 0x7F = 0x37
        packed2 = pack_crc(0xA837)
        assert packed2 == bytes([0x02, 0x50, 0x37])
        assert unpack_crc(packed2) == 0xA837

        # 0x29B1
        packed_check = pack_crc(0x29B1)
        assert unpack_crc(packed_check) == 0x29B1

    def test_pack_unpack_boundary_values(self) -> None:
        """Verify boundary 16-bit values (0x0000, 0xFFFF, powers of 2)."""
        boundary_values = [
            0x0000,
            0x0001,
            0x007F,
            0x0080,
            0x3FFF,
            0x4000,
            0x7FFF,
            0x8000,
            0xFFFE,
            0xFFFF,
        ]
        for val in boundary_values:
            packed = pack_crc(val)
            assert len(packed) == 3
            # Check 7-bit cleanliness of packed output
            assert packed[0] <= 0x03
            assert packed[1] <= 0x7F
            assert packed[2] <= 0x7F
            assert unpack_crc(packed) == val

    def test_pack_crc_out_of_range(self) -> None:
        """Negative integers or values > 0xFFFF must raise ValueError."""
        with pytest.raises(ValueError, match="range"):
            pack_crc(-1)
        with pytest.raises(ValueError, match="range"):
            pack_crc(0x10000)

    def test_unpack_crc_invalid_length(self) -> None:
        """Unpacking from buffers shorter than 3 bytes must raise ValueError."""
        with pytest.raises(ValueError, match="at least 3 bytes"):
            unpack_crc(b"")
        with pytest.raises(ValueError, match="at least 3 bytes"):
            unpack_crc(b"\x00\x00")

    def test_unpack_crc_non_7bit_or_b0_overflow(self) -> None:
        """Unpacking bytes violating septet bounds must raise ValueError."""
        # b0 > 0x03 (only 2 bits allowed)
        with pytest.raises(ValueError, match="Invalid CRC septet"):
            unpack_crc(bytes([0x04, 0x00, 0x00]))
        # b1 > 0x7F (not 7-bit clean)
        with pytest.raises(ValueError, match="Invalid CRC septet"):
            unpack_crc(bytes([0x00, 0x80, 0x00]))
        # b2 > 0x7F (not 7-bit clean)
        with pytest.raises(ValueError, match="Invalid CRC septet"):
            unpack_crc(bytes([0x00, 0x00, 0xFF]))


class TestSeptetIntegerPacking:
    """Test general 14-bit and 21-bit septet packing helpers."""

    def test_14bit_septet_roundtrip(self) -> None:
        """Roundtrip test for 14-bit unsigned integers across boundaries."""
        test_values = [0, 1, 127, 128, 8191, 8192, 16382, 16383]
        for val in test_values:
            packed = pack_septets_14(val)
            assert len(packed) == 2
            assert packed[0] <= 0x7F
            assert packed[1] <= 0x7F
            unpacked = unpack_septets_14(packed[0], packed[1])
            assert unpacked == val

    def test_14bit_septet_out_of_range(self) -> None:
        """Values out of 14-bit bounds [0..16383] must raise ValueError."""
        with pytest.raises(ValueError):
            pack_septets_14(-1)
        with pytest.raises(ValueError):
            pack_septets_14(16384)
        with pytest.raises(ValueError):
            unpack_septets_14(0x80, 0x00)
        with pytest.raises(ValueError):
            unpack_septets_14(0x00, 0x80)

    def test_21bit_septet_roundtrip(self) -> None:
        """Roundtrip test for 21-bit unsigned integers across boundaries."""
        test_values = [0, 1, 127, 128, 16383, 16384, 1048575, 1048576, 2097151]
        for val in test_values:
            packed = pack_septets_21(val)
            assert len(packed) == 3
            assert packed[0] <= 0x7F
            assert packed[1] <= 0x7F
            assert packed[2] <= 0x7F
            unpacked = unpack_septets_21(packed[0], packed[1], packed[2])
            assert unpacked == val

    def test_21bit_septet_out_of_range(self) -> None:
        """Values out of 21-bit bounds [0..2097151] must raise ValueError."""
        with pytest.raises(ValueError):
            pack_septets_21(-1)
        with pytest.raises(ValueError):
            pack_septets_21(2097152)
        with pytest.raises(ValueError):
            unpack_septets_21(0x80, 0x00, 0x00)
        with pytest.raises(ValueError):
            unpack_septets_21(0x00, 0x80, 0x00)
        with pytest.raises(ValueError):
            unpack_septets_21(0x00, 0x00, 0x80)
