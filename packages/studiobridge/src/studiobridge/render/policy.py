"""Instance collision policy definitions and enforcement for FL Studio renders.

Implements collision policies:
- 'require_closed': Preflight halts cleanly if FL Studio is running (default per [RND-01]).
- 'close_gracefully': Sends WM_CLOSE and waits for exit, never auto-confirming 'discard'.
- 'force_kill': Forcibly terminates running FL Studio instances to unblock batch renders.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path

from studiobridge.actuate.win32 import FLWindowInfo, WindowManager
from studiobridge.core.errors import FlRunningError
from studiobridge.render.discover import FlInstall

WM_CLOSE: int = 0x0010
PROCESS_TERMINATE: int = 0x0001


class InstancePolicy(str, Enum):
    """Instance collision policies for headless rendering."""

    REQUIRE_CLOSED = "require_closed"
    CLOSE_GRACEFULLY = "close_gracefully"
    FORCE_KILL = "force_kill"


class InstancePolicyEnforcer:
    """Detects running FL Studio instances and enforces the configured collision policy."""

    def __init__(
        self,
        window_mgr: WindowManager | None = None,
        graceful_timeout_s: float = 5.0,
        poll_interval_s: float = 0.5,
    ) -> None:
        self.window_mgr = window_mgr or WindowManager()
        self.graceful_timeout_s = graceful_timeout_s
        self.poll_interval_s = poll_interval_s

    def find_running_fl_instances(
        self,
        preferred_install: FlInstall | Path | None = None,
    ) -> list[FLWindowInfo]:
        """Find active FL Studio top-level windows."""
        target_path = None
        if isinstance(preferred_install, FlInstall):
            target_path = preferred_install.exe_path
        elif isinstance(preferred_install, (Path, str)):
            p = Path(preferred_install)
            target_path = p if p.suffix.lower() == ".exe" else (p / "FL64.exe")

        windows = self.window_mgr.find_fl_windows()
        if target_path:
            norm_target = str(target_path).lower()
            return [
                w
                for w in windows
                if w.image_path
                and (norm_target in w.image_path.lower() or w.image_path.lower() in norm_target)
            ]
        return windows

    def is_fl_running(self, preferred_install: FlInstall | Path | None = None) -> bool:
        """Check if any interactive FL Studio instance is currently open."""
        return len(self.find_running_fl_instances(preferred_install)) > 0

    def enforce(
        self,
        policy: InstancePolicy | str = InstancePolicy.REQUIRE_CLOSED,
        preferred_install: FlInstall | Path | None = None,
    ) -> None:
        """Enforce instance collision policy before commencing headless render [RND-01].

        Raises:
            FlRunningError: If FL Studio is open and policy is 'require_closed',
                           or if graceful close times out / is blocked by modal prompts.
        """
        policy_str = str(policy.value if isinstance(policy, InstancePolicy) else policy).lower()

        windows = self.find_running_fl_instances(preferred_install)
        if not windows:
            return  # Clean pass; no FL Studio instance running

        pids = sorted({w.pid for w in windows})
        titles = [w.title for w in windows if w.title]

        if policy_str == InstancePolicy.REQUIRE_CLOSED.value:
            msg = (
                f"Cannot perform render because an interactive FL Studio instance is running "
                f"(PIDs: {pids}, Windows: {titles})."
            )
            raise FlRunningError(
                msg,
                code="E_RND_FLRUNNING",
                remedy="Save project and close interactive FL Studio instance before batch render.",
            )

        if policy_str == InstancePolicy.CLOSE_GRACEFULLY.value:
            self._close_gracefully(windows, pids)
            return

        if policy_str == InstancePolicy.FORCE_KILL.value:
            self._force_kill(pids)
            return

        # Unknown policy string fallback to require_closed behavior
        raise FlRunningError(
            f"Unknown instance policy '{policy}'; refusing render while FL Studio is running.",
            code="E_RND_FLRUNNING",
        )

    def _close_gracefully(self, windows: list[FLWindowInfo], pids: list[int]) -> None:
        """Send WM_CLOSE and await clean process termination without auto-discarding."""
        # Send WM_CLOSE to main window handles
        user32 = None
        if sys.platform == "win32":
            with contextlib.suppress(Exception):
                user32 = ctypes.WinDLL("user32.dll", use_last_error=True)

        for w in windows:
            if user32 and hasattr(user32, "PostMessageW"):
                user32.PostMessageW(w.hwnd, WM_CLOSE, 0, 0)

        # Wait up to graceful_timeout_s for windows to close
        deadline = time.time() + self.graceful_timeout_s
        while time.time() < deadline:
            time.sleep(self.poll_interval_s)
            remaining = self.window_mgr.find_fl_windows()
            if not remaining:
                return

        # Still running after timeout: prompt may be asking user to save changes
        raise FlRunningError(
            "FL Studio did not close gracefully within timeout. Unsaved changes prompt "
            "requires user resolution (auto-discarding changes is strictly prohibited).",
            code="E_RND_FLRUNNING",
            remedy="Save or close open projects in FL Studio before starting batch render.",
        )

    def _force_kill(self, pids: list[int]) -> None:
        """Forcibly terminate running FL Studio processes."""
        for pid in pids:
            if pid <= 0:
                continue
            if sys.platform == "win32":
                killed = False
                try:
                    kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
                    h_proc = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                    if h_proc:
                        kernel32.TerminateProcess(h_proc, 1)
                        kernel32.CloseHandle(h_proc)
                        killed = True
                except Exception:
                    pass

                if not killed:
                    with contextlib.suppress(Exception):
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
            else:
                with contextlib.suppress(Exception):
                    os.kill(pid, 9)

        # Brief wait for termination to take effect
        deadline = time.time() + 3.0
        while time.time() < deadline:
            time.sleep(0.2)
            if not self.window_mgr.find_fl_windows():
                return
