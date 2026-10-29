"""Unit and integration tests for Mixer namespace.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) mixer interfaces:
- get_track(), get_tracks()
- set_volume(), set_pan() with Verified[float] readback
- mute(), solo(), arm()
- set_name(), set_color()
- get_peak()
- route() audio send routing
- link_channel() channel-to-mixer assignment
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    Channel,
    MixerTrack,
    ReadOnlyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_mixer_get_tracks(studio: Studio) -> None:
    """Verify mixer get_track and get_tracks return structured MixerTrack objects."""
    fl = studio

    # Master track (index 0)
    master = fl.mixer.get_track(0)
    assert isinstance(master, MixerTrack)
    assert master.index == 0
    assert "Master" in master.name
    assert isinstance(master.volume, float)
    assert isinstance(master.pan, float)
    assert isinstance(master.muted, bool)

    # Track list
    tracks = fl.mixer.get_tracks()
    assert isinstance(tracks, list)
    assert len(tracks) >= 4
    assert tracks[0].index == 0
    assert tracks[1].index == 1

    # Negative index raises ValueError
    with pytest.raises(ValueError):
        fl.mixer.get_track(-1)


def test_sync_mixer_volume_and_pan(studio: Studio) -> None:
    """Verify mixer volume and pan with Verified contract and MixerTrack object input."""
    fl = studio

    # Volume setting
    v_vol = fl.mixer.set_volume(1, 0.65)
    assert isinstance(v_vol, Verified)
    assert v_vol.requested == 0.65
    assert abs(v_vol.value - 0.65) < 0.05
    assert v_vol.verified is True
    assert v_vol.plane == "live"
    assert v_vol.proof == "readback"
    assert v_vol.fp == fl.fp

    # Pan setting
    v_pan = fl.mixer.set_pan(1, -0.25)
    assert isinstance(v_pan, Verified)
    assert v_pan.requested == -0.25
    assert abs(v_pan.value - (-0.25)) < 0.05
    assert v_pan.verified is True

    # Passing MixerTrack identity dataclass
    trk = fl.mixer.get_track(1)
    v_trk_vol = fl.mixer.set_volume(trk, 0.72)
    assert abs(v_trk_vol.value - 0.72) < 0.05


def test_sync_mixer_mute_solo_arm(studio: Studio) -> None:
    """Verify mute, solo, and arm toggle / explicit writes."""
    fl = studio

    # Mute
    v_mute = fl.mixer.mute(1, True)
    assert isinstance(v_mute, Verified)
    assert v_mute.value is True

    v_unmute = fl.mixer.mute(1, False)
    assert v_unmute.value is False

    # Solo
    v_solo = fl.mixer.solo(1, True)
    assert isinstance(v_solo, Verified)
    assert v_solo.value is True

    v_unsolo = fl.mixer.solo(1, False)
    assert v_unsolo.value is False

    # Arm
    v_arm = fl.mixer.arm(1, True)
    assert isinstance(v_arm, Verified)
    assert v_arm.value is True

    v_disarm = fl.mixer.arm(1, False)
    assert v_disarm.value is False


def test_sync_mixer_name_and_color(studio: Studio) -> None:
    """Verify track renaming and color assignment."""
    fl = studio

    # Name
    v_name = fl.mixer.set_name(1, "Lead Synth")
    assert isinstance(v_name, Verified)
    assert v_name.value == "Lead Synth"
    assert fl.mixer.get_name(1) == "Lead Synth"

    # Color (24-bit RGB)
    v_col = fl.mixer.set_color(1, 0x00FF88)
    assert isinstance(v_col, Verified)
    assert v_col.value == 0x00FF88
    assert fl.mixer.get_color(1) == 0x00FF88


def test_sync_mixer_routing_and_linking(studio: Studio) -> None:
    """Verify track peak querying, send routing, and channel linking."""
    fl = studio

    # Peak query
    peak = fl.mixer.get_peak(0)
    assert isinstance(peak, float)
    assert peak >= 0.0

    # Send routing
    v_route = fl.mixer.route(1, 2, True)
    assert isinstance(v_route, Verified)
    assert v_route.value is True

    # Link channel to track (supports int and Channel dataclass)
    v_link = fl.mixer.link_channel(0, 2)
    assert isinstance(v_link, Verified)
    assert v_link.value == 2

    chan = Channel(index=1, name="Sampler")
    v_link2 = fl.mixer.link_channel(chan, 3)
    assert v_link2.value == 3


def test_sync_mixer_readonly_guard(studio_readonly: Studio) -> None:
    """Verify mutating mixer methods raise ReadOnlyError in read_only mode."""
    fl = studio_readonly

    # Non-mutating methods succeed
    assert len(fl.mixer.get_tracks()) > 0
    assert fl.mixer.get_track(0).index == 0
    assert fl.mixer.get_peak(0) >= 0.0

    # Mutating operations fail with ReadOnlyError
    with pytest.raises(ReadOnlyError):
        fl.mixer.set_volume(0, 0.5)

    with pytest.raises(ReadOnlyError):
        fl.mixer.set_pan(0, 0.0)

    with pytest.raises(ReadOnlyError):
        fl.mixer.mute(0, True)

    with pytest.raises(ReadOnlyError):
        fl.mixer.solo(0, True)

    with pytest.raises(ReadOnlyError):
        fl.mixer.arm(0, True)

    with pytest.raises(ReadOnlyError):
        fl.mixer.set_name(1, "Vocals")

    with pytest.raises(ReadOnlyError):
        fl.mixer.set_color(1, 0xFFFFFF)

    with pytest.raises(ReadOnlyError):
        fl.mixer.route(1, 2, True)

    with pytest.raises(ReadOnlyError):
        fl.mixer.link_channel(0, 1)


@pytest.mark.anyio
async def test_async_mixer_operations(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncMixer operations under anyio."""
    port_sdk, _ = running_emulator
    async with AsyncStudio.connect(
        embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
    ) as fl:
        track = await fl.mixer.get_track(1)
        assert track.index == 1

        v_vol = await fl.mixer.set_volume(1, 0.7)
        assert abs(v_vol.value - 0.7) < 0.05

        v_pan = await fl.mixer.set_pan(1, 0.3)
        assert abs(v_pan.value - 0.3) < 0.05

        v_mute = await fl.mixer.mute(1, True)
        assert v_mute.value is True

        v_name = await fl.mixer.set_name(1, "Bassline")
        assert v_name.value == "Bassline"
