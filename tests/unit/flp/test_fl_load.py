"""Unit tests for headless FL-load verification harness and freeze watchdog.

Validates process supervision, freeze detection, modal dialog detection,
watchdog timeout termination, outcome classification, and live bridge verification
per 07_l0e_flp_engine.md §5, 06_l0d §10–§13, and [FLP-50].
# req: FLP-50
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from studiobridge.actuate.win32 import FLWindowInfo
from studiobridge.flp.templates.instantiator import instantiate_project
from studiobridge.flp.validate.fl_load import (
    FlLoadHarness,
    FlLoadResult,
    LiveVerificationResult,
    verify_live_project_load,
)
from studiobridge.render.discover import FlInstall


class _MockProcess:
    """Mock process object for simulating subprocess.Popen lifecycle."""

    def __init__(
        self,
        exit_code: int | None = None,
        delay_exit_s: float = 0.0,
        pid: int = 12345,
        create_wav_on_exit: bool = False,
    ) -> None:
        self._exit_code = exit_code
        self._delay_exit_s = delay_exit_s
        self.pid = pid
        self._created_at = time.time()
        self._is_killed = False
        self._create_wav_on_exit = create_wav_on_exit
        self._cmd: list[str] = []

    def poll(self) -> int | None:
        if self._is_killed:
            return -9
        if time.time() - self._created_at >= self._delay_exit_s:
            if self._create_wav_on_exit and self._cmd and len(self._cmd) > 3:
                flp_path = Path(self._cmd[3])
                wav_path = flp_path.with_suffix(".wav")
                wav_path.write_bytes(b"RIFF" + b"\x00" * 40 + b"WAVEfmt ")
            return self._exit_code
        return None

    def kill(self) -> None:
        self._is_killed = True

    def terminate(self) -> None:
        self._is_killed = True

    def wait(self, timeout: float | None = None) -> int:
        return self._exit_code if self._exit_code is not None else 0


@pytest.fixture
def fake_install(tmp_path: Path) -> FlInstall:
    """Fixture providing a mock FL Studio installation."""
    exe = tmp_path / "FL64.exe"
    exe.write_bytes(b"MZfake_fl_exe")
    return FlInstall(
        path=tmp_path,
        exe_path=exe,
        version_str="26.1.3.5570",
        major=26,
        minor=1,
        build=3,
        revision=5570,
        architecture="x64",
        is_emulated=False,
    )


def test_harness_clean_run_yields_ok(fake_install: FlInstall) -> None:
    """A project running and exiting with code 0 generates outcome 'ok'.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        proc = _MockProcess(exit_code=0, delay_exit_s=0.05, create_wav_on_exit=True)
        proc._cmd = cmd
        return proc

    harness = FlLoadHarness(
        fl_install=fake_install,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
    )

    res = harness.run(project, timeout_s=5.0)
    assert isinstance(res, FlLoadResult)
    assert res.outcome == "ok"
    assert res.is_ok is True
    assert res.exit_code == 0
    assert res.output_generated is True
    assert res.dialog_title is None
    assert res.error_message is None


def test_harness_detects_blocking_dialog(fake_install: FlInstall) -> None:
    """Modal dialogs such as missing sample dialogs are classified as 'blocking_dialog'.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    # Mock window manager reporting a blocking dialog window
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = [
        FLWindowInfo(
            hwnd=101,
            title="Some Missing Sample Could Not Be Found",
            pid=12345,
            image_path=str(fake_install.exe_path),
            is_foreground=True,
        )
    ]
    mock_wm.get_last_active_popup.return_value = None

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return _MockProcess(exit_code=None, delay_exit_s=10.0, pid=12345)

    harness = FlLoadHarness(
        fl_install=fake_install,
        window_mgr=mock_wm,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
    )

    res = harness.run(project, timeout_s=2.0)
    assert res.outcome == "blocking_dialog"
    assert res.is_ok is False
    assert res.dialog_title == "Some Missing Sample Could Not Be Found"
    assert "blocking dialog detected" in str(res.error_message).lower()


def test_harness_detects_modal_crash_dialog(fake_install: FlInstall) -> None:
    """Modal crash dialogs (e.g. fatal access violation) are classified as 'crash'.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = [
        FLWindowInfo(
            hwnd=102,
            title="FL Studio Crash: Fatal Access Violation",
            pid=12345,
            image_path=str(fake_install.exe_path),
            is_foreground=True,
        )
    ]
    mock_wm.get_last_active_popup.return_value = None

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return _MockProcess(exit_code=None, delay_exit_s=10.0, pid=12345)

    harness = FlLoadHarness(
        fl_install=fake_install,
        window_mgr=mock_wm,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
    )

    res = harness.run(project, timeout_s=2.0)
    assert res.outcome == "crash"
    assert res.is_ok is False
    assert "access violation" in str(res.dialog_title).lower()


def test_harness_detects_crash_exit_code(fake_install: FlInstall) -> None:
    """Non-zero crash exit codes are classified as 'crash'.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return _MockProcess(exit_code=1, delay_exit_s=0.05)

    harness = FlLoadHarness(
        fl_install=fake_install,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
    )

    res = harness.run(project, timeout_s=2.0)
    assert res.outcome == "crash"
    assert res.is_ok is False
    assert res.exit_code == 1


def test_harness_watchdog_terminates_hung_process(fake_install: FlInstall) -> None:
    """Watchdog timer timeout terminates hung process and classifies outcome as 'freeze'.

    # req: FLP-50
    """
    project = instantiate_project("minimal")
    proc = _MockProcess(exit_code=None, delay_exit_s=60.0)

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return proc

    harness = FlLoadHarness(
        fl_install=fake_install,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
    )

    start = time.time()
    res = harness.run(project, timeout_s=0.1)
    duration = time.time() - start

    assert res.outcome == "freeze"
    assert res.is_ok is False
    assert proc._is_killed is True  # Terminated reliably
    assert "watchdog timeout" in str(res.error_message).lower()
    assert duration < 2.0  # Terminated promptly


def test_harness_detects_zero_cpu_freeze(fake_install: FlInstall) -> None:
    """Process hanging with zero CPU consumption triggers freeze outcome.

    # req: FLP-50
    """
    project = instantiate_project("minimal")
    proc = _MockProcess(exit_code=None, delay_exit_s=10.0)

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return proc

    # CPU ticks return a static constant value (0 CPU progression)
    harness = FlLoadHarness(
        fl_install=fake_install,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
        freeze_cpu_threshold_s=0.05,
        get_process_times=lambda pid: 1000,  # Static CPU ticks
    )

    # Fake elapsed time > 5.0 in loop by using a short threshold
    res = harness.run(project, timeout_s=0.2)
    assert res.outcome == "freeze"
    assert proc._is_killed is True


def test_harness_detects_hung_window(fake_install: FlInstall) -> None:
    """Win32 IsHungAppWindow flag triggers immediate freeze classification.

    # req: FLP-50
    """
    project = instantiate_project("minimal")
    proc = _MockProcess(exit_code=None, delay_exit_s=10.0)

    def popen_factory(cmd: list[str], **kwargs: Any) -> Any:
        return proc

    harness = FlLoadHarness(
        fl_install=fake_install,
        popen_factory=popen_factory,
        poll_interval_s=0.01,
        is_hung_window=lambda pid: True,  # Reported hung
    )

    res = harness.run(project, timeout_s=5.0)
    assert res.outcome == "freeze"
    assert "hung" in str(res.error_message).lower()
    assert proc._is_killed is True


def test_live_bridge_verification_matches() -> None:
    """Live bridge verification hook confirms project counts when matching.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    # Mock live client returning exact project counts
    mock_client = MagicMock()
    mock_client.channels.count.return_value = len(project.channels)
    mock_client.patterns.count.return_value = len(project.patterns)
    mock_client.mixer.track_count.return_value = len(project.mixer)

    res = verify_live_project_load(project, client=mock_client)
    assert isinstance(res, LiveVerificationResult)
    assert res.available is True
    assert res.matches is True
    assert len(res.differences) == 0
    assert "matched" in res.message.lower()


def test_live_bridge_verification_detects_mismatch() -> None:
    """Live bridge verification hook detects count discrepancies between live FL and offline model.

    # req: FLP-50
    """
    project = instantiate_project("minimal")

    mock_client = MagicMock()
    mock_client.channels.count.return_value = 99  # Mismatch!
    mock_client.patterns.count.return_value = len(project.patterns)
    mock_client.mixer.track_count.return_value = len(project.mixer)

    res = verify_live_project_load(project, client=mock_client)
    assert res.available is True
    assert res.matches is False
    assert len(res.differences) >= 1
    assert any("channels count mismatch" in d for d in res.differences)
