"""Unit tests for semantic FLP project diffing.

Verifies detection of added/removed channels, modified tempos, altered notes,
mixer routing, and metadata differences.
"""

from __future__ import annotations

import io
import struct

from studiobridge.flp import (
    Event,
    Project,
    diff_projects,
)
from studiobridge.flp.codec.writer import serialize_events


def _build_project_data(
    *,
    title: str = "Base Track",
    tempo_bpm: float = 120.0,
    channels: int = 2,
    has_notes: bool = True,
    note_count: int = 4,
    playlist_items: int = 2,
) -> bytes:
    """Helper to assemble raw project bytes for diff testing."""
    out = io.BytesIO()

    # Header
    out.write(b"FLhd")
    header_payload = struct.pack("<HHH", 0, channels, 96)
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)

    events: list[Event] = [
        Event(id=199, raw=b"26.1.0\x00"),
        Event(id=68, raw=struct.pack("<H", int(tempo_bpm))),
        Event(id=156, raw=struct.pack("<I", int(tempo_bpm * 1000))),
        Event(id=201, raw=title.encode("utf-16-le") + b"\x00\x00"),
    ]

    for ch_idx in range(channels):
        events.append(Event(id=64, raw=struct.pack("<H", ch_idx)))
        events.append(Event(id=200, raw=f"Inst {ch_idx + 1}".encode("utf-16-le") + b"\x00\x00"))

    # Pattern
    events.append(Event(id=65, raw=struct.pack("<H", 1)))
    if has_notes and note_count > 0:
        notes_raw = bytearray()
        for k in range(note_count):
            rec = bytearray(20)
            struct.pack_into("<II", rec, 0, k * 96, 96)
            struct.pack_into("<HH", rec, 8, 60, 0)
            struct.pack_into("<BBB", rec, 12, 64, 100, 64)
            notes_raw.extend(rec)
        events.append(Event(id=226, raw=bytes(notes_raw)))

    # Track data
    events.append(Event(id=238, raw=b"\x00" * 70))

    # Playlist items
    if playlist_items > 0:
        pl_bytes = bytearray(88 * playlist_items)
        for i in range(playlist_items):
            struct.pack_into("<IIII", pl_bytes, i * 88, i * 384, 384, 1, 1)
        events.append(Event(id=224, raw=bytes(pl_bytes)))

    events_payload = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(events_payload)))
    out.write(events_payload)

    return out.getvalue()


# =============================================================================
# 1. Identical Projects Diff
# =============================================================================


def test_identical_projects_diff() -> None:
    """Comparing identical projects produces has_differences=False."""
    # req: FLP-20
    data = _build_project_data(title="Twin", tempo_bpm=128.0)
    proj_a = Project.load(data)
    proj_b = Project.load(data)

    diff = diff_projects(proj_a, proj_b)
    assert diff.has_differences is False
    assert diff.format_text() == "Project Diff: Projects are structurally identical."


# =============================================================================
# 2. Metadata Differences
# =============================================================================


def test_metadata_tempo_and_title_diff() -> None:
    """Detects modified title, tempo, and fine tempo."""
    # req: FLP-20
    data_a = _build_project_data(title="Version 1", tempo_bpm=120.0)
    data_b = _build_project_data(title="Version 2", tempo_bpm=140.0)

    proj_a = Project.load(data_a)
    proj_b = Project.load(data_b)

    diff = Project.diff(proj_a, proj_b)
    assert diff.has_differences is True
    assert "title" in diff.metadata
    assert diff.metadata["title"]["before"] == "Version 1"
    assert diff.metadata["title"]["after"] == "Version 2"

    assert "tempo" in diff.metadata
    assert diff.metadata["tempo"]["before"] == 120.0
    assert diff.metadata["tempo"]["after"] == 140.0

    text = diff.format_text()
    assert "Version 1" in text
    assert "Version 2" in text
    assert "120.0" in text
    assert "140.0" in text


# =============================================================================
# 3. Channel Addition and Removal
# =============================================================================


def test_channel_addition_and_removal() -> None:
    """Detects added and removed channels."""
    # req: FLP-20
    data_a = _build_project_data(channels=2)
    data_b = _build_project_data(channels=4)

    proj_a = Project.load(data_a)
    proj_b = Project.load(data_b)

    diff = diff_projects(proj_a, proj_b)
    assert diff.has_differences is True
    assert len(diff.channels_added) == 2
    assert len(diff.channels_removed) == 0

    # Reverse comparison
    diff_rev = diff_projects(proj_b, proj_a)
    assert len(diff_rev.channels_removed) == 2
    assert len(diff_rev.channels_added) == 0


def test_channel_modification() -> None:
    """Detects channel parameter changes (volume, pan, mixer target, name)."""
    # req: FLP-20
    data = _build_project_data(channels=2)
    proj_a = Project.load(data)
    proj_b = Project.load(data)

    proj_b.channel(0).name = "Custom Lead"
    proj_b.channel(0).target_mixer_track = 5
    proj_b.channel(0).volume = 0.5

    diff = diff_projects(proj_a, proj_b)
    assert diff.has_differences is True
    assert len(diff.channels_modified) == 1

    ch_mod = diff.channels_modified[0]
    assert ch_mod["index"] == 0
    assert "name" in ch_mod["changes"]
    assert "mixer_track" in ch_mod["changes"]
    assert "volume" in ch_mod["changes"]


# =============================================================================
# 4. Pattern & Note Modifications
# =============================================================================


def test_pattern_note_differences() -> None:
    """Detects altered note counts or note pitches inside patterns."""
    # req: FLP-20
    data_a = _build_project_data(note_count=4)
    data_b = _build_project_data(note_count=8)

    proj_a = Project.load(data_a)
    proj_b = Project.load(data_b)

    diff = diff_projects(proj_a, proj_b)
    assert diff.has_differences is True
    assert len(diff.patterns_modified) == 1
    p_mod = diff.patterns_modified[0]
    assert p_mod["number"] == 1
    assert "total_notes" in p_mod["changes"]
    assert p_mod["changes"]["total_notes"]["before"] == 4
    assert p_mod["changes"]["total_notes"]["after"] == 8


# =============================================================================
# 5. Mixer & Playlist Diffing
# =============================================================================


def test_mixer_and_playlist_diffing() -> None:
    """Detects mixer track adjustments and playlist count changes."""
    # req: FLP-20
    data_a = _build_project_data(playlist_items=2)
    data_b = _build_project_data(playlist_items=5)

    proj_a = Project.load(data_a)
    proj_b = Project.load(data_b)

    proj_b.mixer_track(0).volume = 0.75
    proj_b.mixer_track(0).mute = True

    diff = diff_projects(proj_a, proj_b)
    assert diff.has_differences is True
    assert len(diff.mixer_modified) >= 1
    assert diff.playlist_diff["count_a"] == 2
    assert diff.playlist_diff["count_b"] == 5
    assert diff.playlist_diff["has_changes"] is True

    diff_dict = diff.to_dict()
    assert diff_dict["has_differences"] is True
    assert "mixer" in diff_dict
    assert "playlist" in diff_dict
