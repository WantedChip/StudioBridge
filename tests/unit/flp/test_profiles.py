"""Unit tests for FLP version profiles, text decoders, and compatibility resolver.

Verifies FL Studio 21–26 profile resolution, exact 88-byte playlist item offsets,
text decoding, write safety gates (E_FLP_VERSION), and fixture expectations manifest
per 07_l0e_flp_engine.md §3.2, §6, §7 and 12_crosscutting.md §7.
"""

from __future__ import annotations

import io
import os
import struct
from pathlib import Path

import pytest

from studiobridge.core.errors import FlpVersionUnsupportedError
from studiobridge.flp.codec.events import Event
from studiobridge.flp.codec.writer import serialize_events
from studiobridge.flp.schema import (
    decode_playlist_items,
    decode_text,
    decode_track_data,
    decode_version_string,
    detect_encoding,
    encode_text,
    get_profile,
    resolve_profile,
    resolve_profile_from_events,
    resolve_profile_from_file,
)
from tests.flp.diff_oracle import (
    MockGplOracle,
    ProjectStats,
    compare_flp,
    extract_studiobridge_stats,
    is_oracle_available,
)


def _build_synthetic_flp(
    *,
    version_str: str = "26.1.0",
    tempo_bpm: float = 120.0,
    channels: int = 4,
    ppq: int = 96,
    title: str = "Test Project",
    playlist_item_size: int = 88,
    playlist_item_count: int = 2,
    track_data_size: int = 70,
    has_event_172: bool = False,
) -> bytes:
    """Helper to assemble a synthetic FLP binary file with version and project metadata."""
    out = io.BytesIO()

    # 1. Header chunk (FLhd)
    header_payload = struct.pack("<HHH", 0, channels, ppq)
    out.write(b"FLhd")
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)

    # 2. Events in FLdt
    events: list[Event] = [
        # Event 199: Version string
        Event(id=199, raw=version_str.encode("ascii") + b"\x00"),
        # Event 68: Main tempo
        Event(id=68, raw=struct.pack("<H", int(tempo_bpm))),
        # Event 156: Fine tempo (BPM * 1000)
        Event(id=156, raw=struct.pack("<I", int(tempo_bpm * 1000))),
        # Event 201: Title (UTF-16LE)
        Event(id=201, raw=title.encode("utf-16-le") + b"\x00\x00"),
    ]

    # Event 172 (FL 25.2.3+ quirk, 4-byte dword framing)
    if has_event_172:
        events.append(Event(id=172, raw=b"\x01\x02\x03\x00"))

    # Event 238: Track data
    if track_data_size > 0:
        events.append(Event(id=238, raw=b"\x00" * track_data_size))

    # Event 224: Playlist items
    if playlist_item_count > 0:
        raw_items = bytearray()
        for i in range(playlist_item_count):
            item_raw = bytearray(playlist_item_size)
            # start_time (uint32), length (uint32), track (uint32), pattern (uint32)
            struct.pack_into("<IIII", item_raw, 0, i * 192, 192, i + 1, 1)
            raw_items.extend(item_raw)
        events.append(Event(id=224, raw=bytes(raw_items)))

    events_payload = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(events_payload)))
    out.write(events_payload)

    return out.getvalue()


# =============================================================================
# 1. Text Decoding Tests ([FLP-06])
# =============================================================================


def test_text_decoding_utf16le() -> None:
    """UTF-16LE strings decode cleanly with and without trailing null terminators [FLP-06]."""
    # req: FLP-06
    # With double null terminator
    raw_with_null = "Lead Synth".encode("utf-16-le") + b"\x00\x00"
    assert decode_text(raw_with_null, encoding="utf-16-le") == "Lead Synth"

    # Without null terminator
    raw_no_null = "Bassline".encode("utf-16-le")
    assert decode_text(raw_no_null, encoding="utf-16-le") == "Bassline"

    # Empty bytes
    assert decode_text(b"", encoding="utf-16-le") == ""


def test_text_decoding_odd_length_and_fallback() -> None:
    """Odd-length bytes or legacy data fall back gracefully without exceptions [FLP-06]."""
    # req: FLP-06
    # ASCII string in byte stream with odd length
    raw_ascii = b"Legacy String\x00"
    decoded = decode_text(raw_ascii, encoding="utf-16-le")
    assert decoded == "Legacy String"

    # CP1252 / Latin1 single byte characters
    raw_latin = "Caf\xe9".encode("latin1")
    assert decode_text(raw_latin, encoding="cp1252") == "Café"


def test_text_encoding_roundtrip() -> None:
    """String encoding produces expected binary payloads with optional null termination [FLP-06]."""
    # req: FLP-06
    encoded_utf16 = encode_text("Kick", encoding="utf-16-le", null_terminate=True)
    assert encoded_utf16.endswith(b"\x00\x00")
    assert decode_text(encoded_utf16, encoding="utf-16-le") == "Kick"

    encoded_ascii = encode_text("Snare", encoding="ascii", null_terminate=True)
    assert encoded_ascii == b"Snare\x00"
    assert decode_text(encoded_ascii, encoding="ascii") == "Snare"


def test_version_string_decoding() -> None:
    """decode_version_string handles both ASCII and UTF-16LE version payloads [FLP-06, FLP-10]."""
    # req: FLP-06, FLP-10
    # Modern ASCII format
    raw_v26 = b"26.1.0.1234\x00"
    assert decode_version_string(raw_v26) == "26.1.0.1234"

    # FL 21 ASCII format
    raw_v21 = b"21.0.3.3517\x00"
    assert decode_version_string(raw_v21) == "21.0.3.3517"

    # UTF-16LE format
    raw_v26_utf16 = "26.0.0".encode("utf-16-le") + b"\x00\x00"
    assert decode_version_string(raw_v26_utf16) == "26.0.0"

    # Empty payload
    assert decode_version_string(b"") == ""


def test_detect_encoding() -> None:
    """detect_encoding distinguishes UTF-16LE, UTF-8, and single-byte streams [FLP-06]."""
    # req: FLP-06
    utf16_sample = "StudioBridge".encode("utf-16-le")
    assert detect_encoding(utf16_sample) == "utf-16-le"

    utf8_sample = "StudioBridge ♫".encode()
    assert detect_encoding(utf8_sample) == "utf-8"

    ascii_sample = b"StudioBridge"
    assert detect_encoding(ascii_sample) == "ascii"


# =============================================================================
# 2. Profile Resolution Tests ([FLP-10])
# =============================================================================


def test_profile_resolution_fl26() -> None:
    """Resolver accurately selects FL Studio 26 profile for 26.x version strings [FLP-10]."""
    # req: FLP-10
    result = resolve_profile("26.1.0.1234")
    assert result.is_exact_match is True
    assert result.is_fallback is False
    assert result.profile.id == "fl26"
    assert result.profile.struct_layouts.playlist_item_size == 88
    assert result.profile.struct_layouts.track_data_size == 70
    assert result.risk is None
    assert result.read_only is False


def test_profile_resolution_fl21_25() -> None:
    """Resolver accurately selects FL Studio 21-25 profile for 21.x to 25.x versions [FLP-10]."""
    # req: FLP-10
    for v in ["21.0.3", "24.1.0", "25.2.3"]:
        res = resolve_profile(v)
        assert res.is_exact_match is True
        assert res.profile.id == "fl21_25"
        assert res.profile.struct_layouts.playlist_item_size == 80
        assert res.risk is None
        assert res.read_only is False


def test_profile_resolution_from_events() -> None:
    """resolve_profile_from_events discovers event 199 in event stream [FLP-10]."""
    # req: FLP-10
    events = [
        Event(id=0, raw=b"\x00"),
        Event(id=199, raw=b"26.0.0\x00"),
        Event(id=68, raw=b"\x78\x00"),
    ]
    res = resolve_profile_from_events(events)
    assert res.profile.id == "fl26"
    assert res.version == "26.0.0"


def test_profile_resolution_missing_event_199() -> None:
    """Event stream without event 199 falls back to default profile with risk flag [FLP-10]."""
    # req: FLP-10
    events = [Event(id=0, raw=b"\x00"), Event(id=68, raw=b"\x78\x00")]
    res = resolve_profile_from_events(events)
    assert res.is_exact_match is False
    assert res.is_fallback is True
    assert res.risk == "unknown_version"
    assert res.read_only is True


# =============================================================================
# 3. Fallback Resolution & Write Gate Safety ([FLP-32], 12 §7)
# =============================================================================


def test_newer_version_fallback_and_write_blocked() -> None:
    """Newer unknown versions fall back to nearest older profile and block writes [FLP-32]."""
    # req: FLP-32
    res = resolve_profile("27.0.0")
    assert res.is_exact_match is False
    assert res.is_fallback is True
    assert res.risk == "unknown_version"
    assert res.read_only is True
    assert res.profile.id == "fl26"

    # Attempting write operation without force must raise FlpVersionUnsupportedError (E_FLP_VERSION)
    with pytest.raises(FlpVersionUnsupportedError) as exc_info:
        res.assert_can_write()
    assert exc_info.value.code == "E_FLP_VERSION"
    assert "27.0.0" in str(exc_info.value)

    # Forcing write overrides the gate
    res.assert_can_write(force=True)


def test_older_version_fallback_and_write_blocked() -> None:
    """Historical versions older than lowest profile fall back in read-only mode [FLP-32]."""
    # req: FLP-32
    res = resolve_profile("11.1.0")
    assert res.is_exact_match is False
    assert res.is_fallback is True
    assert res.risk == "unknown_version"
    assert res.read_only is True
    assert res.profile.id == "fl21_25"

    with pytest.raises(FlpVersionUnsupportedError) as exc_info:
        res.assert_can_write()
    assert exc_info.value.code == "E_FLP_VERSION"


# =============================================================================
# 4. Playlist Item Chunks & Record Offsets ([FLP-10], [FLP-11])
# =============================================================================


def test_fl26_playlist_items_88_byte_offsets() -> None:
    """FL Studio 26 playlist item chunks decode with exact 88-byte offsets [FLP-10, FLP-11]."""
    # req: FLP-10, FLP-11
    fl26 = get_profile("fl26")
    assert fl26.struct_layouts.playlist_item_size == 88

    # Create payload containing 3 records of 88 bytes each (total 264 bytes)
    payload = bytearray()
    for i in range(3):
        rec = bytearray(88)
        # start_time=192*i, length=192, track=i+1, pattern=1, flags=0
        struct.pack_into("<IIII", rec, 0, i * 192, 192, i + 1, 1)
        payload.extend(rec)

    items = decode_playlist_items(bytes(payload), fl26)
    assert len(items) == 3

    # Check exact offsets: 0, 88, 176
    assert items[0].offset == 0
    assert len(items[0].raw) == 88
    assert items[0].start_time == 0
    assert items[0].track_index == 1

    assert items[1].offset == 88
    assert len(items[1].raw) == 88
    assert items[1].start_time == 192
    assert items[1].track_index == 2

    assert items[2].offset == 176
    assert len(items[2].raw) == 88
    assert items[2].start_time == 384
    assert items[2].track_index == 3


def test_fl21_25_playlist_items_80_byte_offsets() -> None:
    """FL Studio 21-25 playlist item chunks decode with exact 80-byte offsets [FLP-10, FLP-11]."""
    # req: FLP-10, FLP-11
    fl21 = get_profile("fl21_25")
    assert fl21.struct_layouts.playlist_item_size == 80

    payload = bytearray(80 * 2)
    items = decode_playlist_items(bytes(payload), fl21)
    assert len(items) == 2
    assert items[0].offset == 0
    assert items[1].offset == 80


def test_legacy_playlist_record_sizes() -> None:
    """Historical playlist record sizes (60 bytes, 32 bytes) decode cleanly [FLP-10]."""
    # req: FLP-10
    # 60-byte intermediate records (FL 12-20)
    payload_60 = bytes(60 * 4)
    items_60 = decode_playlist_items(payload_60, 60)
    assert len(items_60) == 4
    assert [it.offset for it in items_60] == [0, 60, 120, 180]

    # 32-byte legacy records (FL 1-11)
    payload_32 = bytes(32 * 3)
    items_32 = decode_playlist_items(payload_32, 32)
    assert len(items_32) == 3
    assert [it.offset for it in items_32] == [0, 32, 64]


def test_invalid_playlist_record_size_raises() -> None:
    """Non-positive record size raises ValueError [FLP-10]."""
    # req: FLP-10
    with pytest.raises(ValueError):
        decode_playlist_items(b"\x00" * 88, 0)
    with pytest.raises(ValueError):
        decode_playlist_items(b"\x00" * 88, -10)


# =============================================================================
# 5. Track Data & Event 172 Quirk Tests ([FLP-10], [FLP-11])
# =============================================================================


def test_track_data_decoding_sizes() -> None:
    """Track data decodes 70B (FL 26), 66B (FL 24/25), and 61B (FL 21) [FLP-10, FLP-11]."""
    # req: FLP-10, FLP-11
    rec_70 = decode_track_data(bytes(70), 70)
    assert rec_70.size == 70

    rec_66 = decode_track_data(bytes(66), 66)
    assert rec_66.size == 66

    rec_61 = decode_track_data(bytes(61), 61)
    assert rec_61.size == 61


def test_event_172_quirk_mapping() -> None:
    """FL 25.2.3+ 3-byte event 172 is defined in profile event meanings [FLP-10, FLP-11]."""
    # req: FLP-10, FLP-11
    fl21_25 = get_profile("fl21_25")
    meaning_172 = fl21_25.get_event_meaning(172)
    assert meaning_172 is not None
    assert meaning_172.name == "fl25_small_event"
    assert meaning_172.payload_effective_size == 3
    assert meaning_172.kind == "dword"


# =============================================================================
# 6. Fixture Expectations Manifest Tests ([FLP-12])
# =============================================================================


def test_fixture_expectations_manifest_fl26() -> None:
    """FL 26 fixture expectations manifest accurately matches synthetic project [FLP-12]."""
    # req: FLP-12
    fl26 = get_profile("fl26")
    exp = fl26.expectations["synthetic_minimal"]

    flp_bytes = _build_synthetic_flp(
        version_str=exp["fl_version"],
        tempo_bpm=exp["tempo"],
        channels=exp["channel_count"],
        playlist_item_size=exp["playlist_item_record_size"],
        playlist_item_count=exp["playlist_item_count"],
        track_data_size=exp["track_data_size"],
        title=exp["project_title"],
    )

    stats = extract_studiobridge_stats(flp_bytes)
    assert stats.version == exp["fl_version"]
    assert stats.tempo == exp["tempo"]
    assert stats.channel_count == exp["channel_count"]
    assert stats.playlist_item_count == exp["playlist_item_count"]
    assert stats.project_title == exp["project_title"]


def test_fixture_expectations_manifest_fl21_25() -> None:
    """FL 21 and FL 25 fixture expectations manifest match synthetic projects [FLP-12]."""
    # req: FLP-12
    fl21_25 = get_profile("fl21_25")

    # Test synthetic_fl21
    exp21 = fl21_25.expectations["synthetic_fl21"]
    flp_bytes_21 = _build_synthetic_flp(
        version_str=exp21["fl_version"],
        tempo_bpm=exp21["tempo"],
        channels=exp21["channel_count"],
        playlist_item_size=exp21["playlist_item_record_size"],
        playlist_item_count=exp21["playlist_item_count"],
        track_data_size=exp21["track_data_size"],
        title=exp21["project_title"],
    )
    stats21 = extract_studiobridge_stats(flp_bytes_21)
    assert stats21.version == exp21["fl_version"]
    assert stats21.tempo == exp21["tempo"]
    assert stats21.channel_count == exp21["channel_count"]
    assert stats21.playlist_item_count == exp21["playlist_item_count"]
    assert stats21.project_title == exp21["project_title"]

    # Test synthetic_fl25
    exp25 = fl21_25.expectations["synthetic_fl25"]
    flp_bytes_25 = _build_synthetic_flp(
        version_str=exp25["fl_version"],
        tempo_bpm=exp25["tempo"],
        channels=exp25["channel_count"],
        playlist_item_size=exp25["playlist_item_record_size"],
        playlist_item_count=exp25["playlist_item_count"],
        track_data_size=exp25["track_data_size"],
        title=exp25["project_title"],
        has_event_172=exp25.get("has_event_172", False),
    )
    stats25 = extract_studiobridge_stats(flp_bytes_25)
    assert stats25.version == exp25["fl_version"]
    assert stats25.tempo == exp25["tempo"]
    assert stats25.channel_count == exp25["channel_count"]
    assert stats25.playlist_item_count == exp25["playlist_item_count"]
    assert stats25.project_title == exp25["project_title"]


def test_corpus_fixture_expectations_if_present() -> None:
    """Validate real corpus projects against version expectations if configured [FLP-12]."""
    # req: FLP-12
    corpus_dir = os.environ.get("SBRIDGE_FLP_CORPUS_DIR")
    if not corpus_dir or not Path(corpus_dir).is_dir():
        pytest.skip("SBRIDGE_FLP_CORPUS_DIR is not set or does not exist")

    corpus_path = Path(corpus_dir)
    flp_files = list(corpus_path.glob("*.flp"))
    if not flp_files:
        pytest.skip(f"No .flp files found in {corpus_dir}")

    for file_path in flp_files:
        res = resolve_profile_from_file(file_path)
        stats = extract_studiobridge_stats(file_path)
        assert stats.version == res.version
        assert stats.channel_count >= 0


# =============================================================================
# 7. Dev-Only Differential Oracle Tests ([FLP-11], [FLP-60])
# =============================================================================


def test_differential_oracle_comparison() -> None:
    """Differential testing oracle executes and compares metrics cleanly [FLP-11, FLP-60]."""
    # req: FLP-11, FLP-60
    synthetic_flp = _build_synthetic_flp(version_str="26.1.0", tempo_bpm=120.0, channels=4)

    # 1. Comparison with default or mock oracle passes when stats match
    mock_oracle = MockGplOracle()
    report = compare_flp(synthetic_flp, oracle=mock_oracle)
    assert report.passed is True
    assert len(report.mismatches) == 0

    # 2. Mismatch detection
    mismatched_stats = ProjectStats(
        version="26.1.0",
        channel_count=99,  # Intentional mismatch
        tempo=140.0,  # Intentional mismatch
        project_title="Different Title",  # Intentional mismatch
        playlist_item_count=99,  # Intentional mismatch
        raw_event_count=10,
    )
    failing_oracle = MockGplOracle(override_stats=mismatched_stats)
    fail_report = compare_flp(synthetic_flp, oracle=failing_oracle)
    assert fail_report.passed is False
    assert len(fail_report.mismatches) >= 3

    # 3. is_oracle_available function
    avail = is_oracle_available()
    assert isinstance(avail, bool)


# =============================================================================
# 8. Clean-Room Provenance & Zero GPL in Source Tree ([FLP-60])
# =============================================================================


def test_clean_room_provenance_and_zero_gpl_imports() -> None:
    """Ensure no GPL modules are imported anywhere inside src/ [FLP-60]."""
    # req: FLP-60
    src_dir = Path(__file__).parents[3] / "packages" / "studiobridge" / "src"
    forbidden_pkg = "py" + "flp"
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        err_msg = f"Forbidden GPL import found in {py_file.name}"
        assert f"import {forbidden_pkg}" not in content, err_msg
        assert f"from {forbidden_pkg}" not in content, err_msg
