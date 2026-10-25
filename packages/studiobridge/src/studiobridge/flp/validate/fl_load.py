"""Headless FL Studio project load verification harness and freeze detection.

Executes automated FL-load test preflight (FL64.exe /R /Ewav) on isolated staged
project copies, monitors process execution under a strict watchdog timer, detects
unresponsive / frozen processes with zero CPU activity, identifies modal dialogs
(blocking or crash), classifies outcomes (ok, blocking_dialog, freeze, crash), and
terminates hung processes reliably with zero zombies per 07_l0e_flp_engine.md §5,
06_l0d_pianoroll_actuation_render.md §10–§13, Spikes S7, S8, S9, and [FLP-50].
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from studiobridge.actuate.win32 import WindowManager
from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.flp.model.project import Project
from studiobridge.render.discover import FlDiscovery, FlInstall
from studiobridge.render.runner import (
    BLOCKING_DIALOG_KEYWORDS,
    CREATE_NEW_PROCESS_GROUP,
    WindowsJobObject,
)

FlLoadOutcome = Literal["ok", "blocking_dialog", "freeze", "crash"]

CRASH_DIALOG_KEYWORDS: list[str] = [
    "crash",
    "fatal",
    "unhandled exception",
    "werfault",
    "access violation",
    "stopped working",
    "runtime error",
    "abnormal termination",
    "exception caught",
]


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


@dataclass(frozen=True, slots=True)
class FlLoadResult:
    """Result of a headless FL Studio project load preflight verification [FLP-50].

    Attributes:
        outcome: Outcome category ('ok', 'blocking_dialog', 'freeze', 'crash').
        exit_code: Subprocess exit code if terminated cleanly or crashed.
        duration_s: Total preflight elapsed time in seconds.
        dialog_title: Detected modal dialog window title, if any.
        error_message: Explanatory error details if failure occurred.
        cpu_activity_detected: True if process consumed measurable CPU time.
        output_generated: True if exported audio preflight artifact was created.
        details: Additional diagnostic telemetry.
    """

    outcome: FlLoadOutcome
    exit_code: int | None
    duration_s: float
    dialog_title: str | None = None
    error_message: str | None = None
    cpu_activity_detected: bool = True
    output_generated: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        """True if the project opened cleanly without freeze, crash, or blocking dialog."""
        return self.outcome == "ok"

    def to_dict(self) -> dict[str, Any]:
        """Convert load result to dictionary representation."""
        return {
            "outcome": self.outcome,
            "is_ok": self.is_ok,
            "exit_code": self.exit_code,
            "duration_s": round(self.duration_s, 3),
            "dialog_title": self.dialog_title,
            "error_message": self.error_message,
            "cpu_activity_detected": self.cpu_activity_detected,
            "output_generated": self.output_generated,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class LiveVerificationResult:
    """Result of live bridge project integrity check against running FL Studio [FLP-50].

    Attributes:
        available: True if an active StudioBridge live session was connected.
        project_loaded: True if project load confirmation was received.
        matches: True if offline object model counts match live FL Studio counts.
        offline_counts: Counts of channels, patterns, and mixer tracks from parsed FLP.
        live_counts: Counts of channels, patterns, and mixer tracks from live FL Studio.
        differences: Descriptions of any discrepancies found.
        message: Informative status summary.
        details: Diagnostic details.
    """

    available: bool
    project_loaded: bool
    matches: bool
    offline_counts: dict[str, int] = field(default_factory=dict)
    live_counts: dict[str, int] = field(default_factory=dict)
    differences: list[str] = field(default_factory=list)
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert live verification result to dictionary representation."""
        return {
            "available": self.available,
            "project_loaded": self.project_loaded,
            "matches": self.matches,
            "offline_counts": dict(self.offline_counts),
            "live_counts": dict(self.live_counts),
            "differences": list(self.differences),
            "message": self.message,
            "details": dict(self.details),
        }


class FlLoadHarness:
    """Automated FL Studio load and freeze detection test harness [FLP-50].

    Validates that FL Studio project (.flp) files open cleanly in real FL Studio
    using headless render preflight (FL64.exe /R /Ewav) without freezing,
    crashing, or blocking on modal dialogs per 07 §5, 06 §10–§13, and Spikes S7, S8.
    """

    def __init__(
        self,
        *,
        fl_install: FlInstall | Path | str | None = None,
        discovery: FlDiscovery | None = None,
        window_mgr: WindowManager | None = None,
        popen_factory: Callable[..., Any] | None = None,
        config: StudioBridgeConfig | None = None,
        poll_interval_s: float = 0.2,
        freeze_cpu_threshold_s: float = 10.0,
        get_process_times: Callable[[int], int | None] | None = None,
        is_hung_window: Callable[[int], bool] | None = None,
    ) -> None:
        """Initialize the load harness with optional dependency injection for testing.

        Args:
            fl_install: Pre-resolved FL Studio installation or executable path.
            discovery: Optional discovery service for locating FL Studio.
            window_mgr: Optional Win32 WindowManager for dialog discovery.
            popen_factory: Optional process launcher factory (default subprocess.Popen).
            config: StudioBridge configuration.
            poll_interval_s: Watchdog poll interval in seconds.
            freeze_cpu_threshold_s: Duration of zero CPU progression before flagging freeze.
            get_process_times: Custom injectable CPU time query callable for testing.
            is_hung_window: Custom injectable hung window query callable for testing.
        """
        self._fl_install_param = fl_install
        self.discovery = discovery or FlDiscovery()
        self.window_mgr = window_mgr or WindowManager()
        self.popen_factory = popen_factory or subprocess.Popen
        self.config = config or load_config()
        self.poll_interval_s = poll_interval_s
        self.freeze_cpu_threshold_s = freeze_cpu_threshold_s
        self._get_process_times_injected = get_process_times
        self._is_hung_window_injected = is_hung_window

    def resolve_install(self) -> FlInstall:
        """Resolve the FL Studio installation to use for load preflight."""
        if isinstance(self._fl_install_param, FlInstall):
            return self._fl_install_param
        if isinstance(self._fl_install_param, (Path, str)):
            return self.discovery.inspect_install(Path(self._fl_install_param))
        if self.config.fl_install_dir:
            return self.discovery.inspect_install(self.config.fl_install_dir)
        return self.discovery.resolve_install()

    def run(
        self,
        project: Project | Path | str,
        *,
        timeout_s: float = 30.0,
    ) -> FlLoadResult:
        """Execute headless FL-load preflight and watchdog freeze detection [FLP-50].

        Stages the project file to an isolated temporary directory with read-only
        permissions, launches FL64.exe /R /Ewav, attaches the process to a Windows
        Job Object, supervises execution with a watchdog timer, and classifies
        outcome as 'ok', 'blocking_dialog', 'freeze', or 'crash'.

        Args:
            project: Project instance, file path, or string path.
            timeout_s: Watchdog timeout in seconds (default 30.0).

        Returns:
            FlLoadResult with classified outcome and diagnostic metrics.
        """
        fl_install = self.resolve_install()

        # Scale timeout under Windows ARM64 Prism emulation (Spike S11)
        is_emulated = fl_install.is_emulated or self.discovery.is_prism_emulated()
        scale = self.config.render.timeout_multiplier if is_emulated else 1.0
        effective_timeout_s = timeout_s * scale

        with tempfile.TemporaryDirectory(prefix="sbridge_load_") as stage_tmp:
            stage_dir = Path(stage_tmp)
            staged_flp = stage_dir / "load_test.flp"
            expected_wav = staged_flp.with_suffix(".wav")

            # Stage file with read-only flag per [RND-02]
            if isinstance(project, Project):
                project.save_as(staged_flp)
            else:
                shutil.copy2(Path(project), staged_flp)

            with contextlib.suppress(Exception):
                os.chmod(staged_flp, stat.S_IREAD)

            job_obj = WindowsJobObject()
            cmd = [
                str(fl_install.exe_path),
                "/R",
                "/Ewav",
                str(staged_flp),
            ]

            flags = CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            start_time = time.time()
            proc = None

            try:
                proc = self.popen_factory(
                    cmd,
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                return FlLoadResult(
                    outcome="crash",
                    exit_code=None,
                    duration_s=0.0,
                    error_message=f"Failed to spawn FL Studio process: {exc}",
                )

            # Assign process to Job Object to guarantee zero zombie child processes
            job_obj.assign_process(proc)

            last_cpu_ticks: int | None = None
            last_cpu_change_time = start_time
            cpu_activity_seen = False
            outcome: FlLoadOutcome | None = None
            dialog_title: str | None = None
            error_message: str | None = None
            exit_code: int | None = None

            try:
                while True:
                    # 1. Check if process terminated
                    poll_res = proc.poll()
                    if poll_res is not None:
                        exit_code = poll_res
                        if exit_code == 0:
                            outcome = "ok"
                        else:
                            outcome = "crash"
                            error_message = (
                                f"FL Studio exited unexpectedly with exit code {exit_code}."
                            )
                        break

                    now = time.time()
                    elapsed = now - start_time

                    # 2. Check modal dialogs (crash or blocking)
                    has_dialog, title, is_crash = self._detect_dialog(proc.pid)
                    if has_dialog:
                        dialog_title = title
                        if is_crash:
                            outcome = "crash"
                            error_message = f"Modal crash dialog detected: '{title}'."
                        else:
                            outcome = "blocking_dialog"
                            error_message = f"Modal blocking dialog detected: '{title}'."
                        self._terminate(proc, job_obj)
                        break

                    # 3. Check hung window via Win32 IsHungAppWindow
                    if self._is_window_hung(proc.pid):
                        outcome = "freeze"
                        error_message = "FL Studio window reported hung (IsHungAppWindow = TRUE)."
                        self._terminate(proc, job_obj)
                        break

                    # 4. Check CPU activity progression
                    cpu_ticks = self._get_process_cpu_ticks(proc.pid)
                    if cpu_ticks is not None:
                        if last_cpu_ticks is None:
                            last_cpu_ticks = cpu_ticks
                        elif cpu_ticks != last_cpu_ticks:
                            last_cpu_ticks = cpu_ticks
                            last_cpu_change_time = now
                            cpu_activity_seen = True
                        elif (
                            elapsed > 5.0
                            and (now - last_cpu_change_time) >= self.freeze_cpu_threshold_s
                        ):
                            outcome = "freeze"
                            error_message = (
                                f"Process hang detected: zero CPU consumption for "
                                f"{self.freeze_cpu_threshold_s:.1f}s while running."
                            )
                            self._terminate(proc, job_obj)
                            break

                    # 5. Watchdog timeout expiration
                    if elapsed >= effective_timeout_s:
                        outcome = "freeze"
                        error_message = (
                            f"Watchdog timeout ({effective_timeout_s:.1f}s) expired "
                            "without process completion."
                        )
                        self._terminate(proc, job_obj)
                        break

                    time.sleep(self.poll_interval_s)

            finally:
                if proc is not None and proc.poll() is None:
                    self._terminate(proc, job_obj)

            duration_s = time.time() - start_time
            output_generated = expected_wav.exists() and expected_wav.stat().st_size > 44

            # If exit code was 0 and output generated, ensure outcome is ok
            if outcome is None:
                outcome = "ok" if (exit_code == 0 or output_generated) else "crash"

            return FlLoadResult(
                outcome=outcome,
                exit_code=exit_code,
                duration_s=duration_s,
                dialog_title=dialog_title,
                error_message=error_message,
                cpu_activity_detected=cpu_activity_seen or (duration_s < 2.0 and exit_code == 0),
                output_generated=output_generated,
                details={
                    "effective_timeout_s": effective_timeout_s,
                    "is_prism_emulated": is_emulated,
                },
            )

    def _detect_dialog(self, render_pid: int) -> tuple[bool, str, bool]:
        """Detect top-level modal dialogs belonging to FL Studio [RND-04].

        Returns:
            Tuple of (has_dialog, dialog_title, is_crash).
        """
        windows = self.window_mgr.find_fl_windows()
        for w in windows:
            if w.pid == render_pid or "fl" in w.image_path.lower():
                title_lower = w.title.lower()

                # Ignore active render progress titles
                if any(k in title_lower for k in ("rendering", "exporting")):
                    continue

                # Check for crash dialog indicators
                for kw in CRASH_DIALOG_KEYWORDS:
                    if kw in title_lower:
                        return True, w.title, True

                # Check for blocking dialog indicators
                for kw in BLOCKING_DIALOG_KEYWORDS:
                    if kw in title_lower:
                        return True, w.title, False

                # Check last active popup child window
                popup_hwnd = self.window_mgr.get_last_active_popup(w.hwnd)
                if popup_hwnd and popup_hwnd != w.hwnd:
                    popup_title = self.window_mgr.get_window_title(popup_hwnd)
                    if popup_title:
                        popup_lower = popup_title.lower()
                        for kw in CRASH_DIALOG_KEYWORDS:
                            if kw in popup_lower:
                                return True, popup_title, True
                        for kw in BLOCKING_DIALOG_KEYWORDS:
                            if kw in popup_lower:
                                return True, popup_title, False

        return False, "", False

    def _is_window_hung(self, render_pid: int) -> bool:
        """Query Win32 IsHungAppWindow to detect unresponsive UI message loop."""
        if self._is_hung_window_injected is not None:
            return self._is_hung_window_injected(render_pid)

        if sys.platform != "win32":
            return False

        try:
            user32 = getattr(self.window_mgr, "_user32", None)
            if user32 and hasattr(user32, "IsHungAppWindow"):
                windows = self.window_mgr.find_fl_windows()
                for w in windows:
                    if w.pid == render_pid and user32.IsHungAppWindow(w.hwnd):
                        return True
        except Exception:
            pass
        return False

    def _get_process_cpu_ticks(self, pid: int) -> int | None:
        """Query kernel32.GetProcessTimes to monitor CPU time consumption."""
        if self._get_process_times_injected is not None:
            return self._get_process_times_injected(pid)

        if sys.platform != "win32":
            return None

        try:
            kernel32 = getattr(self.window_mgr, "_kernel32", None)
            if kernel32 and hasattr(kernel32, "GetProcessTimes"):
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if not h_proc:
                    return None
                try:
                    creation = _FILETIME()
                    exit_time = _FILETIME()
                    kernel_time = _FILETIME()
                    user_time = _FILETIME()
                    res = kernel32.GetProcessTimes(
                        h_proc,
                        ctypes.byref(creation),
                        ctypes.byref(exit_time),
                        ctypes.byref(kernel_time),
                        ctypes.byref(user_time),
                    )
                    if res:
                        k_ticks = (kernel_time.dwHighDateTime << 32) | kernel_time.dwLowDateTime
                        u_ticks = (user_time.dwHighDateTime << 32) | user_time.dwLowDateTime
                        return k_ticks + u_ticks
                finally:
                    kernel32.CloseHandle(h_proc)
        except Exception:
            pass
        return None

    def _terminate(self, proc: Any, job_obj: WindowsJobObject) -> None:
        """Terminate process tree cleanly via Job Object and process kill [RND-03]."""
        with contextlib.suppress(Exception):
            job_obj.close()

        with contextlib.suppress(Exception):
            proc.kill()

        with contextlib.suppress(Exception):
            proc.wait(timeout=2.0)

    def verify_live_bridge(
        self,
        project: Project | Path | str,
        *,
        client: Any = None,
        timeout_s: float = 15.0,
    ) -> LiveVerificationResult:
        """Verify project integrity against active live FL Studio session [07 §5, S8, S9].

        When a live bridge connection is available, verifies project integrity
        by reading live channel, pattern, and mixer counts and comparing them
        with the offline project object model.
        """
        return verify_live_project_load(project, client=client, timeout_s=timeout_s)


def verify_live_project_load(
    project: Project | Path | str,
    *,
    client: Any = None,
    timeout_s: float = 15.0,
) -> LiveVerificationResult:
    """Verify project integrity via live bridge connection [07 §5, Spikes S8, S9, FLP-50].

    Compares offline Project element counts (channels, patterns, mixer) against
    the active FL Studio session state via live SDK namespaces (fl.channels.count(),
    fl.patterns.count(), fl.mixer.track_count()).

    Args:
        project: Project instance or file path.
        client: Optional active Studio client instance or mock.
        timeout_s: Maximum wait duration.

    Returns:
        LiveVerificationResult indicating match status and count comparisons.
    """
    proj = project if isinstance(project, Project) else Project.load(project)

    offline_counts = {
        "channels": len(proj.channels),
        "patterns": len(proj.patterns),
        "mixer": len(proj.mixer),
    }

    # 1. Resolve client
    active_client = client
    is_managed_client = False

    if active_client is None:
        # Check if live broker / FL Studio is available
        from studiobridge.core.paths import get_broker_json_path

        meta_path = get_broker_json_path()
        if not meta_path.exists():
            return LiveVerificationResult(
                available=False,
                project_loaded=False,
                matches=False,
                offline_counts=offline_counts,
                message="No live StudioBridge broker session is currently running.",
            )

        try:
            from studiobridge.sdk.client import Studio

            active_client = Studio.connect(timeout=timeout_s)
            active_client.__enter__()
            is_managed_client = True
        except Exception as exc:
            return LiveVerificationResult(
                available=False,
                project_loaded=False,
                matches=False,
                offline_counts=offline_counts,
                message=f"Failed to connect to live StudioBridge session: {exc}",
            )

    try:
        # 2. Query live counts
        live_channels = 0
        live_patterns = 0
        live_mixer = 0

        ch_ns: Any = getattr(active_client, "channels", None)
        if ch_ns is not None and hasattr(ch_ns, "count"):
            c_res = ch_ns.count()
            if isinstance(c_res, (int, float, str)):
                live_channels = int(c_res)
        else:
            ch_fn: Any = getattr(active_client, "channel_count", None)
            if callable(ch_fn):
                c_res = ch_fn()
                if isinstance(c_res, (int, float, str)):
                    live_channels = int(c_res)

        pat_ns: Any = getattr(active_client, "patterns", None)
        if pat_ns is not None and hasattr(pat_ns, "count"):
            p_res = pat_ns.count()
            if isinstance(p_res, (int, float, str)):
                live_patterns = int(p_res)
        else:
            pat_fn: Any = getattr(active_client, "pattern_count", None)
            if callable(pat_fn):
                p_res = pat_fn()
                if isinstance(p_res, (int, float, str)):
                    live_patterns = int(p_res)

        mix_ns: Any = getattr(active_client, "mixer", None)
        if mix_ns is not None and hasattr(mix_ns, "track_count"):
            m_res = mix_ns.track_count()
            if isinstance(m_res, (int, float, str)):
                live_mixer = int(m_res)
        else:
            mix_fn: Any = getattr(active_client, "track_count", None)
            if callable(mix_fn):
                m_res = mix_fn()
                if isinstance(m_res, (int, float, str)):
                    live_mixer = int(m_res)

        live_counts = {
            "channels": live_channels,
            "patterns": live_patterns,
            "mixer": live_mixer,
        }

        differences: list[str] = []
        for key in ("channels", "patterns", "mixer"):
            exp = offline_counts[key]
            act = live_counts[key]
            if exp != act:
                differences.append(f"{key} count mismatch: offline={exp}, live={act}")

        matches = len(differences) == 0
        msg = (
            "Live FL Studio counts matched offline project model."
            if matches
            else (
                "Discrepancies detected between live FL Studio and offline project: "
                f"{'; '.join(differences)}"
            )
        )

        return LiveVerificationResult(
            available=True,
            project_loaded=True,
            matches=matches,
            offline_counts=offline_counts,
            live_counts=live_counts,
            differences=differences,
            message=msg,
        )

    finally:
        if is_managed_client and active_client is not None:
            with contextlib.suppress(Exception):
                active_client.__exit__(None, None, None)
