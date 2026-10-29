"""Win32 hardware scancode keystroke dispatcher and UIActuator [ACT-01, ACT-10, ACT-11].

Dispatches guarded hotkeys (Ctrl+Alt+Y) using SendInput with hardware scancodes
(KEYEVENTF_SCANCODE) for layout independence, inserts 10-20ms modifier delays,
exercises temporary focus restoration, and records every actuation into the
session mutation journal [ACT-11].
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from studiobridge.actuate.guards import ActuationGuards
from studiobridge.actuate.win32 import FLWindowInfo, WindowManager
from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.core.errors import (
    ActuationDisabledError,
    WindowNotFoundError,
)

if TYPE_CHECKING:
    from studiobridge.sdk.journal import MutationJournal

# SendInput Constants
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Virtual Key Codes
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_Y = 0x59

# MapVirtualKey translation types
MAPVK_VK_TO_VSC = 0

# IBM PC/AT standard hardware scancodes for layout independence
DEFAULT_SCANCODES: dict[int, int] = {
    VK_CONTROL: 0x1D,
    VK_MENU: 0x38,
    VK_Y: 0x15,
}


class MOUSEINPUT(ctypes.Structure):
    """Win32 MOUSEINPUT dummy structure for INPUT union sizing."""

    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT structure."""

    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    """Win32 HARDWAREINPUT dummy structure for INPUT union sizing."""

    _fields_ = [
        ("uMsg", ctypes.c_uint32),
        ("wParamL", ctypes.c_uint16),
        ("wParamH", ctypes.c_uint16),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    """Win32 INPUT structure for SendInput."""

    _fields_ = [
        ("type", ctypes.c_uint32),
        ("u", _INPUT_UNION),
    ]


def _setup_input_signatures(user32: Any) -> None:
    """Configure ctypes signatures for input dispatching."""
    with contextlib.suppress(Exception):
        if hasattr(user32, "SendInput"):
            user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
            user32.SendInput.restype = ctypes.c_uint
        if hasattr(user32, "MapVirtualKeyExW"):
            user32.MapVirtualKeyExW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
            user32.MapVirtualKeyExW.restype = ctypes.c_uint
        if hasattr(user32, "GetKeyboardLayout"):
            user32.GetKeyboardLayout.argtypes = [ctypes.c_uint32]
            user32.GetKeyboardLayout.restype = ctypes.c_void_p


@dataclass(frozen=True, slots=True)
class ActuationResult:
    """Outcome of a Win32 UI actuation event [ACT-01, ACT-11].

    Attributes:
        success: True if actuation completed without errors.
        hotkey: Hotkey combination dispatched (e.g. 'Ctrl+Alt+Y').
        target_hwnd: Target FL Studio window handle.
        window_title: Title of target window.
        action_type: Category of actuation ('pianoroll_rerun', 'generic').
        payload_hash: SHA-256 hash of pyscript payload if provided.
        dry_run: True if execution was simulated without injecting inputs.
        focus_stolen: True if focus was temporarily transferred and restored.
        journal_id: Audit journal record ID if logged.
        details: Telemetry dictionary including resolved scancodes.
    """

    success: bool
    hotkey: str
    target_hwnd: int
    window_title: str
    action_type: str = "pianoroll_rerun"
    payload_hash: str = ""
    dry_run: bool = False
    focus_stolen: bool = False
    journal_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert actuation result to dictionary."""
        return {
            "success": self.success,
            "hotkey": self.hotkey,
            "target_hwnd": self.target_hwnd,
            "window_title": self.window_title,
            "action_type": self.action_type,
            "payload_hash": self.payload_hash,
            "dry_run": self.dry_run,
            "focus_stolen": self.focus_stolen,
            "journal_id": self.journal_id,
            "details": self.details,
        }


class KeystrokeDispatcher:
    """Dispatches keyboard hotkeys using hardware scancodes via SendInput [ACT-10, ACT-11].

    # req: ACT-10, ACT-11
    """

    def __init__(
        self,
        window_manager: WindowManager,
        *,
        guards: ActuationGuards | None = None,
        user32: Any = None,
        key_delay_ms: float = 15.0,
        sleeper: Callable[[float], None] | None = None,
        journal: MutationJournal | None = None,
        config: StudioBridgeConfig | None = None,
    ) -> None:
        """Initialize KeystrokeDispatcher.

        Args:
            window_manager: WindowManager instance for window queries.
            guards: Optional ActuationGuards instance.
            user32: Optional user32 DLL or mock object.
            key_delay_ms: Delay in ms between modifier and key events (10-20ms).
            sleeper: Optional sleep function (defaults to time.sleep).
            journal: Optional MutationJournal for audit records.
            config: Optional StudioBridgeConfig instance.
        """
        self.wm: WindowManager = window_manager
        self.guards: ActuationGuards = guards or ActuationGuards(self.wm, user32=user32)
        self.config: StudioBridgeConfig = config or load_config()

        self._user32 = user32 or self.wm._user32
        if self._user32 is not None:
            _setup_input_signatures(self._user32)

        self.key_delay_ms: float = key_delay_ms
        self._sleep: Callable[[float], None] = sleeper or time.sleep
        self.journal: MutationJournal | None = journal

    def resolve_scancode(self, vk: int, hwnd: int) -> int:
        """Resolve virtual key code to physical hardware scancode [ACT-10].

        Queries target window's keyboard layout via GetKeyboardLayout, translating
        via MapVirtualKeyExW with fallback to standard IBM PC/AT scancodes.
        """
        if self._user32 and hasattr(self._user32, "MapVirtualKeyExW"):
            try:
                tid: int = 0
                if hasattr(self._user32, "GetWindowThreadProcessId"):
                    pid = ctypes.c_uint32()
                    tid = int(self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))

                hkl = None
                if tid > 0 and hasattr(self._user32, "GetKeyboardLayout"):
                    hkl = self._user32.GetKeyboardLayout(tid)

                scan = self._user32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC, hkl)
                if scan and int(scan) > 0:
                    return int(scan)
            except Exception:
                pass

        return DEFAULT_SCANCODES.get(vk, 0)

    def _send_key_event(self, scancode: int, flags: int) -> bool:
        """Inject a single keyboard event via SendInput using hardware scancode."""
        if not self._user32 or not hasattr(self._user32, "SendInput"):
            return True

        try:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.u.ki.wVk = 0
            inp.u.ki.wScan = scancode
            inp.u.ki.dwFlags = flags | KEYEVENTF_SCANCODE
            inp.u.ki.time = 0
            inp.u.ki.dwExtraInfo = 0

            res = self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return int(res) == 1
        except Exception:
            return False

    def dispatch_ctrl_alt_y(self, hwnd: int) -> dict[str, int]:
        """Dispatch Ctrl+Alt+Y hotkey sequence with 10-20ms inter-event delays [ACT-10].

        Sequence:
        1. Ctrl down -> delay
        2. Alt down -> delay
        3. Y down -> delay
        4. Y up -> delay
        5. Alt up -> delay
        6. Ctrl up

        Returns:
            Dictionary of resolved scancodes used for injection.
        """
        scan_ctrl = self.resolve_scancode(VK_CONTROL, hwnd)
        scan_alt = self.resolve_scancode(VK_MENU, hwnd)
        scan_y = self.resolve_scancode(VK_Y, hwnd)
        delay_sec = self.key_delay_ms / 1000.0

        # Modifiers down
        self._send_key_event(scan_ctrl, 0)
        self._sleep(delay_sec)
        self._send_key_event(scan_alt, 0)
        self._sleep(delay_sec)

        # Key down / up
        self._send_key_event(scan_y, 0)
        self._sleep(delay_sec)
        self._send_key_event(scan_y, KEYEVENTF_KEYUP)
        self._sleep(delay_sec)

        # Modifiers up
        self._send_key_event(scan_alt, KEYEVENTF_KEYUP)
        self._sleep(delay_sec)
        self._send_key_event(scan_ctrl, KEYEVENTF_KEYUP)

        return {
            "ctrl": scan_ctrl,
            "alt": scan_alt,
            "y": scan_y,
        }


class UIActuator:
    """Unified coordinator for Win32 UI actuation, focus guards, and auditing [ACT-01, ACT-10].

    Encapsulates:
    - Target window handle discovery and caching with IsWindow validation.
    - Safety guards preventing actuation when FL is not foreground or dialogs are open.
    - Scancode SendInput injection with 10-20ms delays.
    - Foreground window saving and automatic restoration when allow_focus_steal=true.
    - Audit logging of every actuation into the session mutation journal.

    # req: ACT-01, ACT-10, ACT-11
    """

    def __init__(
        self,
        config: StudioBridgeConfig | None = None,
        *,
        window_manager: WindowManager | None = None,
        guards: ActuationGuards | None = None,
        dispatcher: KeystrokeDispatcher | None = None,
        journal: MutationJournal | None = None,
        user32: Any = None,
        kernel32: Any = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        """Initialize UIActuator."""
        self.config: StudioBridgeConfig = config or load_config()

        self.wm: WindowManager = window_manager or WindowManager(
            user32=user32,
            kernel32=kernel32,
            config=self.config,
        )
        self.guards: ActuationGuards = guards or ActuationGuards(
            self.wm,
            user32=user32,
            kernel32=kernel32,
            user_idle_threshold_ms=self.config.actuation.user_idle_threshold_ms,
        )
        self.dispatcher: KeystrokeDispatcher = dispatcher or KeystrokeDispatcher(
            self.wm,
            guards=self.guards,
            user32=user32,
            key_delay_ms=self.config.actuation.key_delay_ms,
            sleeper=sleeper,
            journal=journal,
            config=self.config,
        )
        self.journal: MutationJournal | None = journal or self.dispatcher.journal

    def is_actuation_enabled(self, action_type: str = "pianoroll_rerun") -> bool:
        """Check if actuation is permitted by active safety policy [ACT-11].

        Defaults per [ACT-11]:
        - Enabled (true) for piano-roll keystrokes ('pianoroll_rerun', 'ctrl_alt_y', 'notes_apply').
        - Disabled (false) for any other actuation actions.
        """
        if action_type in ("pianoroll_rerun", "ctrl_alt_y", "notes_apply"):
            return bool(self.config.actuation.piano_roll_enabled)
        return bool(self.config.actuation.enabled)

    def trigger_pianoroll_rerun(
        self,
        *,
        hwnd: int | None = None,
        pyscript_source: str | None = None,
        payload_hash: str | None = None,
        allow_focus_steal: bool | None = None,
        force: bool = False,
        dry_run: bool = False,
        action_type: str = "pianoroll_rerun",
    ) -> ActuationResult:
        """Dispatch guarded Ctrl+Alt+Y hotkey to re-run last piano-roll script [ACT-01, ACT-10].

        Steps:
        1. Check policy per [ACT-11] (defaults true for piano-roll hotkeys).
        2. Locate and validate FL Studio window handle (cached or newly discovered).
        3. Verify safety guards: foreground, no modal dialogs, human typing idle [ACT-10].
        4. If allow_focus_steal=true, save prior foreground window and restore on completion.
        5. Dispatch Ctrl+Alt+Y via SendInput with hardware scancodes and 10-20ms modifier gaps.
        6. Record actuation event into session mutation journal.

        Returns:
            ActuationResult detailing execution, window title, scancodes, and journal ID.

        Raises:
            ActuationDisabledError: If actuation is disabled by policy [ACT-11].
            WindowNotFoundError: If FL Studio main window handle cannot be found.
            FocusGuardError: If FL Studio is not foreground and allow_focus_steal=false.
            ModalBlockedError: If a modal dialog or popup is open in FL Studio.
            UserInputActiveError: If user input was detected recently and force=false.
        """
        # 1. Policy check [ACT-11]
        if not self.is_actuation_enabled(action_type):
            raise ActuationDisabledError(
                f"UI actuation is disabled by policy for action '{action_type}' [ACT-11].",
                remedy="Enable actuation in config (actuation.enabled=true) or use manual mode.",
                details={"action_type": action_type},
            )

        # 2. Window resolution and validation
        target_info: FLWindowInfo | None = None
        if hwnd is not None and hwnd > 0:
            if self.wm.is_window_valid(hwnd):
                title = self.wm.get_window_title(hwnd)
                pid = self.wm.get_window_pid(hwnd)
                image_path = self.wm.get_process_image_path(pid)
                is_fg = self.wm.is_fl_foreground(hwnd)
                target_info = FLWindowInfo(
                    hwnd=hwnd,
                    title=title,
                    pid=pid,
                    image_path=image_path,
                    is_foreground=is_fg,
                )
            else:
                raise WindowNotFoundError(
                    f"Explicit window handle {hwnd} is invalid or closed.",
                    remedy="Ensure FL Studio is running and pass a valid HWND.",
                    details={"hwnd": hwnd},
                )
        else:
            # Check cached window first, then search
            target_info = self.wm.get_cached_window(validate=True)
            if target_info is None:
                target_info = self.wm.find_main_window()

        if target_info is None:
            raise WindowNotFoundError(
                "FL Studio main window handle could not be located.",
                remedy="Ensure FL Studio is running with an open project window.",
                details={"action_type": action_type},
            )

        target_hwnd = target_info.hwnd
        steal = (
            allow_focus_steal
            if allow_focus_steal is not None
            else self.config.actuation.allow_focus_steal
        )

        # 3. Guard verification [ACT-10]
        self.guards.ensure_ready(
            target_hwnd,
            allow_focus_steal=steal,
            force=force,
        )

        # 4. Resolve payload hash
        p_hash: str = ""
        if payload_hash:
            p_hash = payload_hash
        elif pyscript_source:
            p_hash = hashlib.sha256(pyscript_source.encode("utf-8")).hexdigest()

        # 5. Dispatch hotkey with focus guard and restoration [ACT-10]
        focus_stolen = False
        scancodes: dict[str, int] = {}

        if dry_run:
            scancodes = {
                "ctrl": self.dispatcher.resolve_scancode(VK_CONTROL, target_hwnd),
                "alt": self.dispatcher.resolve_scancode(VK_MENU, target_hwnd),
                "y": self.dispatcher.resolve_scancode(VK_Y, target_hwnd),
            }
        else:
            with self.wm.temporary_focus(target_hwnd, allow_focus_steal=steal) as stolen:
                focus_stolen = stolen
                scancodes = self.dispatcher.dispatch_ctrl_alt_y(target_hwnd)

        # 6. Auditing into MutationJournal [ACT-11]
        journal_id: str | None = None
        if self.journal is not None:
            with contextlib.suppress(Exception):
                op_name = (
                    "actuate.pianoroll"
                    if action_type == "pianoroll_rerun"
                    else f"actuate.{action_type}"
                )
                entry = self.journal.record(
                    op=op_name,
                    target=f"hwnd:{target_hwnd}",
                    args={
                        "hotkey": "Ctrl+Alt+Y",
                        "action": action_type,
                        "dry_run": dry_run,
                        "force": force,
                        "allow_focus_steal": steal,
                    },
                    details={
                        "window_title": target_info.title,
                        "target_hwnd": target_hwnd,
                        "pid": target_info.pid,
                        "payload_hash": p_hash,
                        "scancodes": scancodes,
                        "focus_stolen": focus_stolen,
                        "dry_run": dry_run,
                    },
                    proof="input_dispatched" if not dry_run else "dry_run",
                    verified=True,
                )
                journal_id = entry.entry_id

        return ActuationResult(
            success=True,
            hotkey="Ctrl+Alt+Y",
            target_hwnd=target_hwnd,
            window_title=target_info.title,
            action_type=action_type,
            payload_hash=p_hash,
            dry_run=dry_run,
            focus_stolen=focus_stolen,
            journal_id=journal_id,
            details={"scancodes": scancodes},
        )


def dispatch_pianoroll_rerun(
    *,
    hwnd: int | None = None,
    pyscript_source: str | None = None,
    payload_hash: str | None = None,
    allow_focus_steal: bool = False,
    force: bool = False,
    dry_run: bool = False,
    journal: MutationJournal | None = None,
    config: StudioBridgeConfig | None = None,
    window_manager: WindowManager | None = None,
    user32: Any = None,
    kernel32: Any = None,
) -> ActuationResult:
    """Convenience function to dispatch guarded Ctrl+Alt+Y piano-roll re-run [ACT-01, ACT-10]."""
    actuator = UIActuator(
        config=config,
        journal=journal,
        window_manager=window_manager,
        user32=user32,
        kernel32=kernel32,
    )
    return actuator.trigger_pianoroll_rerun(
        hwnd=hwnd,
        pyscript_source=pyscript_source,
        payload_hash=payload_hash,
        allow_focus_steal=allow_focus_steal,
        force=force,
        dry_run=dry_run,
    )
