"""Safety guards for Win32 UI actuation per spec 06_l0d §4, §5 and [ACT-10].

Guards protect user flow and system state:
1. FL Studio is the active foreground window OR policy allow_focus_steal=true.
2. No modal child popups (GetLastActivePopup / GW_ENABLEDPOPUP / IsWindowEnabled).
3. User input idle time check (GetLastInputInfo) to avoid stealing focus while
   the user is actively typing, with bypass when force=true.
"""

from __future__ import annotations

import contextlib
import ctypes
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from studiobridge.actuate.win32 import WindowManager
from studiobridge.core.errors import (
    FocusGuardError,
    ModalBlockedError,
    UserInputActiveError,
    WindowNotFoundError,
)


class LASTINPUTINFO(ctypes.Structure):
    """Win32 LASTINPUTINFO structure for tracking human user input idle time."""

    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("dwTime", ctypes.c_uint32),
    ]


@dataclass(frozen=True, slots=True)
class GuardCheckResult:
    """Result of an individual actuation safety guard check [ACT-10].

    Attributes:
        passed: True if the guard condition was satisfied.
        guard_name: Guard type identifier (e.g. 'foreground', 'modal_popup', 'user_idle').
        reason: Explanatory diagnostic message if guard check failed.
        remedy: Actionable remedy instructions for human or AI agent.
        details: Additional telemetry or context dictionary.
    """

    passed: bool
    guard_name: str
    reason: str = ""
    remedy: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class ActuationGuards:
    """Safety guards enforcing foreground focus, modal dialog avoidance, and user idle checks.

    # req: ACT-10
    """

    def __init__(
        self,
        window_manager: WindowManager,
        *,
        user32: Any = None,
        kernel32: Any = None,
        user_idle_threshold_ms: float = 1000.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize ActuationGuards.

        Args:
            window_manager: WindowManager instance for window queries.
            user32: Optional user32 DLL or mock object.
            kernel32: Optional kernel32 DLL or mock object.
            user_idle_threshold_ms: Minimum human idle time in ms before actuation is permitted.
            clock: Time function returning seconds (defaults to time.time).
        """
        self.wm = window_manager
        self._user32 = user32 or window_manager._user32
        self._kernel32 = kernel32 or window_manager._kernel32
        self.user_idle_threshold_ms = user_idle_threshold_ms
        self._clock = clock or time.time

        if self._user32 and hasattr(self._user32, "GetLastInputInfo"):
            with contextlib.suppress(Exception):
                self._user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
                self._user32.GetLastInputInfo.restype = ctypes.c_int

    def check_window_valid(self, target_hwnd: int) -> GuardCheckResult:
        """Verify that target window handle exists and is an active Win32 window."""
        if target_hwnd <= 0 or not self.wm.is_window_valid(target_hwnd):
            return GuardCheckResult(
                passed=False,
                guard_name="window_valid",
                reason=f"Target window handle {target_hwnd} is invalid or closed.",
                remedy="Ensure FL Studio is running and its main window is active.",
                details={"hwnd": target_hwnd},
            )
        return GuardCheckResult(
            passed=True,
            guard_name="window_valid",
            details={"hwnd": target_hwnd},
        )

    def check_foreground(
        self,
        target_hwnd: int,
        allow_focus_steal: bool = False,
    ) -> GuardCheckResult:
        """Verify that FL Studio is foreground, or focus steal is permitted [ACT-10].

        Args:
            target_hwnd: Target window handle.
            allow_focus_steal: True if policy permits temporary focus transfer.
        """
        is_fg = self.wm.is_fl_foreground(target_hwnd)
        if is_fg:
            return GuardCheckResult(
                passed=True,
                guard_name="foreground",
                details={"is_foreground": True, "focus_stolen": False},
            )

        if allow_focus_steal:
            return GuardCheckResult(
                passed=True,
                guard_name="foreground",
                details={"is_foreground": False, "focus_steal_allowed": True},
            )

        fg_hwnd = self.wm.get_foreground_window()
        fg_title = self.wm.get_window_title(fg_hwnd)
        return GuardCheckResult(
            passed=False,
            guard_name="foreground",
            reason=(
                f"FL Studio (HWND {target_hwnd}) is not the active foreground window. "
                f"Foreground window is '{fg_title}' (HWND {fg_hwnd})."
            ),
            remedy=(
                "Bring FL Studio to the foreground before triggering hotkeys, or enable "
                "'actuation.allow_focus_steal=true' in configuration."
            ),
            details={
                "target_hwnd": target_hwnd,
                "foreground_hwnd": fg_hwnd,
                "foreground_title": fg_title,
                "focus_steal_allowed": False,
            },
        )

    def check_modal_popup(self, target_hwnd: int) -> GuardCheckResult:
        """Detect modal child popups blocking the FL Studio main window [ACT-10].

        Inspects:
        - Window enabled state: user32.IsWindowEnabled(target_hwnd)
        - Last active popup: user32.GetLastActivePopup(target_hwnd)
        - Enabled popup: user32.GetWindow(target_hwnd, GW_ENABLEDPOPUP)
        """
        main_enabled = self.wm.is_window_enabled(target_hwnd)
        popup1 = self.wm.get_last_active_popup(target_hwnd)
        popup2 = self.wm.get_enabled_popup(target_hwnd)

        # 1. Main window disabled by modal dialog
        if not main_enabled:
            blocking_hwnd = popup1 if (popup1 and popup1 != target_hwnd) else popup2
            blocking_hwnd = (
                blocking_hwnd if (blocking_hwnd and blocking_hwnd != target_hwnd) else target_hwnd
            )
            title = (
                self.wm.get_window_title(blocking_hwnd)
                if blocking_hwnd != target_hwnd
                else "Modal Dialog"
            )
            return GuardCheckResult(
                passed=False,
                guard_name="modal_popup",
                reason=f"FL Studio is disabled by modal dialog '{title}' (HWND {blocking_hwnd}).",
                remedy="Dismiss open modal dialog or alert prompt in FL Studio before actuation.",
                details={
                    "blocking_hwnd": blocking_hwnd,
                    "popup_title": title,
                    "main_enabled": False,
                },
            )

        # 2. Separate active popup window
        if (
            popup1
            and popup1 != target_hwnd
            and self.wm.is_window_valid(popup1)
            and self.wm.is_window_visible(popup1)
        ):
            title = self.wm.get_window_title(popup1) or "Popup Window"
            return GuardCheckResult(
                passed=False,
                guard_name="modal_popup",
                reason=f"Active popup window '{title}' (HWND {popup1}) detected on FL Studio.",
                remedy="Dismiss or close the popup window in FL Studio before actuation.",
                details={
                    "blocking_hwnd": popup1,
                    "popup_title": title,
                    "main_enabled": main_enabled,
                },
            )

        # 3. Enabled popup window
        if (
            popup2
            and popup2 != target_hwnd
            and self.wm.is_window_valid(popup2)
            and self.wm.is_window_visible(popup2)
        ):
            title = self.wm.get_window_title(popup2) or "Popup Window"
            return GuardCheckResult(
                passed=False,
                guard_name="modal_popup",
                reason=f"Enabled popup dialog '{title}' (HWND {popup2}) detected on FL Studio.",
                remedy="Dismiss or close the popup dialog in FL Studio before actuation.",
                details={
                    "blocking_hwnd": popup2,
                    "popup_title": title,
                    "main_enabled": main_enabled,
                },
            )

        return GuardCheckResult(
            passed=True,
            guard_name="modal_popup",
            details={"target_hwnd": target_hwnd, "main_enabled": True},
        )

    def get_idle_time_ms(self) -> float:
        """Calculate human user input idle time in milliseconds using GetLastInputInfo.

        Returns:
            Milliseconds since last keyboard or mouse input, or 10000.0 if unavailable.
        """
        if not self._user32 or not hasattr(self._user32, "GetLastInputInfo"):
            return 10000.0

        try:
            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            res = self._user32.GetLastInputInfo(ctypes.byref(info))
            if not res:
                return 10000.0

            curr_tick: int
            if self._kernel32 and hasattr(self._kernel32, "GetTickCount64"):
                curr_tick = int(self._kernel32.GetTickCount64())
            elif self._kernel32 and hasattr(self._kernel32, "GetTickCount"):
                curr_tick = int(self._kernel32.GetTickCount())
            else:
                curr_tick = int(self._clock() * 1000)

            idle_ms = float((curr_tick - info.dwTime) & 0xFFFFFFFF)
            return idle_ms
        except Exception:
            return 10000.0

    def check_user_idle(
        self,
        threshold_ms: float | None = None,
        force: bool = False,
    ) -> GuardCheckResult:
        """Verify that the user has been idle to avoid fighting the human typing [ACT-10].

        Args:
            threshold_ms: Minimum idle duration in ms (defaults to self.user_idle_threshold_ms).
            force: If True, bypass the idle check.
        """
        if force:
            return GuardCheckResult(
                passed=True,
                guard_name="user_idle",
                details={"forced": True},
            )

        thresh = threshold_ms if threshold_ms is not None else self.user_idle_threshold_ms
        idle_ms = self.get_idle_time_ms()

        if idle_ms < thresh:
            return GuardCheckResult(
                passed=False,
                guard_name="user_idle",
                reason=(
                    f"User input was detected {idle_ms:.0f}ms ago (< {thresh:.0f}ms threshold). "
                    "Aborting actuation to avoid fighting the user."
                ),
                remedy="Wait for user input to pause or pass force=True to override idle guard.",
                details={"idle_ms": idle_ms, "threshold_ms": thresh},
            )

        return GuardCheckResult(
            passed=True,
            guard_name="user_idle",
            details={"idle_ms": idle_ms, "threshold_ms": thresh},
        )

    def verify_all(
        self,
        target_hwnd: int,
        *,
        allow_focus_steal: bool = False,
        force: bool = False,
        threshold_ms: float | None = None,
    ) -> list[GuardCheckResult]:
        """Run all safety guards and return check results [ACT-10]."""
        results: list[GuardCheckResult] = [
            self.check_window_valid(target_hwnd),
            self.check_modal_popup(target_hwnd),
            self.check_user_idle(threshold_ms=threshold_ms, force=force),
            self.check_foreground(target_hwnd, allow_focus_steal=allow_focus_steal),
        ]
        return results

    def ensure_ready(
        self,
        target_hwnd: int,
        *,
        allow_focus_steal: bool = False,
        force: bool = False,
        threshold_ms: float | None = None,
    ) -> None:
        """Verify all safety guards, raising specific typed exceptions on failure [ACT-10].

        Raises:
            WindowNotFoundError: If target_hwnd is not a valid window.
            ModalBlockedError: If a modal dialog or popup is active.
            UserInputActiveError: If recent user input was detected and force=False.
            FocusGuardError: If FL Studio is not foreground and allow_focus_steal=False.
        """
        # 1. Window validity
        w_res = self.check_window_valid(target_hwnd)
        if not w_res.passed:
            raise WindowNotFoundError(
                w_res.reason,
                details=w_res.details,
                remedy=w_res.remedy,
            )

        # 2. Modal popup guard
        m_res = self.check_modal_popup(target_hwnd)
        if not m_res.passed:
            raise ModalBlockedError(
                m_res.reason,
                details=m_res.details,
                remedy=m_res.remedy,
            )

        # 3. User idle guard
        u_res = self.check_user_idle(threshold_ms=threshold_ms, force=force)
        if not u_res.passed:
            raise UserInputActiveError(
                u_res.reason,
                details=u_res.details,
                remedy=u_res.remedy,
            )

        # 4. Foreground focus guard
        f_res = self.check_foreground(target_hwnd, allow_focus_steal=allow_focus_steal)
        if not f_res.passed:
            raise FocusGuardError(
                f_res.reason,
                details=f_res.details,
                remedy=f_res.remedy,
            )
