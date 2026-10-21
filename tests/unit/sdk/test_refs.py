"""Unit tests for entity reference handles and resolvers per 09_l1_sdk.md §3.2.

Tests named identity handles with strict index bases:
- MixerTrack(index): 0-based (0 = Master, 1..126 = Inserts), ValueError on < 0
- Channel(index): 0-based, ValueError on < 0
- Pattern(number): 1-based, ValueError on < 1
- PlaylistTrack(number): 1-based, ValueError on < 1
- Slot(track, slot): 0-based, ValueError on < 0
- resolve_reference helper: exact match, case-insensitive match,
  AmbiguousRefError with candidates/query, BadRefError with target
- High-level studio find() integration: fl.mixer.find(), fl.channels.find(),
  fl.patterns.find(), fl.playlist.find()
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AmbiguousRef,
    AmbiguousRefError,
    BadRef,
    BadRefError,
    Channel,
    MixerTrack,
    Pattern,
    PlaylistTrack,
    Slot,
    Studio,
    resolve_reference,
)


def test_mixer_track_ref() -> None:
    """Verify MixerTrack 0-based indexing and constraints."""
    master = MixerTrack(0, name="Master")
    assert master.index == 0
    assert master.is_master is True
    assert int(master) == 0
    assert hex(master) == "0x0"

    insert1 = MixerTrack(1, name="Kick")
    assert insert1.index == 1
    assert insert1.is_master is False
    assert int(insert1) == 1

    with pytest.raises(ValueError, match="0-based"):
        MixerTrack(-1)


def test_channel_ref() -> None:
    """Verify Channel 0-based indexing and constraints."""
    c0 = Channel(0, name="Sampler")
    assert c0.index == 0
    assert int(c0) == 0

    c3 = Channel(3, name="Synth")
    assert c3.index == 3
    assert int(c3) == 3

    with pytest.raises(ValueError, match="0-based"):
        Channel(-1)


def test_pattern_ref() -> None:
    """Verify Pattern 1-based indexing and constraints."""
    p1 = Pattern(1, name="Intro")
    assert p1.number == 1
    assert p1.index == 1
    assert int(p1) == 1

    p2 = Pattern(2, name="Verse")
    assert p2.number == 2
    assert int(p2) == 2

    # 1-based index validation: 0 and negative must raise ValueError
    with pytest.raises(ValueError, match="1-based"):
        Pattern(0)

    with pytest.raises(ValueError, match="1-based"):
        Pattern(-1)


def test_playlist_track_ref() -> None:
    """Verify PlaylistTrack 1-based indexing and constraints."""
    pt1 = PlaylistTrack(1, name="Drums")
    assert pt1.number == 1
    assert pt1.index == 1
    assert int(pt1) == 1

    pt10 = PlaylistTrack(10, name="Vocals")
    assert pt10.number == 10
    assert int(pt10) == 10

    # 1-based index validation: 0 and negative must raise ValueError
    with pytest.raises(ValueError, match="1-based"):
        PlaylistTrack(0)

    with pytest.raises(ValueError, match="1-based"):
        PlaylistTrack(-5)


def test_slot_ref() -> None:
    """Verify Slot 0-based track and slot indexing."""
    s0 = Slot(track=1, slot=0)
    assert s0.track == 1
    assert s0.slot == 0

    master_slot = Slot(track=0, slot=9)
    assert master_slot.track == 0
    assert master_slot.slot == 9

    with pytest.raises(ValueError, match="0-based"):
        Slot(track=-1, slot=0)

    with pytest.raises(ValueError, match="0-based"):
        Slot(track=1, slot=-1)


def test_resolve_reference_exact_and_ci() -> None:
    """Verify resolve_reference exact and case-insensitive resolution."""
    items = [
        MixerTrack(0, name="Master"),
        MixerTrack(1, name="Kick Drum"),
        MixerTrack(2, name="Bass"),
    ]

    # Exact match
    res = resolve_reference(items, "Master", entity_type="mixer track")
    assert res.index == 0

    # Case-insensitive match
    res_ci = resolve_reference(items, "kick drum", entity_type="mixer track")
    assert res_ci.index == 1

    res_ci_upper = resolve_reference(items, "BASS", entity_type="mixer track")
    assert res_ci_upper.index == 2


def test_resolve_reference_ambiguous_and_bad() -> None:
    """Verify resolve_reference raises AmbiguousRefError and BadRefError."""
    # Duplicate names (two tracks named 'Synth')
    items = [
        MixerTrack(1, name="Synth"),
        MixerTrack(2, name="Synth"),
        MixerTrack(3, name="Drums"),
    ]

    # Multiple exact matches
    with pytest.raises(AmbiguousRefError) as exc_info:
        resolve_reference(items, "Synth", entity_type="mixer track")

    err = exc_info.value
    assert len(err.candidates) == 2
    assert err.query == "Synth"
    # Verify AmbiguousRef alias works
    assert isinstance(err, AmbiguousRef)

    # Multiple case-insensitive matches
    items_ci = [
        MixerTrack(1, name="Pad A"),
        MixerTrack(2, name="PAD A"),
    ]
    with pytest.raises(AmbiguousRefError) as exc_ci:
        resolve_reference(items_ci, "pad a", entity_type="mixer track")
    assert len(exc_ci.value.candidates) == 2

    # Zero matches
    with pytest.raises(BadRefError) as bad_info:
        resolve_reference(items, "Guitar", entity_type="mixer track")

    bad_err = bad_info.value
    assert bad_err.target == "Guitar"
    assert "mixer track" in bad_err.remedy
    # Verify BadRef alias works
    assert isinstance(bad_err, BadRef)


def test_studio_find_mixer(studio: Studio) -> None:
    """Verify mixer.find() locates tracks and handles bad references."""
    fl = studio
    master = fl.mixer.find("Master")
    assert isinstance(master, MixerTrack)
    assert master.index == 0
    assert master.is_master is True

    # Non-existent name raises BadRefError
    with pytest.raises(BadRefError) as exc_info:
        fl.mixer.find("NonExistentMixerTrackXYZ")

    assert exc_info.value.target == "NonExistentMixerTrackXYZ"


def test_studio_find_channels(studio: Studio) -> None:
    """Verify channels.find() locates channels by name."""
    fl = studio
    chan0 = fl.channels.find(fl.channels.get_name(0))
    assert isinstance(chan0, Channel)
    assert chan0.index == 0


def test_studio_find_patterns(studio: Studio) -> None:
    """Verify patterns.find() locates patterns by name."""
    fl = studio
    pat1 = fl.patterns.find(fl.patterns.get_name(1))
    assert isinstance(pat1, Pattern)
    assert pat1.number == 1


def test_studio_find_playlist(studio: Studio) -> None:
    """Verify playlist.find() locates playlist tracks by name."""
    fl = studio
    pt1 = fl.playlist.find(fl.playlist.get_name(1))
    assert isinstance(pt1, PlaylistTrack)
    assert pt1.number == 1
