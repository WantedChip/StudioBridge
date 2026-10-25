"""Unit tests for ActuationGuards: foreground focus, modal popups, and user idle checks [ACT-10]."""

from __future__ import annotations

from typing import Any

import pytest

from studiobridge.actuate.guards import ActuationGuards
from studiobridge.actuate.win32 import WindowManager
from studiobridge.core.errors import (
    FocusGuardError,
    ModalBlockedError,
    UserInputActiveError,
    WindowNotFoundError,
)
from tests.unit.actuate.test_win32 import MockKernel32, MockUser32


class MockGuardsUser32(MockUser32):
    """Extended MockUser32 with simulated human input idle timer."""

    def __init__(self) -> None:
        super().__init__()
        self.last_input_time_tick: int = 100000

    def GetLastInputInfo(self, info_ptr: Any) -> int:
        if info_ptr is not None:
            if hasattr(info_ptr, "_obj"):
                info_ptr._obj.dwTime = self.last_input_time_tick
            elif hasattr(info_ptr, "contents"):
                info_ptr.contents.dwTime = self.last_input_time_tick
        return 1


class MockGuardsKernel32(MockKernel32):
    """Extended MockKernel32 with simulated system tick counter."""

    def __init__(self) -> None:
        super().__init__()
        self.current_tick: int = 100000

    def GetTickCount64(self) -> int:
        return self.current_tick

    def GetTickCount(self) -> int:
        return self.current_tick & 0xFFFFFFFF


@pytest.fixture
def guards_fixture() -> tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards]:
    u32 = MockGuardsUser32()
    k32 = MockGuardsKernel32()

    # Register FL Studio process and window
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    u32.add_window(101, "FL Studio 2024", 1234, is_visible=True, is_enabled=True)
    k32.current_tick = 110000
    u32.last_input_time_tick = 100000  # 10s idle by default

    wm = WindowManager(user32=u32, kernel32=k32)
    guards = ActuationGuards(
        wm,
        user32=u32,
        kernel32=k32,
        user_idle_threshold_ms=1000.0,
    )
    return u32, k32, guards


def test_guard_window_validity(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify window validity guard checks [ACT-10].

    # req: ACT-10
    """
    _u32, _k32, guards = guards_fixture

    # Valid window handle
    res = guards.check_window_valid(101)
    assert res.passed is True

    # Invalid handle
    res_bad = guards.check_window_valid(99999)
    assert res_bad.passed is False
    assert "invalid" in res_bad.reason.lower()

    # ensure_ready raises WindowNotFoundError
    with pytest.raises(WindowNotFoundError) as exc_info:
        guards.ensure_ready(99999)
    assert "99999" in str(exc_info.value)


def test_guard_foreground_focus_check(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify foreground guard aborts when FL Studio is not the active window [ACT-10].

    # req: ACT-10
    """
    u32, _k32, guards = guards_fixture

    # Active window is something else
    u32.foreground_hwnd = 555
    res = guards.check_foreground(101, allow_focus_steal=False)
    assert res.passed is False
    assert "not the active foreground window" in res.reason

    # ensure_ready raises FocusGuardError when allow_focus_steal=False
    with pytest.raises(FocusGuardError) as exc_info:
        guards.ensure_ready(101, allow_focus_steal=False)
    assert "not the active foreground window" in str(exc_info.value)

    # When allow_focus_steal=True, check passes
    res_stolen = guards.check_foreground(101, allow_focus_steal=True)
    assert res_stolen.passed is True
    assert res_stolen.details.get("focus_steal_allowed") is True

    # When FL Studio is foreground, check passes cleanly
    u32.foreground_hwnd = 101
    res_fg = guards.check_foreground(101, allow_focus_steal=False)
    assert res_fg.passed is True
    assert res_fg.details.get("is_foreground") is True


def test_guard_modal_popup_detection_via_get_last_active_popup(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify modal detection when GetLastActivePopup reports a child modal dialog [ACT-10].

    # req: ACT-10
    """
    u32, _k32, guards = guards_fixture
    u32.foreground_hwnd = 101

    # Add open modal popup window
    u32.add_window(777, "Missing Samples Dialog", 1234, is_visible=True, is_enabled=True)
    # Set popup handle on parent window
    u32.windows[101]["popup"] = 777

    res = guards.check_modal_popup(101)
    assert res.passed is False
    assert "Missing Samples Dialog" in res.reason
    assert res.details.get("blocking_hwnd") == 777

    # ensure_ready raises ModalBlockedError
    with pytest.raises(ModalBlockedError) as exc_info:
        guards.ensure_ready(101)
    assert "Missing Samples Dialog" in str(exc_info.value)


def test_guard_modal_popup_detection_via_enabled_popup(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify modal detection when GW_ENABLEDPOPUP reports an active popup [ACT-10].

    # req: ACT-10
    """
    u32, _k32, guards = guards_fixture
    u32.foreground_hwnd = 101

    # Add open enabled popup dialog
    u32.add_window(888, "Export Error Alert", 1234, is_visible=True, is_enabled=True)
    u32.windows[101]["enabled_popup"] = 888

    res = guards.check_modal_popup(101)
    assert res.passed is False
    assert "Export Error Alert" in res.reason
    assert res.details.get("blocking_hwnd") == 888

    with pytest.raises(ModalBlockedError):
        guards.ensure_ready(101)


def test_guard_modal_popup_detection_via_disabled_main_window(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify modal detection when main FL window is disabled by a system modal dialog [ACT-10].

    # req: ACT-10
    """
    u32, _k32, guards = guards_fixture
    u32.foreground_hwnd = 101

    # Main window disabled (classic Win32 modal state)
    u32.windows[101]["is_enabled"] = False
    u32.add_window(999, "Save Changes?", 1234, is_visible=True)
    u32.windows[101]["popup"] = 999

    res = guards.check_modal_popup(101)
    assert res.passed is False
    assert "Save Changes?" in res.reason
    assert res.details.get("main_enabled") is False

    with pytest.raises(ModalBlockedError):
        guards.ensure_ready(101)


def test_guard_user_idle_detection_and_force_override(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify user idle guard detects recent human typing and supports force override [ACT-10].

    # req: ACT-10
    """
    u32, k32, guards = guards_fixture
    u32.foreground_hwnd = 101

    # Simulate recent input: current time = 100,500ms, last input = 100,200ms -> idle = 300ms
    k32.current_tick = 100500
    u32.last_input_time_tick = 100200

    # Guard fails because idle (300ms) < threshold (1000ms)
    res = guards.check_user_idle(threshold_ms=1000.0, force=False)
    assert res.passed is False
    assert "300ms" in res.reason
    assert res.details.get("idle_ms") == 300.0

    with pytest.raises(UserInputActiveError) as exc_info:
        guards.ensure_ready(101, force=False)
    assert "User input was detected" in str(exc_info.value)

    # When force=True, guard passes cleanly despite recent typing
    res_forced = guards.check_user_idle(threshold_ms=1000.0, force=True)
    assert res_forced.passed is True
    assert res_forced.details.get("forced") is True

    # When user has been idle for 2000ms > threshold (1000ms), check passes normally
    k32.current_tick = 102200
    res_idle = guards.check_user_idle(threshold_ms=1000.0, force=False)
    assert res_idle.passed is True
    assert res_idle.details.get("idle_ms") == 2000.0


def test_guard_verify_all_aggregates_all_checks(
    guards_fixture: tuple[MockGuardsUser32, MockGuardsKernel32, ActuationGuards],
) -> None:
    """Verify verify_all aggregates results across validity, modal, idle, and focus [ACT-10].

    # req: ACT-10
    """
    u32, k32, guards = guards_fixture
    u32.foreground_hwnd = 101
    k32.current_tick = 110000
    u32.last_input_time_tick = 100000  # 10s idle

    results = guards.verify_all(101, allow_focus_steal=False, force=False)
    assert len(results) == 4
    names = [r.guard_name for r in results]
    assert "window_valid" in names
    assert "modal_popup" in names
    assert "user_idle" in names
    assert "foreground" in names
    assert all(r.passed for r in results)
