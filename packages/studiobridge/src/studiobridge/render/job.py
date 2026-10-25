"""Render job state machine, project isolation staging, disk checks, and concurrency locks.

Implements RenderJob, staging isolation under %LOCALAPPDATA%\\studiobridge\\jobs\\,
disk space preflight verification, and single-instance render concurrency locks
per spec 06_l0d_pianoroll_actuation_render.md §11-§13 and [RND-01], [RND-02].
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from studiobridge.core.errors import (
    RenderConcurrencyError,
    RenderDiskSpaceError,
    RenderError,
)
from studiobridge.core.paths import get_jobs_dir
from studiobridge.render.discover import FlInstall


class JobState(str, Enum):
    """Lifecycle states of a headless render job [06_l0d §12]."""

    CREATED = "created"
    PREFLIGHT = "preflight"
    STAGED = "staged"
    LAUNCHING = "launching"
    RENDERING = "rendering"
    COLLECTING = "collecting"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


def is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is currently executing."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                return False
            exit_code = wintypes.DWORD()
            res = kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
            kernel32.CloseHandle(h_proc)
            if res:
                return exit_code.value == STILL_ACTIVE
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class RenderJobLock:
    """Single-instance render concurrency lock [06_l0d §13].

    FL Studio headless render forwards commands to running instances, meaning only
    one render job may execute at any given time.
    """

    _thread_lock: threading.Lock = threading.Lock()

    def __init__(self, job_id: str, lock_dir: Path | None = None) -> None:
        self.job_id = job_id
        self.lock_dir = lock_dir or get_jobs_dir()
        self.lock_file = self.lock_dir / "active_render.lock"
        self._acquired = False

    def acquire(self) -> None:
        """Acquire the single active render concurrency lock.

        Raises:
            RenderConcurrencyError: If another render job is currently running.
        """
        with self._thread_lock:
            self.lock_dir.mkdir(parents=True, exist_ok=True)
            if self.lock_file.exists():
                try:
                    data = json.loads(self.lock_file.read_text(encoding="utf-8"))
                    locking_pid = data.get("pid", 0)
                    locking_job = data.get("job_id", "unknown")

                    if is_pid_alive(locking_pid) and locking_job != self.job_id:
                        raise RenderConcurrencyError(
                            f"Render job '{locking_job}' (PID {locking_pid}) is currently running. "
                            "FL Studio headless render supports max 1 concurrent job.",
                            code="E_RND_BUSY",
                        )
                except (json.JSONDecodeError, OSError):
                    pass
                # Previous lock is stale or invalid; overwrite
                with contextlib.suppress(OSError):
                    self.lock_file.unlink()

            lock_payload = {
                "job_id": self.job_id,
                "pid": os.getpid(),
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
            self.lock_file.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")
            self._acquired = True

    def release(self) -> None:
        """Release the concurrency lock."""
        with self._thread_lock:
            if self._acquired and self.lock_file.exists():
                try:
                    data = json.loads(self.lock_file.read_text(encoding="utf-8"))
                    if data.get("job_id") == self.job_id:
                        self.lock_file.unlink()
                except Exception:
                    with contextlib.suppress(OSError):
                        self.lock_file.unlink()
                finally:
                    self._acquired = False

    def __enter__(self) -> RenderJobLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


def generate_job_id() -> str:
    """Generate a unique timestamped render job identifier."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"rnd-{ts}-{suffix}"


@dataclass
class RenderJob:
    """Headless render job specification and tracking [06_l0d §11].

    Attributes:
        source: Source project file (.flp).
        formats: Export formats (e.g. ['wav'], ['mp3']).
        job_id: Unique job identifier.
        out_dir: Target output directory (default: %LOCALAPPDATA%\\studiobridge\\jobs\\{id}\\out\\).
        fl_install: Target FL Studio installation reference or path.
        instance_policy: Collision policy ('require_closed', 'close_gracefully', 'force_kill').
        timeout_s: Total render timeout in seconds (default 900.0).
        idle_timeout_s: Idle timeout with no output file growth (default 120.0).
        timeout_multiplier: Timeout scaling factor (default 1.5 on ARM64 Prism).
        estimated_output_bytes: Estimated audio output size (default 50 MB).
        min_disk_free_multiplier: Required free disk space ratio (default 2.0 per [RND-01]).
        state: Current job state.
        staged_flp: Staged copy of project file.
        staged_dir: Staged isolation directory.
        output_files: Paths to collected rendered files.
        sidecar_path: Path to sidecar metadata JSON file.
        error: Failure reason string if failed.
        error_code: Canonical error code (e.g. 'E_RND_DIALOG').
        exit_code: Subprocess return code.
        pid: Subprocess PID.
    """

    source: Path
    formats: list[str] = field(default_factory=lambda: ["wav"])
    job_id: str = field(default_factory=generate_job_id)
    out_dir: Path | None = None
    fl_install: FlInstall | Path | None = None
    instance_policy: str = "require_closed"
    timeout_s: float = 900.0
    idle_timeout_s: float = 120.0
    timeout_multiplier: float = 1.0
    estimated_output_bytes: int = 50_000_000
    min_disk_free_multiplier: float = 2.0
    state: JobState = JobState.CREATED
    staged_flp: Path | None = None
    staged_dir: Path | None = None
    output_files: list[Path] = field(default_factory=list)
    sidecar_path: Path | None = None
    error: str | None = None
    error_code: str | None = None
    exit_code: int | None = None
    pid: int | None = None
    source_hash: str = ""
    source_size_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source = Path(self.source)
        if self.out_dir is not None:
            self.out_dir = Path(self.out_dir)

    def check_disk_space(self, target_path: Path | None = None) -> tuple[bool, int, int]:
        """Verify available disk space on staging drive is >= 2x estimated output [RND-01].

        Returns:
            Tuple of (is_sufficient, available_bytes, required_bytes).
        """
        required_bytes = int(self.estimated_output_bytes * self.min_disk_free_multiplier)
        check_dir = target_path or self.staged_dir or self.out_dir or get_jobs_dir()

        try:
            check_dir.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(check_dir)
            available = usage.free
            sufficient = available >= required_bytes
            return sufficient, available, required_bytes
        except OSError:
            # If disk_usage fails, fallback to passing
            return True, required_bytes * 2, required_bytes

    def stage(self, staging_root: Path | None = None) -> Path:
        """Stage source project file to an isolated read-only directory [RND-02].

        Copies source .flp to %LOCALAPPDATA%\\studiobridge\\jobs\\{job_id}\\staged\\,
        sets read-only permissions on the staged copy, and records the original hash
        to guarantee original project files remain untouched.

        Returns:
            Path to the staged read-only .flp file.

        Raises:
            RenderError: If source file does not exist or cannot be read.
            RenderDiskSpaceError: If disk space is insufficient (< 2x estimated output).
        """
        if not self.source.exists() or not self.source.is_file():
            self.state = JobState.FAILED
            self.error = f"Source project file not found: '{self.source}'"
            self.error_code = "E_RND_FLRUNNING"
            raise RenderError(self.error)

        # Compute hash and size of original file
        try:
            content = self.source.read_bytes()
            self.source_hash = hashlib.sha256(content).hexdigest()
            self.source_size_bytes = len(content)
        except OSError as e:
            self.state = JobState.FAILED
            self.error = f"Cannot read source project file: {e}"
            raise RenderError(self.error) from e

        # Determine staging directories
        if staging_root is not None:
            base_job_dir = (
                staging_root if staging_root.name == self.job_id else (staging_root / self.job_id)
            )
        else:
            base_job_dir = get_jobs_dir() / self.job_id
        staged_dir = base_job_dir / "staged"
        staged_dir.mkdir(parents=True, exist_ok=True)

        # Verify disk space before copying [RND-01]
        sufficient, avail, req = self.check_disk_space(staged_dir)
        if not sufficient:
            self.state = JobState.FAILED
            self.error_code = "E_RND_DISK"
            self.error = (
                f"Insufficient disk space on staging volume: {avail} bytes available, "
                f"{req} bytes required (2x estimated output {self.estimated_output_bytes} bytes)."
            )
            raise RenderDiskSpaceError(self.error, code="E_RND_DISK")

        staged_flp = staged_dir / self.source.name

        # Copy original file to staged directory
        shutil.copy2(self.source, staged_flp)

        # Set read-only attribute on staged copy to prevent render writes [RND-02]
        staged_flp.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        self.staged_flp = staged_flp
        self.staged_dir = staged_dir
        if self.out_dir is None:
            self.out_dir = base_job_dir / "out"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.state = JobState.STAGED
        return staged_flp

    def unlock_staged(self) -> None:
        """Restore write permissions on staged copy so it can be cleaned up."""
        if self.staged_flp and self.staged_flp.exists():
            with contextlib.suppress(OSError):
                self.staged_flp.chmod(stat.S_IWRITE | stat.S_IREAD)

    def to_dict(self) -> dict[str, Any]:
        """Serialize render job state to dictionary."""
        return {
            "job_id": self.job_id,
            "source": str(self.source),
            "formats": self.formats,
            "out_dir": str(self.out_dir) if self.out_dir else None,
            "state": self.state.value,
            "staged_flp": str(self.staged_flp) if self.staged_flp else None,
            "staged_dir": str(self.staged_dir) if self.staged_dir else None,
            "output_files": [str(f) for f in self.output_files],
            "sidecar_path": str(self.sidecar_path) if self.sidecar_path else None,
            "error": self.error,
            "error_code": self.error_code,
            "exit_code": self.exit_code,
            "pid": self.pid,
            "source_hash": self.source_hash,
            "source_size_bytes": self.source_size_bytes,
            "timeout_s": self.timeout_s,
            "idle_timeout_s": self.idle_timeout_s,
            "timeout_multiplier": self.timeout_multiplier,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metrics": self.metrics,
        }
