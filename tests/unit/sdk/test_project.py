"""Unit and integration tests for Project namespace.

Tests both Studio (synchronous) and AsyncStudio (asynchronous) project interfaces:
- get_title(), get_author(), get_comment(), is_dirty(), info()
- save() confirmation guard [SAF-01, SAF-03]
- save_new_version() non-destructive save
- ReadOnlyError enforcement
"""

from __future__ import annotations

import pytest

from studiobridge import (
    AsyncStudio,
    ProjectInfo,
    ProtectedTargetError,
    ReadOnlyError,
    SafetyError,
    Studio,
    Verified,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_project_metadata(studio: Studio) -> None:
    """Verify project title, author, comment, dirty state, and info snapshot."""
    fl = studio

    title = fl.project.get_title()
    assert isinstance(title, str)
    assert len(title) > 0

    author = fl.project.get_author()
    assert isinstance(author, str)

    comment = fl.project.get_comment()
    assert isinstance(comment, str)

    dirty = fl.project.is_dirty()
    assert isinstance(dirty, bool)

    info = fl.project.info()
    assert isinstance(info, ProjectInfo)
    assert info.title == title
    assert info.author == author
    assert info.comment == comment
    assert info.is_dirty == dirty


def test_sync_project_save_guards(studio: Studio) -> None:
    """Verify safety interlocks on save() preventing unprompted overwrites [SAF-01, SAF-03]."""
    fl = studio

    # 1. Unconfirmed save raises ProtectedTargetError (subclass of SafetyError)
    with pytest.raises(ProtectedTargetError) as exc_info:
        fl.project.save()

    err = exc_info.value
    assert isinstance(err, SafetyError)
    assert err.code == "E_PROTECTED"
    assert "explicit confirmation" in err.message

    # 2. Confirmed save with confirm=True succeeds
    v_save = fl.project.save(confirm=True)
    assert isinstance(v_save, Verified)
    assert v_save.value is True
    assert v_save.verified is True
    assert v_save.plane == "live"
    assert v_save.proof == "display_only"

    # 3. Confirmed save with allow_overwrite=True succeeds
    v_ow = fl.project.save(allow_overwrite=True)
    assert v_ow.value is True
    assert v_ow.verified is True


def test_sync_project_save_new_version(studio: Studio) -> None:
    """Verify save_new_version() executes without requiring confirmation per [SAF-03]."""
    fl = studio

    v_new = fl.project.save_new_version()
    assert isinstance(v_new, Verified)
    assert v_new.value is True
    assert v_new.verified is True
    assert v_new.plane == "live"


def test_sync_project_readonly_guard(studio_readonly: Studio) -> None:
    """Verify project mutations are rejected in read-only safety mode per [SAF-01]."""
    fl = studio_readonly

    # Reads succeed in read_only mode
    assert isinstance(fl.project.get_title(), str)
    assert isinstance(fl.project.is_dirty(), bool)

    # save() raises ReadOnlyError in read-only mode even if confirm=True
    with pytest.raises(ReadOnlyError) as exc_info:
        fl.project.save(confirm=True)
    assert exc_info.value.code == "E_READONLY"

    # save_new_version() raises ReadOnlyError in read-only mode
    with pytest.raises(ReadOnlyError) as exc_info:
        fl.project.save_new_version()
    assert exc_info.value.code == "E_READONLY"


@pytest.mark.anyio
async def test_async_project(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncProject asynchronous operations."""
    port_sdk, _ = running_emulator

    async with AsyncStudio.connect(
        embedded=True,
        port=port_sdk,
        secret=sdk_secret,
        mode="write",
    ) as fl:
        title = await fl.project.get_title()
        assert isinstance(title, str)

        # Unconfirmed save raises ProtectedTargetError
        with pytest.raises(ProtectedTargetError):
            await fl.project.save()

        # Confirmed save succeeds
        v_save = await fl.project.save(confirm=True)
        assert v_save.value is True

        # Non-destructive save new version succeeds
        v_new = await fl.project.save_new_version()
        assert v_new.value is True
