"""Unit and integration tests for UI namespace.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) UI interfaces:
- focus(window)
- hint(text)
- show(window), hide(window)
- is_focused(window), is_visible(window)
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    ReadOnlyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_ui_focus(studio: Studio) -> None:
    """Verify window focus and query."""
    fl = studio

    v_focus = fl.ui.focus(1)
    assert isinstance(v_focus, Verified)
    assert v_focus.value is True
    assert v_focus.verified is True
    assert v_focus.plane == "live"
    assert v_focus.proof == "readback"

    assert fl.ui.is_focused(1) is True
    assert fl.ui.is_focused(2) is False


def test_sync_ui_visibility(studio: Studio) -> None:
    """Verify window show and hide controls with read-back verification."""
    fl = studio

    # Show window 2 (Playlist)
    v_show = fl.ui.show(2)
    assert isinstance(v_show, Verified)
    assert v_show.value is True
    assert fl.ui.is_visible(2) is True

    # Hide window 2
    v_hide = fl.ui.hide(2)
    assert isinstance(v_hide, Verified)
    assert v_hide.value is True
    assert fl.ui.is_visible(2) is False


def test_sync_ui_hint(studio: Studio) -> None:
    """Verify hint text dispatch executes cleanly without error."""
    fl = studio

    # Hint call executes cleanly without error
    fl.ui.hint("StudioBridge: Active Session")


def test_sync_ui_readonly_guard(studio_readonly: Studio) -> None:
    """Verify UI mutating operations raise ReadOnlyError in read-only mode."""
    fl = studio_readonly

    # Queries succeed in read-only mode
    assert isinstance(fl.ui.is_focused(0), bool)
    assert isinstance(fl.ui.is_visible(0), bool)

    # Mutating UI operations raise ReadOnlyError per [SAF-01]
    with pytest.raises(ReadOnlyError):
        fl.ui.focus(1)

    with pytest.raises(ReadOnlyError):
        fl.ui.show(2)

    with pytest.raises(ReadOnlyError):
        fl.ui.hide(2)

    with pytest.raises(ReadOnlyError):
        fl.ui.hint("Exploit")


@pytest.mark.anyio
async def test_async_ui(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncUi asynchronous operations."""
    port_sdk, _ = running_emulator

    async with AsyncStudio.connect(
        embedded=True,
        port=port_sdk,
        secret=sdk_secret,
        mode="write",
    ) as fl:
        v_focus = await fl.ui.focus(0)
        assert v_focus.value is True
        assert await fl.ui.is_focused(0) is True

        v_show = await fl.ui.show(2)
        assert v_show.value is True
        assert await fl.ui.is_visible(2) is True

        v_hide = await fl.ui.hide(2)
        assert v_hide.value is True
        assert await fl.ui.is_visible(2) is False

        await fl.ui.hint("Async hint notification")
