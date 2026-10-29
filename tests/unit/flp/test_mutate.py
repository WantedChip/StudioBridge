"""Unit and property-based tests for FLP project mutations and structural invariants.

Verifies mutation operators, untouched element serialization preservation ([FLP-21]),
journaling ([FLP-30]), header channel count consistency ([FLP-05]), and invariant
validation under Hypothesis property fuzzing.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from studiobridge.core.errors import FlpInvariantViolationError
from studiobridge.flp import (
    Event,
    Note,
    Project,
    check_invariants,
    validate_invariants,
)
from studiobridge.flp.codec.writer import serialize_events


def _build_synthetic_flp_bytes(
    *,
    version_str: str = "26.1.0",
    tempo_bpm: float = 120.0,
    channels: int = 2,
    ppq: int = 96,
    title: str = "Original Title",
    author: str = "Original Author",
    comments: str = "Original Comments",
    include_notes: bool = True,
    include_plugin: bool = True,
) -> bytes:
    """Helper to assemble a synthetic FLP binary data stream with verified events."""
    out = io.BytesIO()

    # 1. Header chunk (FLhd)
    header_payload = struct.pack("<HHH", 0, channels, ppq)
    out.write(b"FLhd")
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)

    # 2. Events in FLdt
    events: list[Event] = [
        Event(id=199, raw=version_str.encode("ascii") + b"\x00"),
        Event(id=68, raw=struct.pack("<H", int(tempo_bpm))),
        Event(id=156, raw=struct.pack("<I", int(tempo_bpm * 1000))),
        Event(id=201, raw=title.encode("utf-16-le") + b"\x00\x00"),
        Event(id=202, raw=comments.encode("utf-16-le") + b"\x00\x00"),
        Event(id=212, raw=author.encode("utf-16-le") + b"\x00\x00"),
    ]

    for ch_idx in range(channels):
        events.append(Event(id=64, raw=struct.pack("<H", ch_idx)))
        events.append(Event(id=200, raw=f"Channel {ch_idx}".encode("utf-16-le") + b"\x00\x00"))
        if ch_idx == 0 and include_plugin:
            events.append(Event(id=213, raw=b"\x11\x22\x33\x44" * 16))
        events.append(Event(id=215, raw=b"\x00" * 32))

    events.append(Event(id=65, raw=struct.pack("<H", 1)))
    events.append(Event(id=200, raw="Pattern 1".encode("utf-16-le") + b"\x00\x00"))
    if include_notes:
        note_bytes = bytearray()
        for k in range(2):
            rec = bytearray(20)
            struct.pack_into("<II", rec, 0, k * 96, 96)
            struct.pack_into("<HH", rec, 8, 60 + k, 0)
            struct.pack_into("<BBBB", rec, 12, 64, 100, 64, 0)
            note_bytes.extend(rec)
        events.append(Event(id=226, raw=bytes(note_bytes)))

    # Mixer track 0
    events.append(Event(id=238, raw=b"\x00" * 70))

    # Playlist items
    playlist_payload = bytearray(88)
    struct.pack_into("<IIII", playlist_payload, 0, 0, 192, 1, 1)
    events.append(Event(id=224, raw=bytes(playlist_payload)))

    # Unmodeled vendor event
    events.append(Event(id=172, raw=b"\x0a\x0b\x0c\x00"))

    events_payload = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(events_payload)))
    out.write(events_payload)

    return out.getvalue()


# =============================================================================
# 1. Project-Level Mutations ([FLP-30])
# =============================================================================


def test_project_metadata_mutations() -> None:
    """Project-level mutations update fields and log to journal [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    mutator.set_tempo(132.5)
    mutator.set_title("New Anthem")
    mutator.set_author("Cyber Producer")
    mutator.set_comments("Ready for mastering")

    assert proj.tempo == 132.5
    assert proj.fine_tempo == 132.5
    assert proj.title == "New Anthem"
    assert proj.author == "Cyber Producer"
    assert proj.comments == "Ready for mastering"

    assert len(mutator.records) == 4
    ops = [r.op for r in mutator.records]
    assert ops == [
        "project.set_tempo",
        "project.set_title",
        "project.set_author",
        "project.set_comments",
    ]


def test_project_tempo_bounds_enforced() -> None:
    """Tempo out of [10.0, 522.0] BPM raises FlpInvariantViolationError [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    with pytest.raises(FlpInvariantViolationError):
        mutator.set_tempo(5.0)

    with pytest.raises(FlpInvariantViolationError):
        mutator.set_tempo(600.0)


# =============================================================================
# 2. Pattern-Level Mutations ([FLP-30])
# =============================================================================


def test_pattern_mutations() -> None:
    """Pattern additions, renames, recoloring, and notes modifications [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    # Add pattern
    new_pat = mutator.add_pattern(name="Bassline", color="#00ff00")
    assert new_pat.number == 2
    assert new_pat.name == "Bassline"
    assert new_pat.color == "#00ff00"

    # Rename and recolor
    mutator.rename_pattern(1, "Lead Synths")
    mutator.recolor_pattern(1, 0xFF00AA)
    assert proj.pattern(1).name == "Lead Synths"
    assert proj.pattern(1).color == 0xFF00AA

    # Set notes: replace mode
    new_notes = [
        Note(pos=0, len=48, key=64, velocity=0.9),
        Note(pos=48, len=48, key=67, velocity=0.85),
    ]
    mutator.set_notes(2, 0, new_notes, mode="replace")
    assert len(proj.pattern(2).get_notes(0)) == 2
    assert proj.pattern(2).get_notes(0)[0].key == 64

    # Set notes: append mode
    extra_notes = [Note(pos=96, len=96, key=71, velocity=0.75)]
    mutator.set_notes(2, 0, extra_notes, mode="append")
    assert len(proj.pattern(2).get_notes(0)) == 3
    assert proj.pattern(2).get_notes(0)[2].key == 71

    # Clear pattern
    mutator.clear_pattern(1)
    assert proj.pattern(1).total_notes == 0


def test_pattern_set_notes_invalid_channel() -> None:
    """Referencing a non-existent channel rack index raises IndexError [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes(channels=2)
    proj = Project.load(raw)
    mutator = proj.mutate()

    with pytest.raises(IndexError):
        mutator.set_notes(1, 99, [Note(pos=0, len=96, key=60)])


# =============================================================================
# 3. Channel-Level Mutations ([FLP-30])
# =============================================================================


def test_channel_mutations() -> None:
    """Channel rename, recolor, mixer routing, volume, and pan operators [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes(channels=2)
    proj = Project.load(raw)
    mutator = proj.mutate()

    mutator.rename_channel(0, "Deep 808")
    mutator.recolor_channel(0, "#FF5500")
    mutator.set_mixer_target(0, 3)
    mutator.set_channel_volume(0, 0.85)
    mutator.set_channel_pan(0, -0.25)

    ch = proj.channel(0)
    assert ch.name == "Deep 808"
    assert ch.color == "#FF5500"
    assert ch.target_mixer_track == 3
    assert ch.volume == 0.85
    assert ch.pan == -0.25


# =============================================================================
# 4. Mixer-Level Mutations ([FLP-30])
# =============================================================================


def test_mixer_mutations() -> None:
    """Mixer track parameters, routing, mute, solo, and slot state [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    mutator.rename_track(1, "Drum Bus")
    mutator.recolor_track(1, 0x00FF88)
    mutator.set_track_volume(1, 0.78)
    mutator.set_track_pan(1, 0.1)
    mutator.set_track_mute(1, True)
    mutator.set_track_solo(1, False)
    mutator.set_track_routing(1, [0, 4])
    mutator.set_slot_state(1, 0, False)

    mt = proj.mixer_track(1)
    assert mt.name == "Drum Bus"
    assert mt.color == 0x00FF88
    assert mt.volume == 0.78
    assert mt.pan == 0.1
    assert mt.mute is True
    assert mt.solo is False
    assert mt.routing == [0, 4]
    assert mt.slots[0].enabled is False


# =============================================================================
# 5. Playlist-Level Mutations ([FLP-30])
# =============================================================================


def test_playlist_mutations() -> None:
    """Playlist items placement, moving, deleting, lane naming, and markers [FLP-30]."""
    # req: FLP-30
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    # Add item
    item = mutator.add_playlist_item(track=2, start=384, length=192, pattern_index=1)
    assert item.track == 2
    assert item.start == 384
    assert item.length == 192
    assert len(proj.arrangement.items) == 2

    # Move item
    mutator.move_playlist_item(1, track=3, start=768)
    assert proj.arrangement.items[1].track == 3
    assert proj.arrangement.items[1].start == 768

    # Delete item
    mutator.delete_playlist_item(0)
    assert len(proj.arrangement.items) == 1

    # Track lane styling & marker
    mutator.set_track_name(1, "Drums Lane")
    mutator.set_track_color(1, "#334455")
    marker = mutator.add_marker("Chorus 1", 768)
    assert marker.name == "Chorus 1"
    assert marker.position_ticks == 768


# =============================================================================
# 6. Untouched Elements Serialization Preservation ([FLP-21])
# =============================================================================


def test_untouched_elements_preserve_original_bytes(tmp_path: Path) -> None:
    """Mutating one element leaves untouched element bytes completely byte-identical [FLP-21]."""
    # req: FLP-21
    raw = _build_synthetic_flp_bytes(
        channels=2,
        title="Original Song",
        include_plugin=True,
    )
    proj = Project.load(raw)
    assert proj.source_file is not None

    # Find original plugin event (id 213) and unmodeled event (id 172)
    orig_plugin_ev = next(ev for ev in proj.source_file.events if ev.id == 213)
    orig_unmodeled_ev = next(ev for ev in proj.source_file.events if ev.id == 172)

    # Mutate ONLY project title
    proj.mutate().set_title("Completely New Title")

    # Serialize
    out_file = tmp_path / "mutated.flp"
    proj.save_as(out_file)

    # Re-parse output
    re_proj = Project.load(out_file)
    assert re_proj.title == "Completely New Title"
    assert re_proj.source_file is not None

    # The untouched plugin event bytes and unmodeled event bytes must be identical
    re_plugin_ev = next(ev for ev in re_proj.source_file.events if ev.id == 213)
    re_unmodeled_ev = next(ev for ev in re_proj.source_file.events if ev.id == 172)

    assert re_plugin_ev.raw == orig_plugin_ev.raw
    assert re_unmodeled_ev.raw == orig_unmodeled_ev.raw


# =============================================================================
# 7. Structural Invariant Checks & Violation Detection ([FLP-05])
# =============================================================================


def test_invariant_validation_clean_project() -> None:
    """Valid project passes invariant check with zero violations."""
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    violations = validate_invariants(proj)
    assert violations == []
    check_invariants(proj)  # Must not raise


def test_invariant_validation_header_channel_count_mismatch() -> None:
    """Header channel count not matching channel rack count raises E_FLP_INVARIANT [FLP-05]."""
    # req: FLP-05
    raw = _build_synthetic_flp_bytes(channels=2)
    proj = Project.load(raw)
    assert proj.source_file is not None
    assert proj.source_file.header is not None

    # Artificially desynchronize header channel count
    proj.source_file.header.channels = 5

    violations = validate_invariants(proj)
    assert any("[FLP-05]" in v for v in violations)

    with pytest.raises(FlpInvariantViolationError) as exc_info:
        check_invariants(proj)
    assert exc_info.value.code == "E_FLP_INVARIANT"


def test_invariant_validation_dangling_pattern_reference() -> None:
    """Playlist item referencing non-existent pattern number violates invariants."""
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)

    # Add item referencing pattern 99 (only pattern 1 exists)
    from studiobridge.flp.model.elements import PlaylistItem

    proj.arrangement.items.append(PlaylistItem(track=1, start=0, length=96, pattern_index=99))

    violations = validate_invariants(proj)
    assert any("references non-existent pattern number 99" in v for v in violations)

    with pytest.raises(FlpInvariantViolationError):
        check_invariants(proj)


def test_invariant_validation_invalid_note_key() -> None:
    """Note with MIDI key outside 0..127 violates structural invariants."""
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)

    proj.pattern(1).set_notes(0, [Note(pos=0, len=96, key=150)])

    violations = validate_invariants(proj)
    assert any("out of MIDI range 0..127" in v for v in violations)

    with pytest.raises(FlpInvariantViolationError):
        check_invariants(proj)


# =============================================================================
# 8. Hypothesis Property-Based Invariant Preservation Tests
# =============================================================================


@given(
    tempo=st.floats(min_value=20.0, max_value=300.0),
    title=st.text(min_size=0, max_size=50),
    channel_vol=st.floats(min_value=0.0, max_value=1.5),
    channel_pan=st.floats(min_value=-1.0, max_value=1.0),
    note_pos=st.integers(min_value=0, max_value=1000),
    note_len=st.integers(min_value=1, max_value=384),
    note_key=st.integers(min_value=0, max_value=127),
)
@settings(max_examples=30, deadline=None)
def test_property_mutations_preserve_invariants(
    tempo: float,
    title: str,
    channel_vol: float,
    channel_pan: float,
    note_pos: int,
    note_len: int,
    note_key: int,
) -> None:
    """Randomized sequences of valid mutations preserve structural invariants."""
    raw = _build_synthetic_flp_bytes()
    proj = Project.load(raw)
    mutator = proj.mutate()

    # Apply generated mutation sequence
    mutator.set_tempo(tempo)
    mutator.set_title(title)
    mutator.set_channel_volume(0, channel_vol)
    mutator.set_channel_pan(0, channel_pan)
    mutator.set_notes(
        1,
        0,
        [Note(pos=note_pos, len=note_len, key=note_key, velocity=0.8)],
        mode="replace",
    )

    # Invariants must hold cleanly after all mutations
    violations = validate_invariants(proj)
    assert violations == []
    check_invariants(proj)
