"""Unit and integration tests for Playlist namespace per 09_l1_sdk.md §4, §8 and v0.2.5.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) playlist interfaces:
- count(), get_track(index), list() with 1-based indexing
- set_name(), set_color()
- mute(), solo() with read-back verification
- Experimental clip placement gate (experimental.playlist_place) raising UnavailableError
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    CapabilityState,
    ExperimentalDisabledError,
    PlaylistTrack,
    ReadOnlyError,
    Studio,
    UnavailableError,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_playlist_tracks_and_inspection(studio: Studio) -> None:
    """Verify playlist track counting, listing, and 1-based indexing."""
    fl = studio

    tot = fl.playlist.count()
    assert isinstance(tot, int)
    assert tot >= 1

    track1 = fl.playlist.get_track(1)
    assert isinstance(track1, PlaylistTrack)
    assert track1.number == 1
    assert track1.index == 1
    assert "Track" in track1.name

    # Listing tracks
    tracks = fl.playlist.list(limit=8)
    assert isinstance(tracks, list)
    assert len(tracks) == 8
    assert tracks[0].number == 1

    # Invalid 0 or negative index raises ValueError per 1-based convention
    with pytest.raises(ValueError):
        fl.playlist.get_track(0)

    with pytest.raises(ValueError):
        fl.playlist.get_name(-1)


def test_sync_playlist_name_and_color(studio: Studio) -> None:
    """Verify playlist track name and color mutations with read-back verification."""
    fl = studio

    v_name = fl.playlist.set_name(1, "Lead Synths")
    assert isinstance(v_name, Verified)
    assert v_name.value == "Lead Synths"
    assert v_name.verified is True
    assert fl.playlist.get_name(1) == "Lead Synths"

    v_col = fl.playlist.set_color(1, 0xFF5500)
    assert isinstance(v_col, Verified)
    assert v_col.value == 0xFF5500
    assert v_col.verified is True
    assert fl.playlist.get_color(1) == 0xFF5500

    # Passing PlaylistTrack instance
    trk = fl.playlist.get_track(1)
    v_trk = fl.playlist.set_name(trk, "Lead Synths v2")
    assert v_trk.value == "Lead Synths v2"


def test_sync_playlist_mute_and_solo(studio: Studio) -> None:
    """Verify playlist track mute and solo states."""
    fl = studio

    # Mute track 1
    v_mute = fl.playlist.mute(1, True)
    assert isinstance(v_mute, Verified)
    assert v_mute.value is True
    assert fl.playlist.is_muted(1) is True

    # Unmute track 1
    v_unmute = fl.playlist.mute(1, False)
    assert v_unmute.value is False
    assert fl.playlist.is_muted(1) is False

    # Solo track 2
    v_solo = fl.playlist.solo(2, True)
    assert isinstance(v_solo, Verified)
    assert v_solo.value is True
    assert fl.playlist.is_solo(2) is True

    # Unsolo track 2
    v_unsolo = fl.playlist.solo(2, False)
    assert v_unsolo.value is False
    assert fl.playlist.is_solo(2) is False


def test_sync_playlist_experimental_placement_gate(studio: Studio) -> None:
    """Verify experimental place_pattern raises UnavailableError when disabled."""
    fl = studio

    # 1. Calling place_pattern without experimental capability enabled raises UnavailableError
    with pytest.raises(UnavailableError) as exc_info:
        fl.playlist.place_pattern(1, 1, 0.0)

    err = exc_info.value
    assert isinstance(err, (UnavailableError, ExperimentalDisabledError))
    assert err.capability_id == "experimental.playlist_place"

    # 2. Enable experimental capability and call place_pattern
    fl.caps.update(
        "experimental.playlist_place",
        CapabilityState.AVAILABLE,
        reason="Enabled by test harness",
    )

    v_place = fl.playlist.place_pattern(1, 1, 0.0)
    assert isinstance(v_place, Verified)
    assert v_place.value is True
    assert v_place.verified is True


def test_sync_playlist_readonly_guard(studio_readonly: Studio) -> None:
    """Verify playlist mutating operations raise ReadOnlyError in read-only mode."""
    fl = studio_readonly

    # Reads succeed
    assert isinstance(fl.playlist.get_name(1), str)
    assert isinstance(fl.playlist.is_muted(1), bool)

    # Writes fail
    with pytest.raises(ReadOnlyError):
        fl.playlist.set_name(1, "Exploit")

    with pytest.raises(ReadOnlyError):
        fl.playlist.mute(1, True)


@pytest.mark.anyio
async def test_async_playlist(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncPlaylist asynchronous operations."""
    port_sdk, _ = running_emulator

    async with AsyncStudio.connect(
        embedded=True,
        port=port_sdk,
        secret=sdk_secret,
        mode="write",
    ) as fl:
        tot = await fl.playlist.count()
        assert tot >= 1

        v_name = await fl.playlist.set_name(3, "Bassline")
        assert v_name.value == "Bassline"

        v_mute = await fl.playlist.mute(3, True)
        assert v_mute.value is True

        # Gated call raises UnavailableError when disabled
        with pytest.raises(UnavailableError):
            await fl.playlist.place_pattern(1, 3, 0.0)
