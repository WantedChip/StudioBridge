"""Unit and integration tests for Channels namespace per 09_l1_sdk.md §4 and v0.2.4.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) channels interfaces:
- count(), list(), get_channel()
- set_volume(), set_pan() with Verified[float] readback
- mute(), solo()
- set_name(), set_color(), set_pitch()
- get_step_grid(), set_step_grid()
- trigger_note()
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    Channel,
    ReadOnlyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_channels_count_and_list(studio: Studio) -> None:
    """Verify channel counting, listing, and individual inspection."""
    fl = studio

    total = fl.channels.count()
    assert isinstance(total, int)
    assert total >= 1

    chans = fl.channels.list()
    assert isinstance(chans, list)
    assert len(chans) == total
    assert chans[0].index == 0
    assert isinstance(chans[0].name, str)
    assert isinstance(chans[0].volume, float)

    c0 = fl.channels.get_channel(0)
    assert isinstance(c0, Channel)
    assert c0.index == 0

    with pytest.raises(ValueError):
        fl.channels.get_channel(-1)


def test_sync_channels_volume_and_pan(studio: Studio) -> None:
    """Verify channel volume and pan with Verified readback contract."""
    fl = studio

    v_vol = fl.channels.set_volume(0, 0.78)
    assert isinstance(v_vol, Verified)
    assert v_vol.requested == 0.78
    assert abs(v_vol.value - 0.78) < 0.05
    assert v_vol.verified is True
    assert v_vol.plane == "live"
    assert v_vol.proof == "readback"
    assert v_vol.fp == fl.fp

    v_pan = fl.channels.set_pan(0, 0.15)
    assert isinstance(v_pan, Verified)
    assert abs(v_pan.value - 0.15) < 0.05
    assert v_pan.verified is True

    # Passing Channel object
    c = fl.channels.get_channel(0)
    v_c_vol = fl.channels.set_volume(c, 0.85)
    assert abs(v_c_vol.value - 0.85) < 0.05


def test_sync_channels_mute_and_solo(studio: Studio) -> None:
    """Verify channel mute and solo operations."""
    fl = studio

    v_mute = fl.channels.mute(0, True)
    assert isinstance(v_mute, Verified)
    assert v_mute.value is True

    v_unmute = fl.channels.mute(0, False)
    assert v_unmute.value is False

    v_solo = fl.channels.solo(0, True)
    assert isinstance(v_solo, Verified)
    assert v_solo.value is True

    v_unsolo = fl.channels.solo(0, False)
    assert v_unsolo.value is False


def test_sync_channels_name_color_pitch(studio: Studio) -> None:
    """Verify channel renaming, color, and pitch tuning."""
    fl = studio

    v_name = fl.channels.set_name(0, "808 Sub")
    assert isinstance(v_name, Verified)
    assert v_name.value == "808 Sub"
    assert fl.channels.get_name(0) == "808 Sub"

    v_col = fl.channels.set_color(0, 0x112233)
    assert isinstance(v_col, Verified)
    assert v_col.value == 0x112233
    assert fl.channels.get_color(0) == 0x112233

    v_pitch = fl.channels.set_pitch(0, 150)
    assert isinstance(v_pitch, Verified)
    assert v_pitch.value == 150
    assert fl.channels.get_pitch(0) == 150


def test_sync_channels_step_grid_and_notes(studio: Studio) -> None:
    """Verify channel 16-step grid querying/updating and note triggering."""
    fl = studio

    initial_grid = fl.channels.get_step_grid(0)
    assert isinstance(initial_grid, list)
    assert len(initial_grid) == 16

    target_grid = [1 if i % 2 == 0 else 0 for i in range(16)]
    v_grid = fl.channels.set_step_grid(0, target_grid)
    assert isinstance(v_grid, Verified)
    assert v_grid.value == target_grid
    assert v_grid.verified is True

    # Read back explicitly
    assert fl.channels.get_step_grid(0) == target_grid

    # Trigger note (returns Verified[bool])
    v_note = fl.channels.trigger_note(0, note=64, vel=90, dur=1)
    assert isinstance(v_note, Verified)
    assert v_note.value is True

    # Invalid step grid length raises ValueError
    with pytest.raises(ValueError):
        fl.channels.set_step_grid(0, [True, False])


def test_sync_channels_readonly_guard(studio_readonly: Studio) -> None:
    """Verify mutating channel methods raise ReadOnlyError in read_only mode."""
    fl = studio_readonly

    # Non-mutating methods succeed
    assert fl.channels.count() >= 1
    assert len(fl.channels.list()) >= 1
    assert fl.channels.get_channel(0).index == 0
    assert len(fl.channels.get_step_grid(0)) == 16

    # Mutating operations fail with ReadOnlyError
    with pytest.raises(ReadOnlyError):
        fl.channels.set_volume(0, 0.5)

    with pytest.raises(ReadOnlyError):
        fl.channels.set_pan(0, 0.0)

    with pytest.raises(ReadOnlyError):
        fl.channels.mute(0, True)

    with pytest.raises(ReadOnlyError):
        fl.channels.solo(0, True)

    with pytest.raises(ReadOnlyError):
        fl.channels.set_name(0, "Lead")

    with pytest.raises(ReadOnlyError):
        fl.channels.set_color(0, 0xFFFFFF)

    with pytest.raises(ReadOnlyError):
        fl.channels.set_pitch(0, 100)

    with pytest.raises(ReadOnlyError):
        fl.channels.trigger_note(0, 60)

    with pytest.raises(ReadOnlyError):
        fl.channels.set_step_grid(0, [False] * 16)


@pytest.mark.anyio
async def test_async_channels_operations(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncChannels operations under anyio."""
    port_sdk, _ = running_emulator
    async with AsyncStudio.connect(
        embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
    ) as fl:
        count = await fl.channels.count()
        assert count >= 1

        v_vol = await fl.channels.set_volume(0, 0.82)
        assert abs(v_vol.value - 0.82) < 0.05

        v_grid = await fl.channels.set_step_grid(0, [1] * 16)
        assert v_grid.value == [1] * 16
        assert v_grid.verified is True
