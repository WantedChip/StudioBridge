"""Headless FL Studio render process supervisor and runner.

Launches FL Studio headless render (FL64.exe /R /E... staged_flp), supervises execution
under a Windows Job Object to guarantee zero zombie child processes, detects blocking
modal dialogs (missing plugins, project info popups), monitors file growth for idle
timeouts, and scales timeouts under Windows ARM64 Prism emulation.
Requirements: [RND-01], [RND-02], [RND-03], [RND-04], 06_l0d_pianoroll_actuation_render.md §9-§13.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import Any

from studiobridge.actuate.win32 import WindowManager
from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.core.errors import (
    BlockingDialogError,
    FlRunningError,
    RenderError,
    RenderTimeoutError,
)
from studiobridge.core.paths import get_jobs_dir
from studiobridge.render.discover import FlDiscovery, FlInstall
from studiobridge.render.job import JobState, RenderJob, RenderJobLock
from studiobridge.render.policy import InstancePolicyEnforcer

# Windows Job Object Win32 Constants & Structures
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: int = 0x2000
JobObjectExtendedLimitInformation: int = 9
CREATE_NEW_PROCESS_GROUP: int = 0x00000200


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class WindowsJobObject:
    """Manages a Windows Job Object configured with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.

    Guarantees zero zombie child processes when the parent process exits, crashes,
    or cancels the render job.
    """

    def __init__(self) -> None:
        self.handle: int | None = None
        self._kernel32: ctypes.WinDLL | None = None
        if sys.platform == "win32":
            with contextlib.suppress(Exception):
                self._kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
                self._init_job()

    def _init_job(self) -> None:
        if not self._kernel32:
            return
        try:
            self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            self._kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
            self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            self._kernel32.TerminateJobObject.restype = wintypes.BOOL
            self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self._kernel32.CloseHandle.restype = wintypes.BOOL

            h_job = self._kernel32.CreateJobObjectW(None, None)
            if h_job:
                info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                res = self._kernel32.SetInformationJobObject(
                    h_job,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                if res:
                    self.handle = h_job
                else:
                    self._kernel32.CloseHandle(h_job)
        except Exception:
            self.handle = None

    def assign_process(self, proc: subprocess.Popen[Any]) -> bool:
        """Assign child process to this Job Object."""
        if not self._kernel32 or not self.handle:
            return False
        try:
            # On Windows, proc._handle is the OS handle
            h_process = getattr(proc, "_handle", None)
            if h_process:
                return bool(self._kernel32.AssignProcessToJobObject(self.handle, int(h_process)))
            # Fallback: open process via PID
            h_opened = self._kernel32.OpenProcess(0x1F0FFF, False, proc.pid)
            if h_opened:
                res = bool(self._kernel32.AssignProcessToJobObject(self.handle, h_opened))
                self._kernel32.CloseHandle(h_opened)
                return res
            return False
        except Exception:
            return False

    def terminate(self, exit_code: int = 1) -> None:
        """Terminate all processes in this Job Object."""
        if self._kernel32 and self.handle:
            with contextlib.suppress(Exception):
                self._kernel32.TerminateJobObject(self.handle, exit_code)

    def close(self) -> None:
        """Close Job Object handle.

        Because JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE is set, closing this handle
        terminates all child processes in the job object.
        """
        if self._kernel32 and self.handle:
            with contextlib.suppress(Exception):
                self._kernel32.CloseHandle(self.handle)
            self.handle = None


BLOCKING_DIALOG_KEYWORDS: list[str] = [
    "missing",
    "project info",
    "could not be found",
    "cannot find",
    "not found",
    "error",
    "warning",
    "attention",
    "locate sample",
    "registration",
    "trial",
    "unsaved",
]


class RenderRunner:
    """Supervised runner for headless FL Studio export jobs.

    Handles preflight, isolated staging, instance collision policy enforcement,
    process tree management via Windows Job Objects, blocking modal dialog detection,
    and output collection.
    """

    def __init__(
        self,
        config: StudioBridgeConfig | None = None,
        discovery: FlDiscovery | None = None,
        window_mgr: WindowManager | None = None,
        policy_enforcer: InstancePolicyEnforcer | None = None,
        popen_factory: Callable[..., Any] | None = None,
        poll_interval_s: float = 0.5,
    ) -> None:
        self.config = config or load_config()
        self.discovery = discovery or FlDiscovery()
        self.window_mgr = window_mgr or WindowManager()
        self.policy_enforcer = policy_enforcer or InstancePolicyEnforcer(self.window_mgr)
        self.popen_factory = popen_factory or subprocess.Popen
        self.poll_interval_s = poll_interval_s

    def resolve_fl_install(self, job: RenderJob) -> FlInstall:
        """Resolve the FL Studio installation for a given job."""
        if isinstance(job.fl_install, FlInstall):
            return job.fl_install
        if isinstance(job.fl_install, (Path, str)):
            return self.discovery.inspect_install(Path(job.fl_install))
        if self.config.fl_install_dir:
            return self.discovery.inspect_install(self.config.fl_install_dir)
        return self.discovery.resolve_install()

    def detect_blocking_dialog(self, render_pid: int) -> tuple[bool, str]:
        """Poll top-level window titles to detect blocking modal dialogs [RND-04].

        Returns:
            Tuple of (is_blocking, dialog_title).
        """
        windows = self.window_mgr.find_fl_windows()
        for w in windows:
            # Check windows belonging to render process or any FL modal window
            if w.pid == render_pid or "fl" in w.image_path.lower():
                title_lower = w.title.lower()
                # Skip normal render progress indications
                if any(k in title_lower for k in ("rendering", "exporting")):
                    continue

                # Check for blocking dialog title keywords
                for kw in BLOCKING_DIALOG_KEYWORDS:
                    if kw in title_lower:
                        return True, w.title

                # Check if a child popup is blocking the main window
                popup_hwnd = self.window_mgr.get_last_active_popup(w.hwnd)
                if popup_hwnd and popup_hwnd != w.hwnd:
                    popup_title = self.window_mgr.get_window_title(popup_hwnd)
                    if popup_title:
                        return True, popup_title

        return False, ""

    def run(self, job: RenderJob) -> RenderJob:
        """Execute a headless render job with full supervision and lifecycle management.

        Steps:
        1. Preflight: disk space, concurrency lock, and instance collision policy.
        2. Staging: isolate project file to job directory with read-only flag.
        3. Launch: launch FL64.exe with CREATE_NEW_PROCESS_GROUP and attach to Job Object.
        4. Supervision: poll for dialog popups, file growth (idle timeout), and total timeout.
        5. Collection: collect output audio files and generate sidecar metadata.
        """
        # Acquire concurrency lock (max 1 active render job) [06_l0d §13]
        lock = RenderJobLock(job.job_id)
        lock.acquire()

        job_obj = WindowsJobObject()
        proc: Any = None

        try:
            # --- 1. Preflight [RND-01] ---
            job.state = JobState.PREFLIGHT

            # Resolve FL install reference
            fl_install = self.resolve_fl_install(job)
            job.fl_install = fl_install

            # Enforce instance collision policy [06_l0d §13]
            policy = job.instance_policy or self.config.render.default_policy
            self.policy_enforcer.enforce(policy, preferred_install=fl_install)

            # --- 2. Staging [RND-02] ---
            staged_flp = job.stage()

            # Determine ARM64 Prism timeout scaling [Spike S11]
            is_arm64_emulated = fl_install.is_emulated or self.discovery.is_prism_emulated()
            scale = self.config.render.timeout_multiplier if is_arm64_emulated else 1.0
            if job.timeout_multiplier > 1.0:
                scale = job.timeout_multiplier
            job.timeout_multiplier = scale

            effective_timeout_s = job.timeout_s * scale
            effective_idle_timeout_s = job.idle_timeout_s * scale

            # --- 3. Launch [RND-03] ---
            job.state = JobState.LAUNCHING
            format_arg = f"/E{','.join(job.formats)}"
            cmd: list[str] = [
                str(fl_install.exe_path),
                "/R",
                format_arg,
                str(staged_flp),
            ]

            flags = CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            job.started_at = time.time()

            try:
                proc = self.popen_factory(
                    cmd,
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                job.state = JobState.FAILED
                job.error = f"Failed to spawn FL Studio render process: {e}"
                job.error_code = "E_RND_FLRUNNING"
                raise RenderError(job.error) from e

            job.pid = proc.pid
            # Assign process to Job Object to guarantee zero zombies on kill [RND-03]
            job_obj.assign_process(proc)
            job.state = JobState.RENDERING

            # --- 4. Supervision & Dialog Detection [RND-04] ---
            start_time = time.time()
            last_growth_time = start_time
            last_max_file_size = 0

            while True:
                # Check if process has terminated
                poll_res = proc.poll()
                if poll_res is not None:
                    job.exit_code = poll_res
                    break

                now = time.time()

                # Check for blocking modal dialog popups [RND-04]
                has_dialog, dialog_title = self.detect_blocking_dialog(proc.pid)
                if has_dialog:
                    self._terminate_process_tree(proc, job_obj)
                    job.state = JobState.FAILED
                    job.error_code = "E_RND_DIALOG"
                    job.error = f"Render process blocked by modal dialog: '{dialog_title}'."
                    raise BlockingDialogError(job.error, code="E_RND_DIALOG")

                # Monitor output file growth in staged directory
                current_size = self._get_staged_outputs_size(job)
                if current_size > last_max_file_size:
                    last_max_file_size = current_size
                    last_growth_time = now
                else:
                    if (now - last_growth_time) > effective_idle_timeout_s:
                        self._terminate_process_tree(proc, job_obj)
                        job.state = JobState.FAILED
                        job.error_code = "E_RND_TIMEOUT"
                        job.error = (
                            f"Render idle timeout exceeded ({effective_idle_timeout_s:.1f}s "
                            f"with no output growth; ARM64 scale {scale:.1f}x)."
                        )
                        raise RenderTimeoutError(job.error, code="E_RND_TIMEOUT")

                # Check total timeout
                if (now - start_time) > effective_timeout_s:
                    self._terminate_process_tree(proc, job_obj)
                    job.state = JobState.FAILED
                    job.error_code = "E_RND_TIMEOUT"
                    job.error = (
                        f"Render total timeout exceeded ({effective_timeout_s:.1f}s; "
                        f"ARM64 scale {scale:.1f}x)."
                    )
                    raise RenderTimeoutError(job.error, code="E_RND_TIMEOUT")

                time.sleep(self.poll_interval_s)

            # Check exit code
            if job.exit_code != 0:
                job.state = JobState.FAILED
                job.error = f"FL Studio render process exited with non-zero code {job.exit_code}"
                job.error_code = "E_RND_FLRUNNING"
                raise RenderError(job.error)

            # --- 5. Collection ---
            job.state = JobState.COLLECTING
            self._collect_outputs(job, fl_install)
            job.state = JobState.DONE
            job.completed_at = time.time()
            return job

        except (BlockingDialogError, RenderTimeoutError, FlRunningError):
            job.state = JobState.FAILED
            raise
        except Exception as e:
            job.state = JobState.FAILED
            if not job.error:
                job.error = str(e)
            if not job.error_code:
                job.error_code = getattr(e, "code", "E_RND_FLRUNNING")
            raise
        finally:
            if proc is not None and proc.poll() is None:
                self._terminate_process_tree(proc, job_obj)
            job_obj.close()
            lock.release()

    def _terminate_process_tree(self, proc: Any, job_obj: WindowsJobObject) -> None:
        """Safely terminate child process and all descendants with zero zombie processes."""
        # 1. Terminate Job Object if present
        job_obj.terminate(exit_code=1)
        job_obj.close()

        # 2. Fallback to taskkill / proc.kill()
        if hasattr(proc, "poll") and proc.poll() is None:
            if sys.platform == "win32" and hasattr(proc, "pid"):
                with contextlib.suppress(Exception):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            with contextlib.suppress(Exception):
                proc.kill()
                proc.wait(timeout=2.0)

    def _get_staged_outputs_size(self, job: RenderJob) -> int:
        """Sum file size of all non-staged-flp files in staged directory."""
        if not job.staged_dir or not job.staged_dir.exists():
            return 0
        total = 0
        try:
            for item in job.staged_dir.iterdir():
                if item.is_file() and item != job.staged_flp:
                    total += item.stat().st_size
        except OSError:
            pass
        return total

    def _collect_outputs(self, job: RenderJob, fl_install: FlInstall) -> None:
        """Move generated audio files to out_dir and write sidecar metadata."""
        out_dir = job.out_dir or (get_jobs_dir() / job.job_id / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        job.out_dir = out_dir

        collected: list[Path] = []
        if job.staged_dir and job.staged_dir.exists():
            for item in job.staged_dir.iterdir():
                if item.is_file() and item != job.staged_flp:
                    dest = out_dir / item.name
                    if dest.exists():
                        dest.unlink()
                    shutil.move(str(item), str(dest))
                    collected.append(dest)

        job.output_files = collected

        # Write sidecar metadata JSON [06_l0d §12]
        fl_build_str = (
            f"{fl_install.major}.{fl_install.minor}.{fl_install.build}.{fl_install.revision}"
        )
        sidecar_data = {
            "job_id": job.job_id,
            "fl_version": fl_install.version_str,
            "fl_build": fl_build_str,
            "fl_architecture": fl_install.architecture,
            "is_emulated": fl_install.is_emulated,
            "source": str(job.source),
            "source_hash": job.source_hash,
            "source_size_bytes": job.source_size_bytes,
            "formats": job.formats,
            "output_files": [f.name for f in collected],
            "duration_s": (job.completed_at or time.time()) - (job.started_at or time.time()),
            "created_at": job.created_at,
            "completed_at": time.time(),
            "settings_warning": (
                "Export settings were inherited from the last FL Studio interactive session."
            ),
        }

        sidecar_path = out_dir / f"{job.source.stem}.render.json"
        sidecar_path.write_text(json.dumps(sidecar_data, indent=2), encoding="utf-8")
        job.sidecar_path = sidecar_path
