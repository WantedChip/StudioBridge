"""Unit tests for FL Studio render instance collision policies.

# req: RND-01
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from studiobridge.actuate.win32 import FLWindowInfo
from studiobridge.core.errors import FlRunningError
from studiobridge.render.discover import FlInstall
from studiobridge.render.policy import InstancePolicy, InstancePolicyEnforcer


def make_mock_fl_window(
    hwnd: int = 1001, pid: int = 4242, title: str = "FL Studio 2026"
) -> FLWindowInfo:
    """Helper to construct a mock FLWindowInfo."""
    return FLWindowInfo(
        hwnd=hwnd,
        title=title,
        pid=pid,
        image_path=r"C:\Program Files\Image-Line\FL Studio 2026\FL64.exe",
        is_foreground=True,
    )


def test_policy_require_closed_passes_when_not_running():
    """Verify require_closed passes cleanly when no FL Studio instances are running.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)
    enforcer.enforce(InstancePolicy.REQUIRE_CLOSED)
    mock_wm.find_fl_windows.assert_called_once()


def test_policy_require_closed_fails_when_running():
    """Verify require_closed halts with FlRunningError (E_RND_FLRUNNING) when FL is open.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = [make_mock_fl_window(1001, 4242, "FL Studio 2026")]

    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)

    with pytest.raises(FlRunningError) as exc_info:
        enforcer.enforce(InstancePolicy.REQUIRE_CLOSED)

    assert exc_info.value.code == "E_RND_FLRUNNING"
    assert "interactive FL Studio instance is running" in str(exc_info.value)
    assert exc_info.value.remedy is not None
    assert "Save project and close" in exc_info.value.remedy


def test_policy_close_gracefully_succeeds_when_process_exits():
    """Verify close_gracefully sends WM_CLOSE and passes when process exits within timeout.

    # req: RND-01
    """
    mock_wm = MagicMock()
    # First call returns running window, second call returns empty list (closed)
    mock_wm.find_fl_windows.side_effect = [
        [make_mock_fl_window(1001, 4242)],
        [],
    ]

    enforcer = InstancePolicyEnforcer(
        window_mgr=mock_wm,
        graceful_timeout_s=2.0,
        poll_interval_s=0.01,
    )
    enforcer.enforce(InstancePolicy.CLOSE_GRACEFULLY)


def test_policy_close_gracefully_fails_when_unsaved_changes_block():
    """Verify close_gracefully fails without auto-discarding if FL remains open after timeout.

    # req: RND-01
    """
    mock_wm = MagicMock()
    # Window never closes (simulating unsaved changes prompt requiring user confirmation)
    mock_wm.find_fl_windows.return_value = [make_mock_fl_window(1001, 4242)]

    enforcer = InstancePolicyEnforcer(
        window_mgr=mock_wm,
        graceful_timeout_s=0.05,
        poll_interval_s=0.01,
    )

    with pytest.raises(FlRunningError) as exc_info:
        enforcer.enforce(InstancePolicy.CLOSE_GRACEFULLY)

    assert exc_info.value.code == "E_RND_FLRUNNING"
    assert "did not close gracefully" in str(exc_info.value)
    assert "auto-discarding changes is strictly prohibited" in str(exc_info.value)


def test_policy_force_kill_terminates_running_process(monkeypatch: pytest.MonkeyPatch):
    """Verify force_kill terminates running process and verifies closure.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.side_effect = [
        [make_mock_fl_window(1001, 4242)],
        [],
    ]

    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)

    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)
    enforcer.enforce(InstancePolicy.FORCE_KILL)


def test_unknown_policy_raises_fl_running_error():
    """Verify unknown policy defaults to refusing render when FL is open.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = [make_mock_fl_window(1001, 4242)]

    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)
    with pytest.raises(FlRunningError):
        enforcer.enforce("invalid_policy_name")


def test_is_fl_running_helper():
    """Verify is_fl_running reports boolean status accurately.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []
    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)
    assert enforcer.is_fl_running() is False

    mock_wm.find_fl_windows.return_value = [make_mock_fl_window()]
    assert enforcer.is_fl_running() is True


def test_target_install_filtering():
    """Verify preferred_install parameter targets specific executable path.

    # req: RND-01
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []
    enforcer = InstancePolicyEnforcer(window_mgr=mock_wm)

    install = FlInstall(
        path=Path(r"C:\Program Files\Image-Line\FL Studio 2026"),
        exe_path=Path(r"C:\Program Files\Image-Line\FL Studio 2026\FL64.exe"),
        version_str="26.1.3.5570",
        major=26,
        minor=1,
        build=3,
        revision=5570,
    )
    enforcer.enforce(InstancePolicy.REQUIRE_CLOSED, preferred_install=install)
    mock_wm.find_fl_windows.assert_called_once()
