"""Unit tests for headless FL Studio render job runner, staging, and process supervision.

# req: RND-01, RND-02, RND-03, RND-04
"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from studiobridge.actuate.win32 import FLWindowInfo
from studiobridge.core.errors import (
    BlockingDialogError,
    FlInstallNotFoundError,
    FlRunningError,
    RenderConcurrencyError,
    RenderDiskSpaceError,
    RenderTimeoutError,
)
from studiobridge.render.discover import FlDiscovery, FlInstall
from studiobridge.render.job import JobState, RenderJob, RenderJobLock
from studiobridge.render.runner import RenderRunner


@pytest.fixture
def sample_flp(tmp_path: Path) -> Path:
    """Create a sample source project file."""
    p = tmp_path / "MyProject.flp"
    p.write_bytes(b"FLhd\x06\x00\x00\x00\x01\x00\x00\x00\x60\x00FLdtMockProjectData")
    return p


@pytest.fixture
def mock_fl_install(tmp_path: Path) -> FlInstall:
    """Create a mock FlInstall reference."""
    fl_dir = tmp_path / "FL Studio 2026"
    fl_dir.mkdir(parents=True, exist_ok=True)
    fl64 = fl_dir / "FL64.exe"
    fl64.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
    return FlInstall(
        path=fl_dir,
        exe_path=fl64,
        version_str="26.1.3.5570",
        major=26,
        minor=1,
        build=3,
        revision=5570,
        architecture="x64",
        is_emulated=False,
        name="FL Studio 2026",
    )


# --- [RND-01]: Preflight Checks ---


def test_preflight_fails_when_disk_space_insufficient(
    sample_flp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verify preflight halts cleanly when available disk space is < 2x estimated output.

    # req: RND-01
    """
    job = RenderJob(
        source=sample_flp,
        estimated_output_bytes=100_000_000,  # 100 MB estimated output
        min_disk_free_multiplier=2.0,  # requires 200 MB
    )

    # Mock shutil.disk_usage to return only 50 MB free (< 200 MB required)
    mock_usage = MagicMock(free=50_000_000)
    monkeypatch.setattr("shutil.disk_usage", lambda _: mock_usage)

    with pytest.raises(RenderDiskSpaceError) as exc_info:
        job.stage(staging_root=tmp_path / "jobs")

    assert exc_info.value.code == "E_RND_DISK"
    assert "Insufficient disk space" in str(exc_info.value)
    assert job.state == JobState.FAILED
    assert job.error_code == "E_RND_DISK"


def test_preflight_fails_when_fl_already_running(sample_flp: Path, mock_fl_install: FlInstall):
    """Verify preflight halts cleanly when FL Studio is open and policy is require_closed.

    # req: RND-01
    """
    job = RenderJob(source=sample_flp, fl_install=mock_fl_install, instance_policy="require_closed")

    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = [
        FLWindowInfo(
            hwnd=101, title="FL Studio", pid=5555, image_path="FL64.exe", is_foreground=True
        )
    ]

    runner = RenderRunner(window_mgr=mock_wm)

    with pytest.raises(FlRunningError) as exc_info:
        runner.run(job)

    assert exc_info.value.code == "E_RND_FLRUNNING"
    assert job.state == JobState.FAILED


# --- [RND-02]: Staging Isolation ---


def test_staging_creates_isolated_readonly_copy(sample_flp: Path, tmp_path: Path):
    """Verify staging creates an isolated read-only copy and leaves original file untouched.

    # req: RND-02
    """
    orig_bytes = sample_flp.read_bytes()
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()
    staging_root = tmp_path / "jobs"

    job = RenderJob(source=sample_flp, job_id="test-job-001")
    staged_path = job.stage(staging_root=staging_root)

    assert staged_path.exists()
    assert staged_path.is_file()
    assert staged_path.name == "MyProject.flp"
    assert staged_path.parent == staging_root / "test-job-001" / "staged"
    assert job.state == JobState.STAGED

    # Verify original file was unmodified
    assert sample_flp.read_bytes() == orig_bytes
    assert hashlib.sha256(sample_flp.read_bytes()).hexdigest() == orig_hash
    assert job.source_hash == orig_hash

    # Verify staged copy has read-only permission flag set
    staged_stat = staged_path.stat()
    assert not (staged_stat.st_mode & stat.S_IWUSR), "Staged .flp must be read-only"

    # Unlock staged file to allow cleanup
    job.unlock_staged()
    assert staged_path.stat().st_mode & stat.S_IWUSR


# --- [RND-03]: Process Launch, Job Objects & Concurrency ---


def test_runner_launches_fl64_with_process_group_and_formats(
    sample_flp: Path,
    mock_fl_install: FlInstall,
    tmp_path: Path,
):
    """Verify runner spawns FL64.exe with /R /E... and CREATE_NEW_PROCESS_GROUP.

    # req: RND-03
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    captured_args: list[Any] = []
    captured_kwargs: dict[str, Any] = {}

    class MockPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured_args.extend(args[0])
            captured_kwargs.update(kwargs)
            self.pid = 9876
            self._handle = 12345

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=MockPopen,
    )

    job = RenderJob(
        source=sample_flp,
        formats=["wav", "mp3"],
        fl_install=mock_fl_install,
        out_dir=tmp_path / "out",
    )

    completed_job = runner.run(job)

    assert captured_args[0] == str(mock_fl_install.exe_path)
    assert captured_args[1] == "/R"
    assert captured_args[2] == "/Ewav,mp3"
    assert "MyProject.flp" in captured_args[3]
    if sys.platform == "win32":
        assert captured_kwargs.get("creationflags", 0) & 0x00000200  # CREATE_NEW_PROCESS_GROUP

    assert completed_job.state == JobState.DONE
    assert completed_job.pid == 9876
    assert completed_job.exit_code == 0


def test_concurrency_lock_enforces_single_active_render(tmp_path: Path):
    """Verify single-instance render concurrency lock rejects overlapping renders.

    # req: RND-03
    """
    lock_dir = tmp_path / "jobs"
    lock1 = RenderJobLock("job-alpha", lock_dir=lock_dir)
    lock1.acquire()

    lock2 = RenderJobLock("job-beta", lock_dir=lock_dir)
    with pytest.raises(RenderConcurrencyError) as exc_info:
        lock2.acquire()

    assert exc_info.value.code == "E_RND_BUSY"
    assert "max 1 concurrent job" in str(exc_info.value)

    # Release lock1, lock2 should now acquire cleanly
    lock1.release()
    lock2.acquire()
    lock2.release()


def test_concurrency_lock_breaks_stale_lock(tmp_path: Path):
    """Verify stale lock from a dead PID is automatically broken.

    # req: RND-03
    """
    lock_dir = tmp_path / "jobs"
    lock_dir.mkdir(parents=True, exist_ok=True)
    stale_file = lock_dir / "active_render.lock"
    # Write lock with a PID that is definitively dead (e.g. 9999999)
    stale_file.write_text(
        json.dumps({"job_id": "dead-job", "pid": 9999999, "acquired_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    new_lock = RenderJobLock("new-job", lock_dir=lock_dir)
    new_lock.acquire()  # Should break stale lock and succeed
    assert new_lock._acquired is True
    new_lock.release()


# --- [RND-04]: Modal Dialog Supervisor & Timeouts ---


def test_modal_dialog_detector_aborts_render_with_e_rnd_dialog(
    sample_flp: Path,
    mock_fl_install: FlInstall,
):
    """Verify runner detects blocking modal dialogs during render and aborts with E_RND_DIALOG.

    # req: RND-04
    """
    mock_wm = MagicMock()
    # At start, no windows; then a blocking dialog appears
    mock_wm.find_fl_windows.side_effect = [
        [],  # preflight check passes
        [
            FLWindowInfo(
                hwnd=2001,
                title="Missing plugin: Serum_x64",
                pid=7777,
                image_path="FL64.exe",
                is_foreground=True,
            )
        ],
    ]
    mock_wm.get_last_active_popup.return_value = None

    class RunningPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 7777
            self._handle = 1234
            self._killed = False

        def poll(self) -> int | None:
            return 1 if self._killed else None

        def kill(self) -> None:
            self._killed = True

        def wait(self, timeout: float | None = None) -> int:
            return 1

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=RunningPopen,
        poll_interval_s=0.01,
    )

    job = RenderJob(source=sample_flp, fl_install=mock_fl_install)

    with pytest.raises(BlockingDialogError) as exc_info:
        runner.run(job)

    assert exc_info.value.code == "E_RND_DIALOG"
    assert "Missing plugin" in str(exc_info.value)
    assert job.state == JobState.FAILED
    assert job.error_code == "E_RND_DIALOG"


def test_total_timeout_terminates_render_process(
    sample_flp: Path,
    mock_fl_install: FlInstall,
):
    """Verify runner enforces total timeout and terminates process tree.

    # req: RND-04
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []
    mock_wm.get_last_active_popup.return_value = None

    class HangingPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 8888
            self._handle = 5678
            self._killed = False

        def poll(self) -> int | None:
            return 1 if self._killed else None

        def kill(self) -> None:
            self._killed = True

        def wait(self, timeout: float | None = None) -> int:
            return 1

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=HangingPopen,
        poll_interval_s=0.01,
    )

    # Set total timeout to very short 0.05 seconds
    job = RenderJob(
        source=sample_flp,
        fl_install=mock_fl_install,
        timeout_s=0.05,
        idle_timeout_s=10.0,
    )

    with pytest.raises(RenderTimeoutError) as exc_info:
        runner.run(job)

    assert exc_info.value.code == "E_RND_TIMEOUT"
    assert "total timeout exceeded" in str(exc_info.value).lower()
    assert job.state == JobState.FAILED


def test_idle_timeout_terminates_when_output_file_stops_growing(
    sample_flp: Path,
    mock_fl_install: FlInstall,
    tmp_path: Path,
):
    """Verify idle timeout triggers when no output file growth occurs within threshold.

    # req: RND-04
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []
    mock_wm.get_last_active_popup.return_value = None

    class HangingPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 9999
            self._handle = 9999
            self._killed = False

        def poll(self) -> int | None:
            return 1 if self._killed else None

        def kill(self) -> None:
            self._killed = True

        def wait(self, timeout: float | None = None) -> int:
            return 1

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=HangingPopen,
        poll_interval_s=0.01,
    )

    # Idle timeout 0.05 seconds, total timeout 10 seconds
    job = RenderJob(
        source=sample_flp,
        fl_install=mock_fl_install,
        timeout_s=10.0,
        idle_timeout_s=0.05,
    )

    with pytest.raises(RenderTimeoutError) as exc_info:
        runner.run(job)

    assert exc_info.value.code == "E_RND_TIMEOUT"
    assert "idle timeout exceeded" in str(exc_info.value).lower()


def test_arm64_timeout_scaling_by_1_5x(sample_flp: Path, mock_fl_install: FlInstall):
    """Verify idle and total timeouts scale by 1.5x on Windows ARM64 under Prism.

    # req: RND-04
    """
    # Create an ARM64 emulated install reference
    arm64_install = FlInstall(
        path=mock_fl_install.path,
        exe_path=mock_fl_install.exe_path,
        version_str="26.1.3.5570",
        major=26,
        minor=1,
        build=3,
        revision=5570,
        architecture="x64",
        is_emulated=True,  # Prism emulated
    )

    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    class MockPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 4321
            self._handle = 1111

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=MockPopen,
    )

    job = RenderJob(
        source=sample_flp,
        fl_install=arm64_install,
        timeout_s=100.0,
        idle_timeout_s=20.0,
    )

    runner.run(job)

    # Job multiplier must scale to 1.5x
    assert job.timeout_multiplier == 1.5


def test_successful_render_collects_output_and_writes_sidecar(
    sample_flp: Path,
    mock_fl_install: FlInstall,
    tmp_path: Path,
):
    """Verify successful render moves output to out_dir and writes sidecar metadata.

    # req: RND-04
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    out_dir = tmp_path / "custom_out"

    class SimulatingPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 3333
            self._handle = 2222
            # Simulate FL Studio creating an output audio file in the staged directory
            staged_flp_arg = Path(args[0][3])
            out_wav = staged_flp_arg.parent / f"{staged_flp_arg.stem}.wav"
            out_wav.write_bytes(
                b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00data\x00\x00\x00\x00"
            )

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=SimulatingPopen,
    )

    job = RenderJob(
        source=sample_flp,
        fl_install=mock_fl_install,
        out_dir=out_dir,
    )

    completed_job = runner.run(job)

    assert completed_job.state == JobState.DONE
    assert len(completed_job.output_files) == 1
    assert completed_job.output_files[0].name == "MyProject.wav"
    assert completed_job.output_files[0].parent == out_dir

    # Verify sidecar metadata JSON exists and contains expected keys
    assert completed_job.sidecar_path is not None
    assert completed_job.sidecar_path.exists()
    sidecar = json.loads(completed_job.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["job_id"] == completed_job.job_id
    assert sidecar["fl_version"] == "26.1.3.5570"
    assert "MyProject.wav" in sidecar["output_files"]
    assert "settings_warning" in sidecar


# --- Discovery Tests ---


def test_fl_discovery_finds_and_inspects_install(tmp_path: Path):
    """Verify FlDiscovery inspects directories and extracts version metadata."""
    fl_dir = tmp_path / "FL Studio 2026"
    fl_dir.mkdir()
    fl64 = fl_dir / "FL64.exe"
    fl64.write_bytes(b"dummy")

    discovery = FlDiscovery(search_paths=[fl_dir])
    installs = discovery.find_installs()

    assert len(installs) == 1
    inst = installs[0]
    assert inst.name == "FL Studio 2026"
    assert inst.major == 2026
    assert inst.architecture == "x64"
    assert "FL Studio 2026" in inst.display_name


def test_fl_discovery_raises_when_no_install_found(tmp_path: Path):
    """Verify resolve_install raises FlInstallNotFoundError when none located."""
    discovery = FlDiscovery(search_paths=[tmp_path / "empty_dir"])

    with pytest.raises(FlInstallNotFoundError) as exc_info:
        discovery.resolve_install()

    assert exc_info.value.code == "E_RND_NO_INSTALL"
