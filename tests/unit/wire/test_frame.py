"""Unit tests for SysEx Frame codec, golden test vectors, and error validation.

Validates golden vector conformity, serialization round-trips, strict 7-bit cleanliness,
and rejection of malformed frames.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.frame import (
    FRAME_OVERHEAD,
    HEADER_LEN,
    MAGIC,
    MANUFACTURER_ID,
    PROTOCOL_VERSION,
    SYSEX_END,
    SYSEX_START,
    Frame,
    FrameFlags,
    FrameKind,
    decode_frame,
    encode_frame,
    try_decode_frame,
)

# Path to golden test vectors JSON
VECTORS_PATH = Path(__file__).resolve().parents[2] / "wire" / "vectors.json"


@pytest.fixture(scope="module")
def golden_vectors() -> list[dict]:
    """Load golden test vectors from tests/wire/vectors.json."""
    assert VECTORS_PATH.exists(), f"Missing vectors file at {VECTORS_PATH}"
    with open(VECTORS_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestGoldenVectors:
    """Validate conformity with the official golden test vectors."""

    def test_framing_constants(self) -> None:
        """Verify protocol wire constants."""
        assert SYSEX_START == 0xF0
        assert SYSEX_END == 0xF7
        assert MANUFACTURER_ID == 0x7D
        assert MAGIC == b"SB"
        assert PROTOCOL_VERSION == 0x01
        assert HEADER_LEN == 18
        assert FRAME_OVERHEAD == 22

    def test_vector_1_ping_request(self, golden_vectors: list[dict]) -> None:
        """Vector 1: REQ, session 0, MID 1, single chunk, payload {"op":"ping"} (35 bytes)."""
        v1 = next(v for v in golden_vectors if v["name"] == "vector_1")
        raw_bytes = bytes.fromhex(v1["hex"])
        assert len(raw_bytes) == 35

        # 1. Decode raw bytes
        frame = decode_frame(raw_bytes)
        assert frame.kind == FrameKind.REQ
        assert frame.kind == 1
        assert frame.is_req is True
        assert frame.flags == 0
        assert frame.sid == 0
        assert frame.mid == 1
        assert frame.cidx == 0
        assert frame.ccnt == 1
        assert frame.payload_len == 13
        assert frame.payload == b'{"op":"ping"}'
        assert frame.crc == 0x2017

        # 2. Re-encode decoded frame and verify byte-for-byte identity
        encoded = encode_frame(frame)
        assert encoded == raw_bytes

        # 3. Construct new Frame and encode from scratch
        new_frame = Frame(
            kind=FrameKind.REQ,
            flags=0,
            sid=0,
            mid=1,
            cidx=0,
            ccnt=1,
            payload=b'{"op":"ping"}',
        )
        new_encoded = new_frame.encode()
        assert new_encoded == raw_bytes
        assert new_frame.crc == 0x2017
        assert new_frame.payload_len == 13

    def test_vector_2_chunked_response(self, golden_vectors: list[dict]) -> None:
        """Vector 2: RES, session 0x1234, MID 5, chunk 0 of 2 (63 bytes)."""
        v2 = next(v for v in golden_vectors if v["name"] == "vector_2")
        raw_bytes = bytes.fromhex(v2["hex"])
        assert len(raw_bytes) == 63

        # 1. Decode raw bytes
        frame = decode_frame(raw_bytes)
        assert frame.kind == FrameKind.RES
        assert frame.kind == 2
        assert frame.is_res is True
        assert frame.flags == 0
        assert frame.sid == 0x1234
        assert frame.mid == 5
        assert frame.cidx == 0
        assert frame.ccnt == 2
        assert frame.payload_len == 41
        assert frame.payload == b'{"ok":true,"r":{"device":{"build":"0.1.0"'
        assert frame.crc == 0xA837

        # 2. Re-encode decoded frame and verify byte-for-byte identity
        encoded = encode_frame(frame)
        assert encoded == raw_bytes

        # 3. Construct new Frame and encode from scratch
        new_frame = Frame(
            kind=FrameKind.RES,
            flags=0,
            sid=0x1234,
            mid=5,
            cidx=0,
            ccnt=2,
            payload=b'{"ok":true,"r":{"device":{"build":"0.1.0"',
        )
        new_encoded = new_frame.encode()
        assert new_encoded == raw_bytes
        assert new_frame.crc == 0xA837
        assert new_frame.payload_len == 41


class TestFrameEncodingValidation:
    """Test parameter validation and constraints during frame encoding."""

    def test_encode_empty_payload_frame(self) -> None:
        """An empty payload frame has exactly 22 bytes overhead."""
        frame = Frame(kind=FrameKind.CTL, mid=42, ccnt=1, payload=b"")
        encoded = encode_frame(frame)
        assert len(encoded) == FRAME_OVERHEAD
        decoded = decode_frame(encoded)
        assert decoded.payload == b""
        assert decoded.payload_len == 0
        assert decoded.mid == 42
        assert decoded.is_ctl is True

    def test_encode_bytearray_and_memoryview_payload(self) -> None:
        """Bytearray and memoryview payloads are normalized to bytes."""
        frame1 = Frame(kind=FrameKind.REQ, payload=bytearray(b"ping"))
        assert isinstance(frame1.payload, bytes)
        assert frame1.payload == b"ping"

        frame2 = Frame(kind=FrameKind.REQ, payload=memoryview(b"pong"))
        assert isinstance(frame2.payload, bytes)
        assert frame2.payload == b"pong"

    def test_encode_payload_exceeding_14bit_limit(self) -> None:
        """Payload exceeding 14 bits (16383 bytes) raises ProtocolError with E_TOOBIG."""
        frame = Frame(kind=FrameKind.REQ, payload=b"X" * 16384)
        with pytest.raises(ProtocolError) as exc_info:
            encode_frame(frame)
        assert exc_info.value.code == "E_TOOBIG"

    def test_encode_non_7bit_payload_rejected(self) -> None:
        """Payload containing non-7-bit bytes (>= 0x80) must raise ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, payload=b"invalid \x80 byte")
        with pytest.raises(ProtocolError, match="Non-7-bit byte in payload"):
            encode_frame(frame)

    def test_encode_kind_out_of_range(self) -> None:
        """Frame kind out of 7-bit range must raise ProtocolError."""
        frame = Frame(kind=128, payload=b"test")
        with pytest.raises(ProtocolError, match="Frame kind"):
            encode_frame(frame)

    def test_encode_flags_out_of_range(self) -> None:
        """Flags out of 7-bit range must raise ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, flags=128, payload=b"test")
        with pytest.raises(ProtocolError, match="Frame flags"):
            encode_frame(frame)

    def test_encode_sid_out_of_range(self) -> None:
        """SID exceeding 14 bits (16383) must raise ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, sid=16384, payload=b"test")
        with pytest.raises(ProtocolError, match="Session ID"):
            encode_frame(frame)

    def test_encode_mid_out_of_range(self) -> None:
        """MID exceeding 21 bits (2097151) must raise ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, mid=2097152, payload=b"test")
        with pytest.raises(ProtocolError, match="Message ID"):
            encode_frame(frame)

    def test_encode_cidx_out_of_range(self) -> None:
        """CIDX exceeding 14 bits (16383) must raise ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, cidx=16384, ccnt=20000, payload=b"test")
        with pytest.raises(ProtocolError, match="Chunk index"):
            encode_frame(frame)

    def test_encode_ccnt_zero_or_out_of_range(self) -> None:
        """CCNT must be between 1 and 16383."""
        with pytest.raises(ProtocolError, match="Chunk count"):
            encode_frame(Frame(kind=FrameKind.REQ, ccnt=0, payload=b"test"))
        with pytest.raises(ProtocolError, match="Chunk count"):
            encode_frame(Frame(kind=FrameKind.REQ, ccnt=16384, payload=b"test"))

    def test_encode_cidx_greater_or_equal_ccnt(self) -> None:
        """CIDX >= CCNT must raise ProtocolError."""
        with pytest.raises(ProtocolError, match="Chunk index .* less than chunk count"):
            encode_frame(Frame(kind=FrameKind.REQ, cidx=1, ccnt=1, payload=b"test"))
        with pytest.raises(ProtocolError, match="Chunk index .* less than chunk count"):
            encode_frame(Frame(kind=FrameKind.REQ, cidx=5, ccnt=3, payload=b"test"))

    def test_encode_mismatched_payload_len(self) -> None:
        """Explicitly specifying payload_len different from actual payload raises ProtocolError."""
        frame = Frame(kind=FrameKind.REQ, payload=b"hello", payload_len=10)
        with pytest.raises(ProtocolError, match="payload_len"):
            encode_frame(frame)

    def test_encode_max_frame_size_enforcement(self) -> None:
        """Encoding frame exceeding max_frame_size raises E_TOOBIG."""
        frame = Frame(kind=FrameKind.REQ, payload=b"A" * 100)
        # Overhead is 22, so total frame is 122 bytes
        with pytest.raises(ProtocolError) as exc_info:
            encode_frame(frame, max_frame_size=100)
        assert exc_info.value.code == "E_TOOBIG"


class TestFrameDecodingValidation:
    """Test rigorous rejection of corrupt, truncated, or malformed frames."""

    @pytest.fixture
    def valid_frame_raw(self) -> bytes:
        """Provide valid encoded frame bytes for tampering tests."""
        frame = Frame(
            kind=FrameKind.REQ,
            flags=0,
            sid=100,
            mid=200,
            cidx=0,
            ccnt=1,
            payload=b'{"op":"test"}',
        )
        return encode_frame(frame)

    def test_decode_truncated_frame(self) -> None:
        """Frames shorter than minimum 22 bytes must be rejected with E_PROTO."""
        truncated_samples = [b"", b"\xf0", b"\xf0\x7dSB", b"\x00" * 21]
        for sample in truncated_samples:
            with pytest.raises(ProtocolError, match="Truncated SysEx frame") as exc_info:
                decode_frame(sample)
            assert exc_info.value.code == "E_PROTO"
            assert try_decode_frame(sample) is None

    def test_decode_invalid_delimiters(self, valid_frame_raw: bytes) -> None:
        """Frames with invalid start (not 0xF0) or end (not 0xF7) must be rejected."""
        # Corrupt start byte
        bad_start = b"\xf1" + valid_frame_raw[1:]
        with pytest.raises(ProtocolError, match="Invalid SysEx start byte"):
            decode_frame(bad_start)
        assert try_decode_frame(bad_start) is None

        # Corrupt end byte
        bad_end = valid_frame_raw[:-1] + b"\xf8"
        with pytest.raises(ProtocolError, match="Invalid SysEx end byte"):
            decode_frame(bad_end)
        assert try_decode_frame(bad_end) is None

    def test_decode_invalid_manufacturer_id(self, valid_frame_raw: bytes) -> None:
        """Frames with manufacturer ID != 0x7D must be rejected."""
        bad_mfg = valid_frame_raw[:1] + b"\x7e" + valid_frame_raw[2:]
        with pytest.raises(ProtocolError, match="Invalid manufacturer ID"):
            decode_frame(bad_mfg)
        assert try_decode_frame(bad_mfg) is None

    def test_decode_invalid_magic_bytes(self, valid_frame_raw: bytes) -> None:
        """Frames with magic != 'SB' must be rejected."""
        bad_magic = valid_frame_raw[:2] + b"FL" + valid_frame_raw[4:]
        with pytest.raises(ProtocolError, match="Invalid magic bytes"):
            decode_frame(bad_magic)
        assert try_decode_frame(bad_magic) is None

    def test_decode_unsupported_version(self, valid_frame_raw: bytes) -> None:
        """Frames with version != 1 must raise ProtocolError with code E_VERSION."""
        bad_ver = valid_frame_raw[:4] + b"\x02" + valid_frame_raw[5:]
        with pytest.raises(ProtocolError, match="Unsupported protocol version") as exc_info:
            decode_frame(bad_ver)
        assert exc_info.value.code == "E_VERSION"
        assert try_decode_frame(bad_ver) is None

    def test_decode_non_7bit_clean_interior_bytes(self, valid_frame_raw: bytes) -> None:
        """Any interior byte with high bit set (>= 0x80) must be rejected."""
        for offset in [1, 2, 4, 5, 6, 7, 10, 15, 18]:
            if offset < len(valid_frame_raw) - 1:
                corrupted = bytearray(valid_frame_raw)
                corrupted[offset] = corrupted[offset] | 0x80
                with pytest.raises(ProtocolError, match="not 7-bit clean"):
                    decode_frame(bytes(corrupted))
                assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_ccnt_zero(self, valid_frame_raw: bytes) -> None:
        """CCNT encoded as 0 must raise ProtocolError."""
        corrupted = bytearray(valid_frame_raw)
        corrupted[14] = 0  # CCNT high septet
        corrupted[15] = 0  # CCNT low septet
        with pytest.raises(ProtocolError, match="Invalid chunk count"):
            decode_frame(bytes(corrupted))
        assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_cidx_out_of_range(self, valid_frame_raw: bytes) -> None:
        """CIDX >= CCNT must raise ProtocolError."""
        corrupted = bytearray(valid_frame_raw)
        corrupted[12] = 0  # CIDX high septet
        corrupted[13] = 5  # CIDX low septet = 5, CCNT is 1
        with pytest.raises(ProtocolError, match="Chunk index .* out of range"):
            decode_frame(bytes(corrupted))
        assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_frame_length_mismatch(self, valid_frame_raw: bytes) -> None:
        """PLEN in header not matching actual byte length must be rejected."""
        # Truncate by dropping one payload byte without altering PLEN
        short_raw = valid_frame_raw[:18] + valid_frame_raw[19:]
        with pytest.raises(ProtocolError, match="Frame length mismatch"):
            decode_frame(short_raw)
        assert try_decode_frame(short_raw) is None

    def test_decode_corrupted_payload_crc_failure(self, valid_frame_raw: bytes) -> None:
        """Altered payload byte causing CRC mismatch must raise ProtocolError with E_CRC."""
        corrupted = bytearray(valid_frame_raw)
        corrupted[19] = ord("X") if corrupted[19] != ord("X") else ord("Y")
        with pytest.raises(ProtocolError, match="E_CRC") as exc_info:
            decode_frame(bytes(corrupted))
        assert exc_info.value.code == "E_PROTO"
        assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_corrupted_crc_bytes(self, valid_frame_raw: bytes) -> None:
        """Tampered CRC bytes must trigger CRC mismatch."""
        corrupted = bytearray(valid_frame_raw)
        # Flip low CRC septet
        corrupted[-2] = (corrupted[-2] ^ 0x01) & 0x7F
        with pytest.raises(ProtocolError, match="E_CRC") as exc_info:
            decode_frame(bytes(corrupted))
        assert exc_info.value.code == "E_PROTO"
        assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_malformed_crc_septets(self, valid_frame_raw: bytes) -> None:
        """CRC byte b0 > 0x03 violates 2-bit limit and raises ProtocolError."""
        corrupted = bytearray(valid_frame_raw)
        corrupted[-4] = 0x04  # 0x04 < 0x80 passes 7-bit clean check, but violates b0 <= 0x03
        with pytest.raises(ProtocolError, match="Malformed CRC septets") as exc_info:
            decode_frame(bytes(corrupted))
        assert exc_info.value.code == "E_PROTO"
        assert try_decode_frame(bytes(corrupted)) is None

    def test_decode_max_frame_size_exceeded(self, valid_frame_raw: bytes) -> None:
        """Exceeding max_frame_size limit raises E_TOOBIG."""
        with pytest.raises(ProtocolError, match="exceeds limit") as exc_info:
            decode_frame(valid_frame_raw, max_frame_size=25)
        assert exc_info.value.code == "E_TOOBIG"
        assert try_decode_frame(valid_frame_raw, max_frame_size=25) is None


class TestFrameRoundTripAndProperties:
    """Test round-trip encoding/decoding and helper properties."""

    @pytest.mark.parametrize(
        ("kind", "expected_req", "expected_res", "expected_evt", "expected_ctl"),
        [
            (FrameKind.REQ, True, False, False, False),
            (FrameKind.RES, False, True, False, False),
            (FrameKind.EVT, False, False, True, False),
            (FrameKind.CTL, False, False, False, True),
        ],
    )
    def test_frame_kind_predicates(
        self,
        kind: FrameKind,
        expected_req: bool,
        expected_res: bool,
        expected_evt: bool,
        expected_ctl: bool,
    ) -> None:
        """Verify is_req, is_res, is_evt, is_ctl property methods."""
        frame = Frame(kind=kind)
        assert frame.is_req is expected_req
        assert frame.is_res is expected_res
        assert frame.is_evt is expected_evt
        assert frame.is_ctl is expected_ctl

    def test_frame_flags_enc_json(self) -> None:
        """Verify FrameFlags.ENC_JSON bitmask is preserved across serialization."""
        frame = Frame(
            kind=FrameKind.REQ,
            flags=FrameFlags.ENC_JSON,
            payload=b'{"key":"val"}',
        )
        encoded = frame.encode()
        decoded = Frame.decode(encoded)
        assert decoded.flags == FrameFlags.ENC_JSON
        assert decoded.flags & FrameFlags.ENC_JSON

    @pytest.mark.parametrize(
        "payload",
        [
            b"",
            b"x",
            b'{"op":"ping"}',
            b'{"numbers":[1,2,3,4,5],"text":"clean ascii string"}',
            bytes(range(1, 128)),  # All valid 7-bit values (excluding null)
        ],
    )
    def test_arbitrary_payload_roundtrip(self, payload: bytes) -> None:
        """Verify round-trip integrity for arbitrary 7-bit payloads."""
        frame = Frame(
            kind=FrameKind.EVT,
            flags=0,
            sid=1234,
            mid=98765,
            cidx=3,
            ccnt=10,
            payload=payload,
        )
        encoded = frame.encode()
        decoded = Frame.decode(encoded)
        assert decoded.kind == frame.kind
        assert decoded.flags == frame.flags
        assert decoded.sid == frame.sid
        assert decoded.mid == frame.mid
        assert decoded.cidx == frame.cidx
        assert decoded.ccnt == frame.ccnt
        assert decoded.payload == payload
        assert decoded.payload_len == len(payload)
        assert decoded.crc == frame.crc
