"""Unit and round-trip tests for binary FLP codec.

Verifies 100% byte-identical roundtrips, non-canonical varint preservation,
trailing byte handling, streaming reader memory bounds, clean-room provenance,
and performance budgets.
"""

from __future__ import annotations

import io
import os
import struct
import time
import tracemalloc
from pathlib import Path

import pytest

from studiobridge.core.errors import (
    FlpInvariantViolationError,
    FlpParseError,
)
from studiobridge.flp.codec import (
    Event,
    EventChunk,
    EventKind,
    FlpFile,
    FlpHeader,
    HeaderChunk,
    LenEnc,
    RawChunk,
    decode_varint,
    encode_varint,
    event_fixed_size,
    event_kind,
    iter_events_from_file,
    parse,
    serialize,
    serialize_events,
)


def _build_synthetic_flp(
    *,
    format_val: int = 0,
    channels: int = 4,
    ppq: int = 96,
    events: list[Event] | None = None,
    extra_header_bytes: bytes = b"",
    trailing_bytes: bytes = b"",
    inter_chunk_padding: bytes = b"",
    extra_chunks: list[tuple[bytes, bytes]] | None = None,
) -> bytes:
    """Helper to assemble a raw binary FLP stream from components."""
    out = io.BytesIO()

    # 1. Header chunk (FLhd)
    header_payload = struct.pack("<HHH", format_val, channels, ppq) + extra_header_bytes
    out.write(b"FLhd")
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)
    if inter_chunk_padding:
        out.write(inter_chunk_padding)

    # 2. Extra chunks if requested
    if extra_chunks:
        for cid, cdata in extra_chunks:
            out.write(cid)
            out.write(struct.pack("<I", len(cdata)))
            out.write(cdata)

    # 3. Data chunk (FLdt)
    if events is not None:
        events_payload = serialize_events(events)
        out.write(b"FLdt")
        out.write(struct.pack("<I", len(events_payload)))
        out.write(events_payload)

    # 4. Trailing bytes
    if trailing_bytes:
        out.write(trailing_bytes)

    return out.getvalue()


# =============================================================================
# Varint Encoding & Decoding Tests ([FLP-01])
# =============================================================================


def test_varint_canonical_roundtrip() -> None:
    """Canonical varints encode and decode correctly across range boundaries."""
    # req: FLP-01
    test_values = [
        0,
        1,
        63,
        127,
        128,
        255,
        16383,
        16384,
        2097151,
        2097152,
        268435455,
    ]
    for val in test_values:
        encoded = encode_varint(val)
        decoded_val, len_enc, next_pos = decode_varint(encoded)
        assert decoded_val == val
        assert len_enc.value == val
        assert len_enc.raw == encoded
        assert next_pos == len(encoded)
        assert len(len_enc) == len(encoded)
        assert bytes(len_enc) == encoded


def test_varint_non_canonical_preservation() -> None:
    """Non-canonical varints with padding bytes are preserved verbatim in LenEnc."""
    # req: FLP-01
    # 5 encoded canonically is b"\x05". Non-canonical 2-byte encoding: b"\x85\x00".
    non_canonical_5 = b"\x85\x00"
    val, len_enc, next_pos = decode_varint(non_canonical_5)
    assert val == 5
    assert len_enc.value == 5
    assert len_enc.raw == non_canonical_5
    assert next_pos == 2

    # 0 encoded non-canonically with 3 bytes: b"\x80\x80\x00"
    non_canonical_0 = b"\x80\x80\x00"
    val0, len_enc0, next_pos0 = decode_varint(non_canonical_0)
    assert val0 == 0
    assert len_enc0.value == 0
    assert len_enc0.raw == non_canonical_0
    assert next_pos0 == 3


def test_varint_error_conditions() -> None:
    """Varint decoding raises structured FlpParseError on truncated or invalid data."""
    # req: FLP-01
    # Empty buffer
    with pytest.raises(FlpParseError) as exc_info:
        decode_varint(b"", offset=0)
    assert exc_info.value.code == "E_FLP_PARSE"
    assert exc_info.value.offset == 0

    # Truncated varint (MSB set on final byte)
    with pytest.raises(FlpParseError) as exc_info:
        decode_varint(b"\x80\x80\x80", offset=0)
    assert exc_info.value.code == "E_FLP_PARSE"
    assert exc_info.value.offset == 0

    # Shift overflow exceeding 35 bits
    overflow_bytes = b"\x80\x80\x80\x80\x80\x80"
    with pytest.raises(FlpParseError) as exc_info:
        decode_varint(overflow_bytes, offset=0)
    assert exc_info.value.code == "E_FLP_PARSE"

    # Negative value to encode_varint raises ValueError
    with pytest.raises(ValueError):
        encode_varint(-1)


# =============================================================================
# Event Classification & Payload Tests ([FLP-01])
# =============================================================================


def test_event_classification_and_properties() -> None:
    """Event kinds and fixed payload sizes conform to FLP specification ranges."""
    # req: FLP-01
    # Byte events (0–63)
    assert event_kind(0) == EventKind.BYTE
    assert event_kind(63) == EventKind.BYTE
    assert event_fixed_size(0) == 1
    assert event_fixed_size(63) == 1

    ev_byte = Event(id=10, raw=b"\x01")
    assert ev_byte.is_byte
    assert not ev_byte.is_word
    assert not ev_byte.is_dword
    assert not ev_byte.is_variable
    assert ev_byte.as_int() == 1

    # Word events (64–127)
    assert event_kind(64) == EventKind.WORD
    assert event_kind(127) == EventKind.WORD
    assert event_fixed_size(64) == 2
    assert event_fixed_size(127) == 2

    ev_word = Event(id=65, raw=b"\x20\x01")
    assert ev_word.is_word
    assert ev_word.as_int() == 0x0120

    # Dword events (128–191)
    assert event_kind(128) == EventKind.DWORD
    assert event_kind(191) == EventKind.DWORD
    assert event_fixed_size(128) == 4
    assert event_fixed_size(191) == 4

    ev_dword = Event(id=130, raw=b"\x78\x56\x34\x12")
    assert ev_dword.is_dword
    assert ev_dword.as_int() == 0x12345678

    # Variable events (192–255)
    assert event_kind(192) == EventKind.VARIABLE
    assert event_kind(255) == EventKind.VARIABLE
    assert event_fixed_size(192) is None
    assert event_fixed_size(255) is None

    ev_var = Event(id=199, raw=b"FL Studio 26.1.0")
    assert ev_var.is_variable
    assert ev_var.as_str() == "FL Studio 26.1.0"

    # Out of range event ID
    with pytest.raises(ValueError):
        event_kind(256)
    with pytest.raises(ValueError):
        event_fixed_size(256)
    with pytest.raises(ValueError):
        Event(id=256, raw=b"")


# =============================================================================
# Header Preservation & Modification Tests ([FLP-05])
# =============================================================================


def test_header_preservation_and_modification() -> None:
    """Header chunk preserves exact verbatim bytes unless modeled fields are modified."""
    # req: FLP-05
    # Standard 6-byte header
    raw_header = struct.pack("<HHH", 0, 8, 192)
    hdr = FlpHeader.from_bytes(raw_header)
    assert hdr.format == 0
    assert hdr.channels == 8
    assert hdr.ppq == 192
    assert not hdr.is_modified()
    assert hdr.to_bytes() == raw_header

    # Non-standard header with 4 extra bytes (10 bytes total)
    raw_header_extra = raw_header + b"\xde\xad\xbe\xef"
    hdr_extra = FlpHeader.from_bytes(raw_header_extra)
    assert not hdr_extra.is_modified()
    assert hdr_extra.to_bytes() == raw_header_extra

    # Modify a field -> is_modified() becomes True, extra bytes preserved
    hdr_extra.ppq = 96
    assert hdr_extra.is_modified()
    repacked = hdr_extra.to_bytes()
    assert repacked == struct.pack("<HHH", 0, 8, 96) + b"\xde\xad\xbe\xef"


def test_header_error_conditions() -> None:
    """Invalid or truncated header payloads raise structured FlpParseError."""
    # req: FLP-02, FLP-05
    # Less than 6 bytes
    with pytest.raises(FlpParseError) as exc_info:
        FlpHeader.from_bytes(b"\x00\x00\x01\x00")
    assert exc_info.value.code == "E_FLP_PARSE"

    # Entire file missing FLhd header
    with pytest.raises(FlpParseError) as exc_info:
        parse(b"TEST\x04\x00\x00\x001234")
    assert exc_info.value.code == "E_FLP_PARSE"

    # File shorter than 8 bytes
    with pytest.raises(FlpParseError) as exc_info:
        parse(b"FLhd\x00")
    assert exc_info.value.code == "E_FLP_PARSE"


# =============================================================================
# Lossless Round-Trip Invariant Tests ([FLP-02], [FLP-03])
# =============================================================================


def test_lossless_roundtrip_synthetic() -> None:
    """Synthetic FLP binary roundtrips with 100% byte identity."""
    # req: FLP-02
    events = [
        Event(id=0, raw=b"\x01"),
        Event(id=64, raw=b"\x34\x12"),
        Event(id=128, raw=b"\x78\x56\x34\x12"),
        # Canonical varint variable event
        Event(id=199, raw=b"StudioBridge Test Project"),
        # Empty variable event (len 0)
        Event(id=200, raw=b""),
        # Non-canonical varint variable event
        Event(
            id=210,
            raw=b"Custom Blob",
            enc=LenEnc(value=11, raw=b"\x8b\x00"),
        ),
    ]

    raw_flp = _build_synthetic_flp(
        format_val=0,
        channels=16,
        ppq=96,
        events=events,
    )

    parsed = parse(raw_flp)
    assert parsed.header.format == 0
    assert parsed.header.channels == 16
    assert parsed.header.ppq == 96
    assert len(parsed.events) == len(events)

    serialized = serialize(parsed)
    assert serialized == raw_flp


def test_unknown_event_ids_preserved() -> None:
    """Unknown event IDs across all 4 payload ranges are preserved verbatim."""
    # req: FLP-03
    events = [
        Event(id=42, raw=b"\xff"),  # Unknown 1-byte event
        Event(id=99, raw=b"\xaa\xbb"),  # Unknown 2-byte event
        Event(id=172, raw=b"\x01\x02\x03\x04"),  # Unknown 4-byte event
        Event(id=250, raw=b"\x10\x20\x30\x40\x50"),  # Unknown variable event
    ]

    raw_flp = _build_synthetic_flp(events=events)
    parsed = parse(raw_flp)
    assert len(parsed.events) == 4
    assert parsed.events[0].id == 42
    assert parsed.events[0].raw == b"\xff"
    assert parsed.events[2].id == 172
    assert parsed.events[3].id == 250
    assert serialize(parsed) == raw_flp


def test_trailing_bytes_after_fldt_preserved() -> None:
    """Arbitrary trailing bytes after the FLdt chunk are preserved verbatim."""
    # req: FLP-03
    trailing = b"\x00\xff\xaa\x55--SIGNATURE-TRAILING-BYTES--"
    events = [Event(id=1, raw=b"\x00")]
    raw_flp = _build_synthetic_flp(events=events, trailing_bytes=trailing)

    parsed = parse(raw_flp)
    assert parsed.trailing_bytes == trailing
    assert serialize(parsed) == raw_flp


def test_inter_chunk_alignment_and_extra_chunks_preserved() -> None:
    """Inter-chunk alignment padding and extra non-standard chunks are preserved."""
    # req: FLP-03
    events = [Event(id=65, raw=b"\x01\x00")]
    extra_chunks = [(b"META", b"Sample metadata chunk payload")]
    padding = b"\x00\x00"

    raw_flp = _build_synthetic_flp(
        events=events,
        inter_chunk_padding=padding,
        extra_chunks=extra_chunks,
    )

    parsed = parse(raw_flp)
    assert len(parsed.chunks) == 3
    assert isinstance(parsed.chunks[0], HeaderChunk)
    assert parsed.chunks[0].padding == padding
    assert isinstance(parsed.chunks[1], RawChunk)
    assert parsed.chunks[1].id == b"META"
    assert parsed.chunks[1].data == b"Sample metadata chunk payload"
    assert isinstance(parsed.chunks[2], EventChunk)

    assert serialize(parsed) == raw_flp


# =============================================================================
# Streaming & Lazy Reader Tests ([FLP-04])
# =============================================================================


def test_streaming_and_lazy_reader(tmp_path: Path) -> None:
    """Large variable payloads are lazily materialized on demand [FLP-04]."""
    # req: FLP-04
    # Create an event with a 128KB payload (exceeding DEFAULT_LAZY_THRESHOLD = 64KB)
    large_payload = b"X" * 131072
    events = [
        Event(id=1, raw=b"\x05"),
        Event(id=213, raw=large_payload),  # Plugin data event
        Event(id=2, raw=b"\x09"),
    ]

    flp_path = tmp_path / "large_test.flp"
    flp_bytes = _build_synthetic_flp(events=events)
    flp_path.write_bytes(flp_bytes)

    # Parse with lazy=True and threshold=65536
    parsed = parse(flp_path, lazy=True, lazy_threshold=65536)
    assert len(parsed.events) == 3

    # Small events are materialized immediately
    assert not parsed.events[0].is_lazy
    assert not parsed.events[2].is_lazy

    # Large event is lazy
    lazy_event = parsed.events[1]
    assert lazy_event.is_lazy

    # Materialize payload upon access
    assert lazy_event.raw == large_payload
    assert not lazy_event.is_lazy

    # Serialization matches original file
    assert serialize(parsed) == flp_bytes

    # Test iter_events_from_file generator
    streamed_events = list(iter_events_from_file(flp_path, lazy=True, lazy_threshold=65536))
    assert len(streamed_events) == 3
    assert streamed_events[1].raw == large_payload


# =============================================================================
# Performance Budget Benchmark Tests ([FLP-02], [FLP-04])
# =============================================================================


def test_performance_budget_50mb(tmp_path: Path) -> None:
    """50 MB project binary parses and serializes in <= 3 seconds, memory <= 3x file size."""
    # req: FLP-02, FLP-04
    # Assemble a synthetic ~50 MB project:
    # 5 large plugin data blobs of 10 MB each, plus 1000 small events
    blob_10mb = b"B" * (10 * 1024 * 1024)
    events: list[Event] = []

    for i in range(1000):
        events.append(Event(id=0, raw=b"\x01"))
        events.append(Event(id=64, raw=struct.pack("<H", i % 65535)))
        events.append(Event(id=128, raw=struct.pack("<I", i)))

    for _ in range(5):
        events.append(Event(id=213, raw=blob_10mb))

    flp_bytes = _build_synthetic_flp(events=events)
    file_size_mb = len(flp_bytes) / (1024 * 1024)
    assert file_size_mb >= 50.0  # Verify it is at least 50 MB

    test_file = tmp_path / "budget_50mb.flp"
    test_file.write_bytes(flp_bytes)

    # 1. Benchmark Parse Time
    t0 = time.perf_counter()
    parsed = parse(flp_bytes)
    parse_duration = time.perf_counter() - t0
    assert parse_duration <= 3.0, f"Parse duration {parse_duration:.3f}s exceeded 3.0s budget"

    # 2. Benchmark Serialize Time
    t1 = time.perf_counter()
    serialized = serialize(parsed)
    serialize_duration = time.perf_counter() - t1
    assert serialize_duration <= 3.0, (
        f"Serialize duration {serialize_duration:.3f}s exceeded 3.0s budget"
    )

    # 3. Assert Byte Identity
    assert serialized == flp_bytes

    # 4. Benchmark Memory with Lazy Streaming Reader
    tracemalloc.start()
    parsed_lazy = parse(test_file, lazy=True, lazy_threshold=1024 * 1024)
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    max_memory_budget = len(flp_bytes) * 3
    assert peak_memory <= max_memory_budget, (
        f"Peak memory {peak_memory} exceeded 3x file size ({max_memory_budget})"
    )
    assert len(parsed_lazy.events) == len(events)


# =============================================================================
# Text Encoding Decoupling Tests ([FLP-06])
# =============================================================================


def test_text_encoding_separation() -> None:
    """Binary codec does not modify or decode raw text payloads into str [FLP-06]."""
    # req: FLP-06
    # UTF-16LE text representation of a Japanese track title
    japanese_title = "ドラム".encode("utf-16le")
    ev = Event(id=199, raw=japanese_title)

    raw_flp = _build_synthetic_flp(events=[ev])
    parsed = parse(raw_flp)

    # Codec stores exact bytes, leaving text decoding to schema profiles
    assert parsed.events[0].raw == japanese_title
    assert parsed.events[0].as_str(encoding="utf-16le") == "ドラム"
    assert serialize(parsed) == raw_flp


# =============================================================================
# Clean-Room Provenance & GPL Isolation Tests ([FLP-60])
# =============================================================================


def test_clean_room_provenance_and_zero_gpl() -> None:
    """Verify clean-room documentation exists and zero GPL imports exist in studiobridge."""
    # req: FLP-60
    provenance_doc = Path("docs/flp/PROVENANCE.md")
    assert provenance_doc.exists(), "docs/flp/PROVENANCE.md must exist per [FLP-60]"
    content = provenance_doc.read_text(encoding="utf-8")
    assert "Clean-Room Provenance Registry" in content
    assert "flp-file" in content
    assert "FLParser" in content
    assert "bravoh-daw" in content
    assert "GPL-3.0" in content

    # Scan python source code in packages/studiobridge to verify GPL library is NEVER imported
    src_dir = Path("packages/studiobridge/src/studiobridge")
    forbidden_pkg = "py" + "flp"
    for py_file in src_dir.rglob("*.py"):
        code = py_file.read_text(encoding="utf-8")
        assert f"import {forbidden_pkg}" not in code, f"Forbidden GPL import found in {py_file}"
        assert f"from {forbidden_pkg}" not in code, f"Forbidden GPL import found in {py_file}"


# =============================================================================
# Corpus Harness Tests (SBRIDGE_FLP_CORPUS_DIR) ([FLP-02])
# =============================================================================


def test_corpus_roundtrip_or_fixture_validation() -> None:
    """Execute lossless roundtrip across SBRIDGE_FLP_CORPUS_DIR if available [FLP-02]."""
    # req: FLP-02
    corpus_dir_env = os.environ.get("SBRIDGE_FLP_CORPUS_DIR")
    if corpus_dir_env and Path(corpus_dir_env).is_dir():
        corpus_path = Path(corpus_dir_env)
        flp_files = list(corpus_path.rglob("*.flp"))
        assert len(flp_files) > 0, f"No .flp files found in corpus directory {corpus_path}"

        for flp_path in flp_files:
            original_bytes = flp_path.read_bytes()
            parsed = parse(original_bytes)
            re_serialized = serialize(parsed)
            assert re_serialized == original_bytes, (
                f"Roundtrip failed for corpus file: {flp_path.name}"
            )
    else:
        # Fallback to multiple diverse synthetic projects
        for ch_count in [1, 4, 16, 64]:
            events = [
                Event(id=0, raw=b"\x00"),
                Event(id=64, raw=b"\x01\x02"),
                Event(id=128, raw=b"\x01\x02\x03\x04"),
                Event(id=199, raw=f"Project with {ch_count} channels".encode("ascii")),
            ]
            raw_data = _build_synthetic_flp(channels=ch_count, events=events)
            assert serialize(parse(raw_data)) == raw_data


# =============================================================================
# Error Handling & Corrupt Chunk Tests
# =============================================================================


def test_corrupt_chunk_and_stream_errors() -> None:
    """Structured FlpParseError and FlpInvariantViolationError on corrupt binaries."""
    # req: FLP-02
    # Truncated FLdt chunk header
    truncated_fldt = b"FLhd\x06\x00\x00\x00\x00\x00\x01\x00\x60\x00FLdt\x10\x00\x00\x00\x00"
    with pytest.raises(FlpParseError) as exc_info:
        parse(truncated_fldt)
    assert exc_info.value.code == "E_FLP_PARSE"
    assert exc_info.value.offset is not None

    # Truncated 2-byte event
    truncated_event = b"FLhd\x06\x00\x00\x00\x00\x00\x01\x00\x60\x00FLdt\x02\x00\x00\x00\x40\x01"
    with pytest.raises(FlpParseError) as exc_info:
        parse(truncated_event)
    assert exc_info.value.code == "E_FLP_PARSE"

    # Truncated variable event payload
    truncated_var = b"FLhd\x06\x00\x00\x00\x00\x00\x01\x00\x60\x00FLdt\x03\x00\x00\x00\xc0\x0a\x01"
    with pytest.raises(FlpParseError) as exc_info:
        parse(truncated_var)
    assert exc_info.value.code == "E_FLP_PARSE"

    # Invariant violation when event ID and payload length mismatch
    with pytest.raises(FlpInvariantViolationError):
        serialize_events([Event(id=0, raw=b"\x01\x02")])
    with pytest.raises(FlpInvariantViolationError):
        serialize_events([Event(id=64, raw=b"\x01")])
    with pytest.raises(FlpInvariantViolationError):
        serialize_events([Event(id=128, raw=b"\x01\x02\x03")])


def test_codec_api_coverage_and_convenience_methods(tmp_path: Path) -> None:
    """Verify convenience constructors, file IO helpers, and type validations [FLP-02]."""
    # req: FLP-02
    events = [Event(id=0, raw=b"\x01"), Event(id=199, raw=b"Test")]
    raw_flp = _build_synthetic_flp(events=events)

    # 1. Parse from io.BytesIO
    stream = io.BytesIO(raw_flp)
    flp_from_stream = parse(stream)
    assert len(flp_from_stream.events) == 2

    # 2. From bytes and from file classmethods
    flp_from_b = FlpFile.from_bytes(raw_flp)
    assert len(flp_from_b.events) == 2

    test_file = tmp_path / "saved.flp"
    flp_from_b.save(test_file)
    flp_from_f = FlpFile.from_file(test_file)
    assert flp_from_f.serialize() == raw_flp

    # 3. Serialize to destination stream and path
    buf = io.BytesIO()
    serialize(flp_from_b, destination=buf)
    assert buf.getvalue() == raw_flp

    out_file = tmp_path / "out_direct.flp"
    serialize(flp_from_b, destination=out_file)
    assert out_file.read_bytes() == raw_flp

    # 4. Serialize from tuple and from list of events
    hdr = FlpHeader(format=0, channels=2, ppq=96)
    tuple_bytes = serialize((hdr, events))
    assert len(tuple_bytes) > 0

    list_bytes = serialize(events)
    assert len(list_bytes) > 0

    # 5. Type validation errors
    with pytest.raises(TypeError):
        parse(12345)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        serialize("invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        serialize(flp_from_b, destination=12345)  # type: ignore[arg-type]

    with pytest.raises(FlpInvariantViolationError):
        from studiobridge.flp.codec.writer import write_chunk

        write_chunk(b"SHORT", b"", io.BytesIO())

    # 6. Event properties and raw setter
    ev = Event(id=1, raw=b"\x00")
    ev.raw = b"\xff"
    assert ev.raw == b"\xff"
    assert "Event(id=1" in repr(ev)

    lazy_ev = Event(id=213, raw=lambda: b"materialized")
    assert lazy_ev.is_lazy
    assert "raw=<lazy>" in repr(lazy_ev)
    assert lazy_ev.raw == b"materialized"
    assert not lazy_ev.is_lazy
