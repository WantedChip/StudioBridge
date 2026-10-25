"""Unit tests for high-level FLP object model hydration and event tracking.

Verifies Project, Channel, Pattern, Note, MixerTrack, Slot, PlaylistItem,
Arrangement, and unmodeled event tail list per 07_l0e_flp_engine.md §3.3,
09_l1_sdk.md §1–§2, [FLP-20], and [FLP-21].
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from studiobridge import Project as RootProject
from studiobridge.flp import (
    Arrangement,
    Event,
    OpaquePlugin,
    Project,
    Slot,
    UnmodeledEvent,
)
from studiobridge.flp.codec.writer import serialize_events


def _build_test_project_bytes(
    *,
    version_str: str = "26.1.0",
    tempo_bpm: float = 128.5,
    channels: int = 3,
    ppq: int = 96,
    title: str = "Test Electronic Track",
    author: str = "Sound Designer",
    comments: str = "Created for FLP model validation",
    include_notes: bool = True,
    include_plugin: bool = True,
    include_unmodeled_event: bool = True,
) -> bytes:
    """Build synthetic FLP binary data stream with structured project events."""
    out = io.BytesIO()

    # 1. Header chunk (FLhd)
    header_payload = struct.pack("<HHH", 0, channels, ppq)
    out.write(b"FLhd")
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)

    # 2. Events in FLdt
    events: list[Event] = [
        # Metadata
        Event(id=199, raw=version_str.encode("ascii") + b"\x00"),
        Event(id=68, raw=struct.pack("<H", int(tempo_bpm))),
        Event(id=156, raw=struct.pack("<I", int(tempo_bpm * 1000))),
        Event(id=201, raw=title.encode("utf-16-le") + b"\x00\x00"),
        Event(id=202, raw=comments.encode("utf-16-le") + b"\x00\x00"),
        Event(id=212, raw=author.encode("utf-16-le") + b"\x00\x00"),
    ]

    # Channels
    for ch_idx in range(channels):
        events.append(Event(id=64, raw=struct.pack("<H", ch_idx)))
        ch_name = f"Synth {ch_idx + 1}" if ch_idx > 0 else "Kick Drum"
        events.append(Event(id=200, raw=ch_name.encode("utf-16-le") + b"\x00\x00"))
        if ch_idx == 1 and include_plugin:
            events.append(Event(id=213, raw=b"\xaa\xbb\xcc\xdd" * 16))
        events.append(Event(id=215, raw=b"\x00" * 32))

    # Pattern & Notes
    events.append(Event(id=65, raw=struct.pack("<H", 1)))  # Pattern 1
    if include_notes:
        note_bytes = bytearray()
        # 4 quarter notes: pos = 0, 96, 192, 288, len = 96, key = 60, pan = 64
        for k in range(4):
            rec = bytearray(20)
            struct.pack_into("<II", rec, 0, k * 96, 96)
            struct.pack_into("<HH", rec, 8, 60, 0)
            struct.pack_into("<BBB", rec, 12, 64, 100, 64)
            note_bytes.extend(rec)
        events.append(Event(id=226, raw=bytes(note_bytes)))

    # Mixer track data
    events.append(Event(id=238, raw=b"\x00" * 70))  # Track 0 (Master)

    # Playlist items (2 items in FL26 88-byte layout)
    playlist_payload = bytearray(88 * 2)
    # Item 1: start=0, len=384, track=1, pattern=1
    struct.pack_into("<IIII", playlist_payload, 0, 0, 384, 1, 1)
    # Item 2: start=384, len=384, track=1, pattern=1
    struct.pack_into("<IIII", playlist_payload, 88, 384, 384, 1, 1)
    events.append(Event(id=224, raw=bytes(playlist_payload)))

    # Unknown / unmodeled event (e.g. event 172 or 180)
    if include_unmodeled_event:
        events.append(Event(id=172, raw=b"\x01\x02\x03\x00"))
        events.append(Event(id=55, raw=b"\x7f"))

    events_payload = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(events_payload)))
    out.write(events_payload)

    return out.getvalue()


# =============================================================================
# 1. Project Hydration & Top-level Namespace Export ([FLP-20], 09 §1–§2)
# =============================================================================


def test_project_top_level_exports() -> None:
    """Project is accessible from both studiobridge and studiobridge.flp."""
    # req: FLP-20
    assert RootProject is Project
    assert issubclass(Project, object)


def test_project_load_from_bytes() -> None:
    """Project.load parses binary stream into complete typed object tree [FLP-20]."""
    # req: FLP-20
    data = _build_test_project_bytes(
        version_str="26.1.0",
        tempo_bpm=135.0,
        channels=3,
        ppq=96,
        title="Epic Lead",
        author="Producer Alpha",
    )
    proj = Project.load(data)

    assert proj.version == "26.1.0"
    assert proj.title == "Epic Lead"
    assert proj.author == "Producer Alpha"
    assert proj.tempo == 135.0
    assert proj.fine_tempo == 135.0
    assert proj.ppq == 96
    assert proj.licensed is True
    assert len(proj.channels) == 3


def test_project_load_from_file(tmp_path: Path) -> None:
    """Project.load parses file from disk path."""
    # req: FLP-20
    flp_path = tmp_path / "test.flp"
    flp_path.write_bytes(_build_test_project_bytes(title="Disk Song"))

    proj = Project.load(flp_path)
    assert proj.title == "Disk Song"
    assert len(proj.channels) == 3


# =============================================================================
# 2. Channel & Plugin Object Model ([FLP-20], [FLP-21])
# =============================================================================


def test_channel_hydration_and_source_events() -> None:
    """Channel models retain metadata, plugin wrappers, and event handles [FLP-20, FLP-21]."""
    # req: FLP-20, FLP-21
    data = _build_test_project_bytes(channels=3, include_plugin=True)
    proj = Project.load(data)

    ch0 = proj.channel(0)
    assert ch0.index == 0
    assert ch0.name == "Kick Drum"
    assert ch0.channel_type == "sampler"
    assert ch0.target_mixer_track == 0
    assert ch0.mixer_track == 0
    assert len(ch0.source_events) > 0

    ch1 = proj.channel(1)
    assert ch1.index == 1
    assert ch1.name == "Synth 2"
    assert ch1.channel_type == "plugin"
    assert ch1.plugin is not None
    assert isinstance(ch1.plugin, OpaquePlugin)
    assert len(ch1.plugin.data) == 64
    assert len(ch1.source_events) > 0
    assert len(ch1.plugin.source_events) > 0


def test_channel_index_error() -> None:
    """Channel accessor raises IndexError for out of range indices."""
    # req: FLP-20
    data = _build_test_project_bytes(channels=2)
    proj = Project.load(data)

    with pytest.raises(IndexError, match="Channel index 99 out of range"):
        proj.channel(99)


# =============================================================================
# 3. Pattern & Note Object Model ([FLP-20], [FLP-21])
# =============================================================================


def test_pattern_and_notes_hydration() -> None:
    """Pattern models hydrate note lists, timing, and pitch accurately [FLP-20, FLP-21]."""
    # req: FLP-20, FLP-21
    data = _build_test_project_bytes(include_notes=True)
    proj = Project.load(data)

    assert len(proj.patterns) >= 1
    pat1 = proj.pattern(1)
    assert pat1.number == 1
    assert len(pat1.source_events) > 0

    all_notes = pat1.all_notes
    assert len(all_notes) == 4
    assert pat1.total_notes == 4

    # Validate note fields
    for idx, n in enumerate(all_notes):
        assert n.pos == idx * 96
        assert n.len == 96
        assert n.key == 60
        assert n.release == 64
        assert len(n.source_events) > 0


def test_pattern_key_error() -> None:
    """Pattern accessor raises KeyError when pattern number does not exist."""
    # req: FLP-20
    data = _build_test_project_bytes()
    proj = Project.load(data)

    with pytest.raises(KeyError, match="Pattern number 99 not found"):
        proj.pattern(99)


# =============================================================================
# 4. Mixer Track & Slots Object Model ([FLP-20], [FLP-21])
# =============================================================================


def test_mixer_tracks_and_slots() -> None:
    """Mixer tracks maintain 10 effect slots and retain event handles [FLP-20, FLP-21]."""
    # req: FLP-20, FLP-21
    data = _build_test_project_bytes()
    proj = Project.load(data)

    assert len(proj.mixer) == 126
    master = proj.mixer_track(0)
    assert master.index == 0
    assert master.name == "Master"
    assert len(master.slots) == 10
    assert len(master.source_events) > 0  # Captured from event 238

    # All slots default to empty
    for s in master.slots:
        assert isinstance(s, Slot)
        assert s.is_empty is True


# =============================================================================
# 5. Arrangement & Playlist Items ([FLP-20], [FLP-21])
# =============================================================================


def test_playlist_items_hydration() -> None:
    """Playlist arrangement items decode positions, tracks, and pattern refs [FLP-20, FLP-21]."""
    # req: FLP-20, FLP-21
    data = _build_test_project_bytes()
    proj = Project.load(data)

    arr = proj.arrangement
    assert isinstance(arr, Arrangement)
    assert len(arr.items) == 2
    assert len(arr.source_events) > 0

    it1 = arr.items[0]
    assert it1.track == 1
    assert it1.start == 0
    assert it1.length == 384
    assert it1.pattern_index == 1
    assert len(it1.source_events) > 0

    it2 = arr.items[1]
    assert it2.track == 1
    assert it2.start == 384
    assert it2.length == 384
    assert it2.pattern_index == 1


# =============================================================================
# 6. Unmodeled Events Tail List Retention ([FLP-20])
# =============================================================================


def test_unmodeled_events_tail_list_retention() -> None:
    """Unmodeled and unknown events are retained with byte positions in tail list [FLP-20]."""
    # req: FLP-20
    data = _build_test_project_bytes(include_unmodeled_event=True)
    proj = Project.load(data)

    assert len(proj.unmodeled_events) >= 2
    unmod_ids = [u.event.id for u in proj.unmodeled_events]
    assert 172 in unmod_ids
    assert 55 in unmod_ids

    for u in proj.unmodeled_events:
        assert isinstance(u, UnmodeledEvent)
        assert u.event_index >= 0
        assert u.byte_position is not None
        assert u.byte_position >= 0
        assert len(u.event.raw) > 0


# =============================================================================
# 7. Inspection Summaries & Dictionaries ([FLP-20], 07 §8)
# =============================================================================


def test_project_info_and_to_dict() -> None:
    """Project.info() and to_dict() produce complete standardized summaries [FLP-20]."""
    # req: FLP-20
    data = _build_test_project_bytes(
        title="Summer Vibe",
        author="DJ FL",
        tempo_bpm=124.0,
        channels=3,
    )
    proj = Project.load(data)

    info = proj.info()
    assert info["title"] == "Summer Vibe"
    assert info["author"] == "DJ FL"
    assert info["tempo"] == 124.0
    assert info["channel_count"] == 3
    assert info["playlist_item_count"] == 2
    assert "channels" in info
    assert "patterns" in info

    d = proj.to_dict()
    assert "metadata" in d
    assert "channels" in d
    assert "patterns" in d
    assert "arrangement" in d
    assert d["metadata"]["title"] == "Summer Vibe"
