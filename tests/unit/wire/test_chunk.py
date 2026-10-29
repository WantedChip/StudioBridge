"""Unit and property-based tests for payload chunking and multi-chunk reassembly.

Tests 1,000 Hypothesis runs covering arbitrary payloads up to 96 KiB, random chunk sizes,
out-of-order delivery, duplicate chunks, and boundary edge cases.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.chunk import (
    DEFAULT_MAX_PAYLOAD,
    MAX_DEVICE_INBOUND,
    Reassembler,
    chunk_payload,
)
from studiobridge.wire.frame import Frame, FrameKind


class TestChunkPayload:
    """Test chunk_payload function boundaries and edge cases."""

    def test_empty_payload(self) -> None:
        """Empty payload produces one empty chunk [b""] so CCNT >= 1."""
        chunks = chunk_payload(b"")
        assert chunks == [b""]
        assert len(chunks) == 1

    def test_single_byte_payload(self) -> None:
        """Single-byte payload produces a single chunk."""
        chunks = chunk_payload(b"A")
        assert chunks == [b"A"]

    def test_exact_chunk_boundary(self) -> None:
        """Payload matching max_payload exactly produces a single chunk."""
        data = b"X" * DEFAULT_MAX_PAYLOAD
        chunks = chunk_payload(data, max_payload=DEFAULT_MAX_PAYLOAD)
        assert len(chunks) == 1
        assert chunks[0] == data

    def test_chunk_boundary_plus_one(self) -> None:
        """Payload matching max_payload + 1 produces 2 chunks."""
        data = b"Y" * (DEFAULT_MAX_PAYLOAD + 1)
        chunks = chunk_payload(data, max_payload=DEFAULT_MAX_PAYLOAD)
        assert len(chunks) == 2
        assert len(chunks[0]) == DEFAULT_MAX_PAYLOAD
        assert len(chunks[1]) == 1
        assert b"".join(chunks) == data

    def test_max_device_inbound_boundary(self) -> None:
        """Payload of exactly 96 KiB (98,304 bytes) is accepted."""
        data = b"Z" * MAX_DEVICE_INBOUND
        chunks = chunk_payload(data, max_payload=DEFAULT_MAX_PAYLOAD)
        assert b"".join(chunks) == data

    def test_exceeding_max_device_inbound_raises_toobig(self) -> None:
        """Payload of 96 KiB + 1 byte raises ProtocolError with E_TOOBIG."""
        data = b"Z" * (MAX_DEVICE_INBOUND + 1)
        with pytest.raises(ProtocolError) as exc_info:
            chunk_payload(data)
        assert exc_info.value.code == "E_TOOBIG"

    def test_invalid_max_payload_raises_value_error(self) -> None:
        """max_payload <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            chunk_payload(b"test", max_payload=0)
        with pytest.raises(ValueError, match="positive"):
            chunk_payload(b"test", max_payload=-10)


class TestReassemblerDirect:
    """Direct tests for Reassembler functionality, sliding window, and timeouts."""

    def test_single_chunk_reassembly(self) -> None:
        """Single-chunk message completes immediately."""
        reassembler = Reassembler()
        result = reassembler.add_chunk(
            kind=FrameKind.REQ,
            sid=1,
            mid=100,
            cidx=0,
            ccnt=1,
            payload=b'{"op":"ping"}',
        )
        assert result == b'{"op":"ping"}'
        assert reassembler.active_count == 0

    def test_in_order_multi_chunk_reassembly(self) -> None:
        """Multi-chunk message in sequential order reassembles correctly."""
        reassembler = Reassembler()
        payload = b"Hello world! This is a test."
        chunks = [payload[:10], payload[10:20], payload[20:]]

        assert reassembler.add_chunk(FrameKind.RES, 42, 1, 0, 3, chunks[0]) is None
        assert reassembler.active_count == 1
        assert reassembler.add_chunk(FrameKind.RES, 42, 1, 1, 3, chunks[1]) is None
        assert reassembler.active_count == 1
        result = reassembler.add_chunk(FrameKind.RES, 42, 1, 2, 3, chunks[2])
        assert result == payload
        assert reassembler.active_count == 0

    def test_reverse_order_multi_chunk_reassembly(self) -> None:
        """Multi-chunk message in reverse order reassembles correctly."""
        reassembler = Reassembler()
        payload = b"Reverse order chunks test payload."
        chunks = [payload[:10], payload[10:20], payload[20:]]

        assert reassembler.add_chunk(FrameKind.RES, 42, 2, 2, 3, chunks[2]) is None
        assert reassembler.add_chunk(FrameKind.RES, 42, 2, 1, 3, chunks[1]) is None
        result = reassembler.add_chunk(FrameKind.RES, 42, 2, 0, 3, chunks[0])
        assert result == payload
        assert reassembler.active_count == 0

    def test_duplicate_chunks_are_ignored(self) -> None:
        """Duplicate chunks do not corrupt state or cause errors."""
        reassembler = Reassembler()
        payload = b"Duplicate chunk test."
        chunk0 = payload[:10]
        chunk1 = payload[10:]

        assert reassembler.add_chunk(FrameKind.EVT, 1, 5, 0, 2, chunk0) is None
        # Send duplicate of chunk 0
        assert reassembler.add_chunk(FrameKind.EVT, 1, 5, 0, 2, chunk0) is None
        # Now send chunk 1
        result = reassembler.add_chunk(FrameKind.EVT, 1, 5, 1, 2, chunk1)
        assert result == payload

    def test_feed_frame_method(self) -> None:
        """Feed method correctly unpacks Frame instances."""
        reassembler = Reassembler()
        f0 = Frame(kind=FrameKind.REQ, flags=0, sid=10, mid=20, cidx=0, ccnt=2, payload=b"Part 1")
        f1 = Frame(kind=FrameKind.REQ, flags=0, sid=10, mid=20, cidx=1, ccnt=2, payload=b"Part 2")

        assert reassembler.feed(f0) is None
        res = reassembler.feed(f1)
        assert res == b"Part 1Part 2"

    def test_sliding_window_enforcement(self) -> None:
        """With window_size=8, chunks >= 8 ahead of lowest missing are dropped."""
        reassembler = Reassembler(window_size=8)
        # Message has 20 chunks
        # Chunk 0 is missing. Chunk 7 (diff 7) should be accepted.
        assert reassembler.add_chunk(FrameKind.REQ, 1, 1, 7, 20, b"c7") is None
        # Chunk 8 (diff 8 >= window) should be dropped
        assert reassembler.add_chunk(FrameKind.REQ, 1, 1, 8, 20, b"c8") is None
        missing = reassembler.get_missing(FrameKind.REQ, 1, 1)
        assert 8 in missing  # Chunk 8 was dropped!

    def test_two_stage_timeout_expiry(self) -> None:
        """Incomplete buffer emits NACK on 1st expiry, discards on 2nd per [WIRE-12]."""
        reassembler = Reassembler(timeout_ms=2000.0)
        reassembler.add_chunk(FrameKind.REQ, 1, 10, 0, 3, b"chunk0", now_ms=1000.0)

        # Before timeout (t = 2500 ms, elapsed = 1500 ms < 2000 ms)
        expiries = reassembler.check_timeouts(now_ms=2500.0)
        assert len(expiries) == 0
        assert reassembler.active_count == 1

        # First expiry at t = 3500 ms (elapsed = 2500 ms >= 2000 ms)
        expiries = reassembler.check_timeouts(now_ms=3500.0)
        assert len(expiries) == 1
        assert expiries[0].action == "nack"
        assert expiries[0].key == (FrameKind.REQ, 1, 10)
        assert expiries[0].missing == [1, 2]
        assert reassembler.active_count == 1  # Still retained!

        # Second expiry at t = 6000 ms (elapsed = 2500 ms >= 2000 ms)
        expiries2 = reassembler.check_timeouts(now_ms=6000.0)
        assert len(expiries2) == 1
        assert expiries2[0].action == "discard"
        assert expiries2[0].key == (FrameKind.REQ, 1, 10)
        assert reassembler.active_count == 0  # Purged on second expiry!

    def test_cancel_and_clear(self) -> None:
        """Cancel and clear methods purge active buffers."""
        reassembler = Reassembler()
        reassembler.add_chunk(FrameKind.REQ, 1, 1, 0, 3, b"A")
        reassembler.add_chunk(FrameKind.REQ, 1, 2, 0, 3, b"B")
        assert reassembler.active_count == 2

        assert reassembler.cancel(FrameKind.REQ, 1, 1) is True
        assert reassembler.cancel(FrameKind.REQ, 1, 1) is False
        assert reassembler.active_count == 1

        reassembler.clear()
        assert reassembler.active_count == 0

    def test_invalid_chunk_indices_raise_error(self) -> None:
        """Invalid chunk indices or ccnt raise ProtocolError with E_PROTO."""
        reassembler = Reassembler()
        with pytest.raises(ProtocolError) as exc_info:
            reassembler.add_chunk(FrameKind.REQ, 1, 1, 0, 0, b"")
        assert exc_info.value.code == "E_PROTO"

        with pytest.raises(ProtocolError) as exc_info2:
            reassembler.add_chunk(FrameKind.REQ, 1, 1, 5, 5, b"")
        assert exc_info2.value.code == "E_PROTO"

        with pytest.raises(ProtocolError) as exc_info3:
            reassembler.add_chunk(FrameKind.REQ, 1, 1, -1, 5, b"")
        assert exc_info3.value.code == "E_PROTO"

    def test_mismatched_ccnt_raises_error(self) -> None:
        """Chunks with conflicting ccnt for same (kind, sid, mid) raise E_PROTO."""
        reassembler = Reassembler()
        reassembler.add_chunk(FrameKind.REQ, 1, 1, 0, 3, b"part0")
        with pytest.raises(ProtocolError) as exc_info:
            reassembler.add_chunk(FrameKind.REQ, 1, 1, 1, 4, b"part1")
        assert exc_info.value.code == "E_PROTO"

    def test_exceeding_max_message_size_raises_toobig(self) -> None:
        """Accumulated chunks exceeding max_message_size raise E_TOOBIG and purge buffer."""
        reassembler = Reassembler(max_message_size=100)
        reassembler.add_chunk(FrameKind.REQ, 1, 1, 0, 3, b"X" * 60)
        with pytest.raises(ProtocolError) as exc_info:
            reassembler.add_chunk(FrameKind.REQ, 1, 1, 1, 3, b"Y" * 60)
        assert exc_info.value.code == "E_TOOBIG"
        assert reassembler.active_count == 0


class TestHypothesisReassembly:
    """Hypothesis property-based tests (1,000 runs) for chunking and reassembly.

    Verifies arbitrary payload bytes up to 96 KiB reassemble identically under
    packet reordering and deduplication.
    """

    @settings(max_examples=1000, deadline=None)
    @given(
        payload=st.binary(min_size=0, max_size=MAX_DEVICE_INBOUND),
        max_payload=st.integers(min_value=10, max_value=DEFAULT_MAX_PAYLOAD),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
    )
    def test_chunking_and_out_of_order_reassembly_property(
        self,
        payload: bytes,
        max_payload: int,
        seed: int,
    ) -> None:
        """Verify arbitrary payloads reassemble identically under shuffling and duplicates."""
        chunks = chunk_payload(payload, max_payload=max_payload)
        ccnt = len(chunks)

        # Build list of chunk tuples: (cidx, payload_bytes)
        chunk_items = [(i, chunks[i]) for i in range(ccnt)]

        # Use deterministic RNG seeded by Hypothesis
        rng = random.Random(seed)

        # Introduce duplicate chunks (up to 3 duplicates chosen randomly)
        if ccnt > 1:
            num_duplicates = rng.randint(0, min(3, ccnt))
            for _ in range(num_duplicates):
                dup_idx = rng.randint(0, ccnt - 1)
                chunk_items.append((dup_idx, chunks[dup_idx]))

        # Shuffle delivery order
        rng.shuffle(chunk_items)

        # Feed all chunks to reassembler
        reassembler = Reassembler(max_message_size=MAX_DEVICE_INBOUND)
        result: bytes | None = None

        kind = FrameKind.RES
        sid = 123
        mid = 456

        for cidx, chunk_bytes in chunk_items:
            res = reassembler.add_chunk(
                kind=kind,
                sid=sid,
                mid=mid,
                cidx=cidx,
                ccnt=ccnt,
                payload=chunk_bytes,
            )
            if res is not None:
                result = res

        # Must have completed and matched byte-for-byte
        assert result is not None
        assert result == payload
        assert reassembler.active_count == 0
