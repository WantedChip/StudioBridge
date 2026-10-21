"""Unit and integration tests for Plugins namespace per 09_l1_sdk.md §4 and v0.2.5.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) plugins interfaces:
- get_plugin(track, slot), list_plugins(track)
- get_param(track, slot, param_id), set_param(track, slot, param_id, val)
- Slot identity reference
- Strict verification and tolerance comparison
- ReadOnlyError enforcement in read-only mode
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    PluginInfo,
    PluginParam,
    ReadOnlyError,
    Slot,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_plugins_get_and_list(studio: Studio) -> None:
    """Verify plugin inspection and slot listing."""
    fl = studio

    # 1. Inspect existing master slot 0 plugin (Fruity Limiter)
    plug = fl.plugins.get_plugin(0, 0)
    assert isinstance(plug, PluginInfo)
    assert plug.track == 0
    assert plug.slot == 0
    assert plug.name == "Fruity Limiter"
    assert plug.is_valid is True
    assert plug.param_count >= 4
    assert plug.preset_count >= 1

    # 2. Inspect with Slot identity type
    plug_slot = fl.plugins.get_plugin(Slot(0, 0))
    assert plug_slot.name == "Fruity Limiter"
    assert plug_slot.is_valid is True

    # 3. Inspect unoccupied slot
    empty = fl.plugins.get_plugin(0, 9)
    assert isinstance(empty, PluginInfo)
    assert empty.is_valid is False

    # 4. List plugins on track 0
    track0_plugins = fl.plugins.list_plugins(0)
    assert isinstance(track0_plugins, list)
    assert len(track0_plugins) >= 1
    assert track0_plugins[0].name == "Fruity Limiter"

    # Track 1 has Fruity Parametric EQ 2
    track1_plugins = fl.plugins.list_plugins(1)
    assert len(track1_plugins) >= 1
    assert track1_plugins[0].name == "Fruity Parametric EQ 2"


def test_sync_plugins_param_get_and_set(studio: Studio) -> None:
    """Verify plugin parameter reading and verified mutating write."""
    fl = studio

    # 1. Read parameter 0 (Ceiling) on track 0 slot 0
    param0 = fl.plugins.get_param(0, 0, 0)
    assert isinstance(param0, PluginParam)
    assert param0.track == 0
    assert param0.slot == 0
    assert param0.param_id == 0
    assert param0.name == "Ceiling"
    assert param0.value == pytest.approx(0.9, rel=0.01)

    # 2. Set parameter with read-back verification
    v_param = fl.plugins.set_param(0, 0, 0, 0.75)
    assert isinstance(v_param, Verified)
    assert v_param.value == pytest.approx(0.75, rel=0.01)
    assert v_param.requested == 0.75
    assert v_param.verified is True
    assert v_param.plane == "live"
    assert v_param.proof == "readback"
    assert v_param.fp == fl.fp

    # 3. Read back to confirm mutation
    param_after = fl.plugins.get_param(0, 0, 0)
    assert param_after.value == pytest.approx(0.75, rel=0.01)

    # 4. Set using Slot identity object
    v_slot = fl.plugins.set_param(Slot(0, 0), 1, 0.6)
    assert isinstance(v_slot, Verified)
    assert v_slot.value == pytest.approx(0.6, rel=0.01)
    assert fl.plugins.get_param(Slot(0, 0), 1).value == pytest.approx(0.6, rel=0.01)


def test_sync_plugins_strict_verification(studio: Studio) -> None:
    """Verify strict write verification on plugin parameter updates."""
    fl = studio

    v = fl.plugins.set_param(1, 0, 0, 0.35, strict=True)
    assert v.verified is True
    assert v.value == pytest.approx(0.35, rel=0.01)


def test_sync_plugins_readonly_guard(studio_readonly: Studio) -> None:
    """Verify mutating plugin calls raise ReadOnlyError in read-only mode."""
    fl = studio_readonly

    # Reading parameters is allowed in read-only mode
    param = fl.plugins.get_param(0, 0, 0)
    assert isinstance(param, PluginParam)

    # Mutating parameters raises ReadOnlyError per [SAF-01]
    with pytest.raises(ReadOnlyError) as exc_info:
        fl.plugins.set_param(0, 0, 0, 0.5)

    err = exc_info.value
    assert err.code == "E_READONLY"
    assert "read-only mode" in err.message


@pytest.mark.anyio
async def test_async_plugins(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncPlugins asynchronous operations."""
    port_sdk, _ = running_emulator

    async with AsyncStudio.connect(
        embedded=True,
        port=port_sdk,
        secret=sdk_secret,
        mode="write",
    ) as fl:
        plug = await fl.plugins.get_plugin(0, 0)
        assert plug.name == "Fruity Limiter"

        param = await fl.plugins.get_param(0, 0, 2)
        assert param.name == "Attack"

        v_write = await fl.plugins.set_param(0, 0, 2, 0.45)
        assert isinstance(v_write, Verified)
        assert v_write.value == pytest.approx(0.45, rel=0.01)
        assert v_write.verified is True
