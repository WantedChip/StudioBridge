"""Win32 user32 and kernel32 ctypes bindings and WindowManager for FL Studio [ACT-01, ACT-10].

Implements zero-dependency Win32 UI actuation primitives using ctypes calling
user32.dll and kernel32.dll to locate FL Studio window handles, verify focus,
track window visibility, and manage focus transitions per spec 06_l0d §4, §5.
"""

from __future__ import annotations

import contextlib
import ctypes
import sys
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from studiobridge.core.config import StudioBridgeConfig, load_config

# Win32 Process Access Flags
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Win32 Window Relationships
GW_HWNDNEXT = 2
GW_OWNER = 4
GW_ENABLEDPOPUP = 6

# Window Styles
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

# Machine Architecture Constants (IMAGE_FILE_MACHINE_*)
IMAGE_FILE_MACHINE_UNKNOWN = 0
IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64

MACHINE_ARCH_NAMES: dict[int, str] = {
    IMAGE_FILE_MACHINE_UNKNOWN: "unknown",
    IMAGE_FILE_MACHINE_I386: "x86",
    IMAGE_FILE_MACHINE_AMD64: "x64",
    IMAGE_FILE_MACHINE_ARM64: "arm64",
}

# Cross-platform callback function type definition
if hasattr(ctypes, "WINFUNCTYPE"):
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)
else:
    WNDENUMPROC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t)


@dataclass(frozen=True, slots=True)
class FLWindowInfo:
    """Detailed metadata for an identified FL Studio window handle [ACT-01].

    Attributes:
        hwnd: Native Win32 window handle (integer representation).
        title: Window title string.
        pid: Process identifier.
        image_path: Full path to the executable image (e.g. '...\\FL64.exe').
        is_foreground: True if this window currently has foreground focus.
        is_visible: True if window is currently visible.
        dpi: DPI value reported by OS for this window (default 96).
        class_name: Win32 window class name.
        architecture: Target process machine architecture ('x64', 'arm64', 'x86').
    """

    hwnd: int
    title: str
    pid: int
    image_path: str
    is_foreground: bool
    is_visible: bool = True
    dpi: int = 96
    class_name: str = ""
    architecture: str = "x64"

    def to_dict(self) -> dict[str, Any]:
        """Serialize window metadata to dictionary."""
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "pid": self.pid,
            "image_path": self.image_path,
            "is_foreground": self.is_foreground,
            "is_visible": self.is_visible,
            "dpi": self.dpi,
            "class_name": self.class_name,
            "architecture": self.architecture,
        }


def _setup_user32_signatures(user32: Any) -> None:
    """Configure ctypes argtypes and restype for user32 functions."""
    with contextlib.suppress(Exception):
        user32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.c_ssize_t]
        user32.EnumWindows.restype = ctypes.c_int
        user32.IsWindow.argtypes = [ctypes.c_void_p]
        user32.IsWindow.restype = ctypes.c_int
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        user32.IsWindowVisible.restype = ctypes.c_int
        user32.IsWindowEnabled.argtypes = [ctypes.c_void_p]
        user32.IsWindowEnabled.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.GetClassNameW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        user32.SetForegroundWindow.restype = ctypes.c_int
        user32.GetLastActivePopup.argtypes = [ctypes.c_void_p]
        user32.GetLastActivePopup.restype = ctypes.c_void_p
        user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetWindow.restype = ctypes.c_void_p
        if hasattr(user32, "GetDpiForWindow"):
            user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
            user32.GetDpiForWindow.restype = ctypes.c_uint


def _setup_kernel32_signatures(kernel32: Any) -> None:
    """Configure ctypes argtypes and restype for kernel32 functions."""
    with contextlib.suppress(Exception):
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        if hasattr(kernel32, "QueryFullProcessImageNameW"):
            kernel32.QueryFullProcessImageNameW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
        if hasattr(kernel32, "IsWow64Process2"):
            kernel32.IsWow64Process2.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint16),
                ctypes.POINTER(ctypes.c_uint16),
            ]
            kernel32.IsWow64Process2.restype = ctypes.c_int


class WindowManager:
    """Manages window discovery, HWND caching, focus tracking, and state validation for FL Studio.

    # req: ACT-01, ACT-10
    """

    def __init__(
        self,
        *,
        user32: Any = None,
        kernel32: Any = None,
        config: StudioBridgeConfig | None = None,
    ) -> None:
        """Initialize WindowManager with optional mock DLLs and configuration."""
        self.config: StudioBridgeConfig = config or load_config()

        self._user32 = user32
        if self._user32 is None and sys.platform == "win32":
            with contextlib.suppress(Exception):
                self._user32 = ctypes.WinDLL("user32", use_last_error=True)
                _setup_user32_signatures(self._user32)
        elif self._user32 is not None:
            _setup_user32_signatures(self._user32)

        self._kernel32 = kernel32
        if self._kernel32 is None and sys.platform == "win32":
            with contextlib.suppress(Exception):
                self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                _setup_kernel32_signatures(self._kernel32)
        elif self._kernel32 is not None:
            _setup_kernel32_signatures(self._kernel32)

        self._cached_window: FLWindowInfo | None = None

    @property
    def is_available(self) -> bool:
        """True if Win32 user32 backend is accessible."""
        return self._user32 is not None

    def find_fl_windows(self) -> list[FLWindowInfo]:
        """Enumerate all top-level windows and identify running FL Studio instances.

        Matches process executable name matching 'FL64.exe' or 'FL.exe', recording
        window handle (HWND), title, PID, DPI, architecture, and foreground status.
        Tool windows and invisible helper windows are filtered out.

        # req: ACT-01
        """
        if not self._user32:
            return []

        found: list[FLWindowInfo] = []
        fg_hwnd = self.get_foreground_window()

        def enum_window_callback(hwnd_val: Any, _lparam: Any) -> int:
            hwnd = int(hwnd_val) if hwnd_val else 0
            if not hwnd:
                return 1

            # Skip non-visible windows
            if not self.is_window_visible(hwnd):
                return 1

            # Skip tool windows
            ex_style = self.get_window_ex_style(hwnd)
            if ex_style & WS_EX_TOOLWINDOW:
                return 1

            # Resolve process ID
            pid = self.get_window_pid(hwnd)
            if pid <= 0:
                return 1

            # Check process executable image path
            image_path = self.get_process_image_path(pid)
            if not image_path:
                return 1

            exe_name = Path(image_path).name.lower()
            if exe_name not in ("fl64.exe", "fl.exe"):
                return 1

            title = self.get_window_title(hwnd)
            class_name = self.get_window_class_name(hwnd)
            dpi = self.get_window_dpi(hwnd)
            arch = self.get_process_architecture(pid)
            is_fg = hwnd == fg_hwnd

            found.append(
                FLWindowInfo(
                    hwnd=hwnd,
                    title=title,
                    pid=pid,
                    image_path=image_path,
                    is_foreground=is_fg,
                    is_visible=True,
                    dpi=dpi,
                    class_name=class_name,
                    architecture=arch,
                )
            )
            return 1

        try:
            cb = WNDENUMPROC(enum_window_callback)
            self._user32.EnumWindows(cb, 0)
        except Exception:
            pass

        return found

    def find_main_window(
        self,
        fl_install_dir: Path | str | None = None,
    ) -> FLWindowInfo | None:
        """Find and cache the primary FL Studio application window handle [ACT-01].

        Args:
            fl_install_dir: Optional installation directory filter if multiple FL versions coexist.

        Returns:
            FLWindowInfo if located and verified, None otherwise.
        """
        windows = self.find_fl_windows()
        if not windows:
            return None

        # Filter by configured or passed install directory if multiple versions exist
        target_dir = fl_install_dir or self.config.fl_install_dir
        if target_dir is not None:
            norm_dir = Path(target_dir).resolve()
            matched = [
                w
                for w in windows
                if norm_dir in Path(w.image_path).resolve().parents
                or str(norm_dir).lower() in w.image_path.lower()
            ]
            if matched:
                windows = matched

        # Heuristic 1: Filter windows that have no owner (main application frame)
        unowned = [w for w in windows if self.get_window_owner(w.hwnd) == 0]
        candidates = unowned if unowned else windows

        # Heuristic 2: Prefer window whose title contains "FL Studio"
        title_candidates = [w for w in candidates if "fl studio" in w.title.lower()]
        if title_candidates:
            candidates = title_candidates

        # Heuristic 3: Prefer foreground window if among candidates
        fg_candidates = [w for w in candidates if w.is_foreground]
        if fg_candidates:
            selected = fg_candidates[0]
        else:
            # Heuristic 4: Pick the window with longest title (usually displays project name)
            selected = max(candidates, key=lambda w: len(w.title))

        self._cached_window = selected
        return selected

    def get_cached_window(self, validate: bool = True) -> FLWindowInfo | None:
        """Return the cached FLWindowInfo, validating window handle if requested [ACT-01].

        If validate=True, verifies user32.IsWindow(hwnd). If the window is no longer
        valid, clears the cache and returns None.
        """
        if self._cached_window is None:
            return None

        if validate:
            if self.is_window_valid(self._cached_window.hwnd):
                is_fg = self.is_fl_foreground(self._cached_window.hwnd)
                title = self.get_window_title(self._cached_window.hwnd) or self._cached_window.title
                self._cached_window = replace(self._cached_window, is_foreground=is_fg, title=title)
                return self._cached_window
            else:
                self._cached_window = None
                return None

        return self._cached_window

    def clear_cache(self) -> None:
        """Clear the cached window handle."""
        self._cached_window = None

    def is_window_valid(self, hwnd: int) -> bool:
        """Validate if a window handle exists and is an active Win32 window."""
        if not self._user32 or hwnd <= 0:
            return False
        try:
            return bool(self._user32.IsWindow(hwnd))
        except Exception:
            return False

    def is_window_visible(self, hwnd: int) -> bool:
        """Check if a window is visible."""
        if not self._user32 or hwnd <= 0:
            return False
        try:
            return bool(self._user32.IsWindowVisible(hwnd))
        except Exception:
            return False

    def is_window_enabled(self, hwnd: int) -> bool:
        """Check if a window is enabled (not disabled by a modal dialog)."""
        if not self._user32 or hwnd <= 0:
            return False
        try:
            return bool(self._user32.IsWindowEnabled(hwnd))
        except Exception:
            return False

    def get_foreground_window(self) -> int:
        """Return the Win32 handle of the current foreground window."""
        if not self._user32:
            return 0
        try:
            hwnd = self._user32.GetForegroundWindow()
            return int(hwnd) if hwnd else 0
        except Exception:
            return 0

    def is_fl_foreground(self, hwnd: int | None = None) -> bool:
        """Check if FL Studio is currently the foreground window [ACT-10]."""
        target = hwnd or (self._cached_window.hwnd if self._cached_window else 0)
        if not self._user32 or target <= 0:
            return False

        try:
            fg = self.get_foreground_window()
            if fg == target:
                return True

            # Also consider foreground if the active window belongs to the same process
            pid_fg = self.get_window_pid(fg)
            pid_target = self.get_window_pid(target)
            return pid_fg > 0 and pid_fg == pid_target
        except Exception:
            return False

    def save_foreground_window(self) -> int:
        """Save and return the current active foreground window handle."""
        return self.get_foreground_window()

    def restore_foreground_window(self, prev_hwnd: int) -> bool:
        """Restore foreground focus to a previously active window handle [ACT-10]."""
        if not self._user32 or prev_hwnd <= 0:
            return False
        if not self.is_window_valid(prev_hwnd):
            return False
        try:
            return bool(self._user32.SetForegroundWindow(prev_hwnd))
        except Exception:
            return False

    def bring_to_foreground(self, hwnd: int) -> bool:
        """Bring target window handle to the foreground."""
        if not self._user32 or hwnd <= 0:
            return False
        try:
            return bool(self._user32.SetForegroundWindow(hwnd))
        except Exception:
            return False

    @contextlib.contextmanager
    def temporary_focus(
        self,
        target_hwnd: int,
        allow_focus_steal: bool = False,
    ) -> Iterator[bool]:
        """Temporarily transfer focus to target window if allowed [ACT-10].

        Restores previous foreground window on exit.

        Args:
            target_hwnd: Target window handle to focus.
            allow_focus_steal: True if focus steal is permitted by safety policy.

        Yields:
            True if focus was actively stolen and transferred, False otherwise.
        """
        if not allow_focus_steal:
            yield False
            return

        is_fg = self.is_fl_foreground(target_hwnd)
        if is_fg:
            yield False
            return

        prev = self.save_foreground_window()
        stolen = self.bring_to_foreground(target_hwnd)
        try:
            yield stolen
        finally:
            if prev and prev != target_hwnd and self.is_window_valid(prev):
                self.restore_foreground_window(prev)

    def get_window_title(self, hwnd: int) -> str:
        """Retrieve window title string."""
        if not self._user32 or hwnd <= 0:
            return ""
        try:
            length = self._user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            res = self._user32.GetWindowTextW(hwnd, buf, length + 1)
            if isinstance(res, str):
                return res
            return buf.value[:res] if isinstance(res, int) else buf.value
        except Exception:
            return ""

    def get_window_class_name(self, hwnd: int) -> str:
        """Retrieve Win32 class name for window."""
        if not self._user32 or hwnd <= 0:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(256)
            res = self._user32.GetClassNameW(hwnd, buf, 256)
            if isinstance(res, str):
                return res
            return buf.value[:res] if isinstance(res, int) else buf.value
        except Exception:
            return ""

    def get_window_pid(self, hwnd: int) -> int:
        """Retrieve process ID owning the window handle."""
        if not self._user32 or hwnd <= 0:
            return 0
        try:
            pid = ctypes.c_uint32()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return int(pid.value)
        except Exception:
            return 0

    def get_window_dpi(self, hwnd: int) -> int:
        """Retrieve DPI for window handle, defaulting to 96."""
        if not self._user32 or hwnd <= 0:
            return 96
        try:
            if hasattr(self._user32, "GetDpiForWindow"):
                dpi = self._user32.GetDpiForWindow(hwnd)
                if dpi and dpi > 0:
                    return int(dpi)
        except Exception:
            pass
        return 96

    def get_window_owner(self, hwnd: int) -> int:
        """Retrieve owner window handle (GW_OWNER). Top-level unowned windows return 0."""
        if not self._user32 or hwnd <= 0:
            return 0
        try:
            owner = self._user32.GetWindow(hwnd, GW_OWNER)
            return int(owner) if owner else 0
        except Exception:
            return 0

    def get_window_ex_style(self, hwnd: int) -> int:
        """Retrieve extended window style flags."""
        if not self._user32 or hwnd <= 0:
            return 0
        try:
            fn = getattr(self._user32, "GetWindowLongPtrW", None) or getattr(
                self._user32, "GetWindowLongW", None
            )
            if fn:
                return int(fn(hwnd, GWL_EXSTYLE))
        except Exception:
            pass
        return 0

    def get_last_active_popup(self, hwnd: int) -> int:
        """Retrieve handle of last active popup owned by window handle."""
        if not self._user32 or hwnd <= 0:
            return 0
        try:
            popup = self._user32.GetLastActivePopup(hwnd)
            return int(popup) if popup else 0
        except Exception:
            return 0

    def get_enabled_popup(self, hwnd: int) -> int:
        """Retrieve enabled popup window handle via GW_ENABLEDPOPUP."""
        if not self._user32 or hwnd <= 0:
            return 0
        try:
            popup = self._user32.GetWindow(hwnd, GW_ENABLEDPOPUP)
            return int(popup) if popup else 0
        except Exception:
            return 0

    def get_process_image_path(self, pid: int) -> str:
        """Query executable image path for given process ID."""
        if not self._kernel32 or pid <= 0:
            return ""
        h_proc = None
        try:
            h_proc = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_uint32(1024)
            if hasattr(self._kernel32, "QueryFullProcessImageNameW"):
                res = self._kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
                if isinstance(res, str):
                    return res
                if res:
                    return buf.value
            return ""
        except Exception:
            return ""
        finally:
            if h_proc and hasattr(self._kernel32, "CloseHandle"):
                with contextlib.suppress(Exception):
                    self._kernel32.CloseHandle(h_proc)

    def get_process_architecture(self, pid: int) -> str:
        """Query process machine architecture using IsWow64Process2."""
        if not self._kernel32 or pid <= 0:
            return "x64"
        h_proc = None
        try:
            h_proc = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                return "x64"
            if hasattr(self._kernel32, "IsWow64Process2"):
                proc_machine = ctypes.c_uint16()
                native_machine = ctypes.c_uint16()
                res = self._kernel32.IsWow64Process2(
                    h_proc,
                    ctypes.byref(proc_machine),
                    ctypes.byref(native_machine),
                )
                if res:
                    pm = proc_machine.value
                    nm = native_machine.value
                    if pm == IMAGE_FILE_MACHINE_UNKNOWN:
                        return MACHINE_ARCH_NAMES.get(nm, "x64")
                    return MACHINE_ARCH_NAMES.get(pm, "x64")
            return "x64"
        except Exception:
            return "x64"
        finally:
            if h_proc and hasattr(self._kernel32, "CloseHandle"):
                with contextlib.suppress(Exception):
                    self._kernel32.CloseHandle(h_proc)
