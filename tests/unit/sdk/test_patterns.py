"""Unit and integration tests for Patterns namespace.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) patterns interfaces:
- count(), list(), get_active()
- set_active(), jump() with 1-based indexing
- set_name(), set_color()
- clear(), get_length()
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    Pattern,
    ReadOnlyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_patterns_count_and_list(studio: Studio) -> None:
    """Verify pattern counting, listing, and length inspection."""
    fl = studio

    total = fl.patterns.count()
    assert isinstance(total, int)
    assert total >= 1

    pats = fl.patterns.list()
    assert isinstance(pats, list)
    assert len(pats) == total
    assert pats[0].index == 1  # 1-based index per FL Studio conventions

    active = fl.patterns.get_active()
    assert isinstance(active, Pattern)
    assert active.index >= 1

    length = fl.patterns.get_length(1)
    assert isinstance(length, int)
    assert length > 0

    # 0 or negative index raises ValueError (FL patterns are 1-based)
    with pytest.raises(ValueError):
        fl.patterns.set_active(0)

    with pytest.raises(ValueError):
        fl.patterns.get_length(-1)


def test_sync_patterns_selection_and_jump(studio: Studio) -> None:
    """Verify active pattern selection and jump navigation."""
    fl = studio

    v_act2 = fl.patterns.set_active(2)
    assert isinstance(v_act2, Verified)
    assert v_act2.value == 2
    assert v_act2.requested == 2
    assert v_act2.verified is True
    assert v_act2.plane == "live"
    assert v_act2.proof == "readback"
    assert v_act2.fp == fl.fp

    assert fl.patterns.get_active().index == 2

    # Jump to pattern 1
    v_jump = fl.patterns.jump(1)
    assert isinstance(v_jump, Verified)
    assert v_jump.value == 1
    assert fl.patterns.get_active().index == 1

    # Pass Pattern dataclass
    pat = fl.patterns.get_active()
    v_pat = fl.patterns.set_active(pat)
    assert v_pat.value == pat.index


def test_sync_patterns_name_and_color(studio: Studio) -> None:
    """Verify pattern renaming and color assignment."""
    fl = studio

    v_name = fl.patterns.set_name(1, "Chorus Drop")
    assert isinstance(v_name, Verified)
    assert v_name.value == "Chorus Drop"
    assert fl.patterns.get_name(1) == "Chorus Drop"

    v_col = fl.patterns.set_color(1, 0xABCDEF)
    assert isinstance(v_col, Verified)
    assert v_col.value == 0xABCDEF
    assert fl.patterns.get_color(1) == 0xABCDEF


def test_sync_patterns_clear(studio: Studio) -> None:
    """Verify pattern content clearing."""
    fl = studio

    v_clr = fl.patterns.clear(1)
    assert isinstance(v_clr, Verified)
    assert v_clr.value is True


def test_sync_patterns_readonly_guard(studio_readonly: Studio) -> None:
    """Verify mutating pattern methods raise ReadOnlyError in read_only mode."""
    fl = studio_readonly

    # Non-mutating methods succeed
    assert fl.patterns.count() >= 1
    assert len(fl.patterns.list()) >= 1
    assert fl.patterns.get_active().index >= 1
    assert fl.patterns.get_length(1) > 0

    # Mutating operations fail with ReadOnlyError
    with pytest.raises(ReadOnlyError):
        fl.patterns.set_active(2)

    with pytest.raises(ReadOnlyError):
        fl.patterns.jump(2)

    with pytest.raises(ReadOnlyError):
        fl.patterns.set_name(1, "Hook")

    with pytest.raises(ReadOnlyError):
        fl.patterns.set_color(1, 0xFFFFFF)

    with pytest.raises(ReadOnlyError):
        fl.patterns.clear(1)


@pytest.mark.anyio
async def test_async_patterns_operations(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncPatterns operations under anyio."""
    port_sdk, _ = running_emulator
    async with AsyncStudio.connect(
        embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
    ) as fl:
        count = await fl.patterns.count()
        assert count >= 1

        v_act = await fl.patterns.set_active(2)
        assert v_act.value == 2

        v_name = await fl.patterns.set_name(2, "Bridge Section")
        assert v_name.value == "Bridge Section"
