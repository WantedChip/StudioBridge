"""Unit tests for Win32 WindowManager and FL Studio window discovery [ACT-01, ACT-10]."""

from __future__ import annotations

from typing import Any

import pytest

from studiobridge.actuate.win32 import (
    WS_EX_TOOLWINDOW,
    WindowManager,
)


def set_ptr_val(ptr: Any, val: Any) -> None:
    """Helper to set value on either ctypes byref pointer or POINTER."""
    if ptr is None:
        return
    if hasattr(ptr, "_obj"):
        ptr._obj.value = val
    elif hasattr(ptr, "contents"):
        ptr.contents.value = val
    elif hasattr(ptr, "value"):
        ptr.value = val


class MockUser32:
    """Mock user32 DLL for deterministic window enumeration and focus tests."""

    def __init__(self) -> None:
        self.windows: dict[int, dict[str, Any]] = {}
        self.foreground_hwnd: int = 0

    def add_window(
        self,
        hwnd: int,
        title: str,
        pid: int,
        is_visible: bool = True,
        is_enabled: bool = True,
        class_name: str = "FL64Frame",
        ex_style: int = 0,
        dpi: int = 96,
        owner: int = 0,
        popup: int | None = None,
        enabled_popup: int | None = None,
    ) -> None:
        self.windows[hwnd] = {
            "title": title,
            "pid": pid,
            "is_visible": is_visible,
            "is_enabled": is_enabled,
            "class_name": class_name,
            "ex_style": ex_style,
            "dpi": dpi,
            "owner": owner,
            "popup": popup if popup is not None else hwnd,
            "enabled_popup": enabled_popup if enabled_popup is not None else hwnd,
        }

    def EnumWindows(self, callback: Any, lparam: Any) -> int:
        for hwnd in list(self.windows.keys()):
            if not callback(hwnd, lparam):
                break
        return 1

    def IsWindow(self, hwnd: int) -> int:
        return 1 if hwnd in self.windows else 0

    def IsWindowVisible(self, hwnd: int) -> int:
        return 1 if self.windows.get(hwnd, {}).get("is_visible", False) else 0

    def IsWindowEnabled(self, hwnd: int) -> int:
        return 1 if self.windows.get(hwnd, {}).get("is_enabled", True) else 0

    def GetWindowTextLengthW(self, hwnd: int) -> int:
        return len(self.windows.get(hwnd, {}).get("title", ""))

    def GetWindowTextW(self, hwnd: int, buf: Any, max_count: int) -> int:
        title = self.windows.get(hwnd, {}).get("title", "")
        if hasattr(buf, "value"):
            buf.value = title
        return len(title)

    def GetClassNameW(self, hwnd: int, buf: Any, max_count: int) -> int:
        cname = self.windows.get(hwnd, {}).get("class_name", "")
        if hasattr(buf, "value"):
            buf.value = cname
        return len(cname)

    def GetWindowThreadProcessId(self, hwnd: int, pid_ptr: Any) -> int:
        pid = self.windows.get(hwnd, {}).get("pid", 0)
        set_ptr_val(pid_ptr, pid)
        return 1000

    def GetForegroundWindow(self) -> int:
        return self.foreground_hwnd

    def SetForegroundWindow(self, hwnd: int) -> int:
        if hwnd in self.windows:
            self.foreground_hwnd = hwnd
            return 1
        return 0

    def GetWindow(self, hwnd: int, ucmd: int) -> int:
        if ucmd == 4:  # GW_OWNER
            return self.windows.get(hwnd, {}).get("owner", 0)
        if ucmd == 6:  # GW_ENABLEDPOPUP
            return self.windows.get(hwnd, {}).get("enabled_popup", hwnd)
        return 0

    def GetLastActivePopup(self, hwnd: int) -> int:
        return self.windows.get(hwnd, {}).get("popup", hwnd)

    def GetWindowLongW(self, hwnd: int, index: int) -> int:
        return self.windows.get(hwnd, {}).get("ex_style", 0)

    def GetWindowLongPtrW(self, hwnd: int, index: int) -> int:
        return self.windows.get(hwnd, {}).get("ex_style", 0)

    def GetDpiForWindow(self, hwnd: int) -> int:
        return self.windows.get(hwnd, {}).get("dpi", 96)


class MockKernel32:
    """Mock kernel32 DLL for process queries and architecture detection."""

    def __init__(self) -> None:
        self.processes: dict[int, dict[str, Any]] = {}

    def add_process(self, pid: int, image_path: str, arch: str = "x64") -> None:
        self.processes[pid] = {
            "image_path": image_path,
            "arch": arch,
        }

    def OpenProcess(self, access: int, inherit: int, pid: int) -> int:
        if pid in self.processes:
            return 0x9000 + pid
        return 0

    def CloseHandle(self, handle: int) -> int:
        return 1

    def QueryFullProcessImageNameW(self, handle: int, flags: int, buf: Any, size_ptr: Any) -> int:
        pid = handle - 0x9000
        path = self.processes.get(pid, {}).get("image_path", "")
        if hasattr(buf, "value"):
            buf.value = path
        return 1 if path else 0

    def IsWow64Process2(self, handle: int, proc_machine_ptr: Any, native_machine_ptr: Any) -> int:
        pid = handle - 0x9000
        arch = self.processes.get(pid, {}).get("arch", "x64")
        if arch == "arm64":
            set_ptr_val(native_machine_ptr, 0xAA64)  # native ARM64
            set_ptr_val(proc_machine_ptr, 0x8664)  # emulated x64
        elif arch == "x64":
            set_ptr_val(native_machine_ptr, 0x8664)
            set_ptr_val(proc_machine_ptr, 0)
        elif arch == "x86":
            set_ptr_val(proc_machine_ptr, 0x014C)
        return 1


@pytest.fixture
def mock_win32_env() -> tuple[MockUser32, MockKernel32]:
    u32 = MockUser32()
    k32 = MockKernel32()
    return u32, k32


def test_window_manager_locates_fl64_windows(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify WindowManager enumerates and identifies running FL64.exe windows.

    # req: ACT-01
    """
    u32, k32 = mock_win32_env
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    k32.add_process(5678, r"C:\Windows\explorer.exe")

    u32.add_window(101, "FL Studio 2024 - Project1.flp", 1234, is_visible=True, dpi=120)
    u32.add_window(202, "File Explorer", 5678, is_visible=True)

    wm = WindowManager(user32=u32, kernel32=k32)
    windows = wm.find_fl_windows()

    assert len(windows) == 1
    w = windows[0]
    assert w.hwnd == 101
    assert "FL Studio 2024" in w.title
    assert w.pid == 1234
    assert w.image_path == r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe"
    assert w.dpi == 120
    assert w.architecture == "x64"


def test_window_manager_skips_tool_and_invisible_windows(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify tooltips and invisible windows are excluded from discovery.

    # req: ACT-01
    """
    u32, k32 = mock_win32_env
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")

    # Main visible window
    u32.add_window(101, "FL Studio 2024", 1234, is_visible=True)
    # Invisible helper window
    u32.add_window(102, "FL Hidden Worker", 1234, is_visible=False)
    # Tool window (e.g. tooltip or floating palette)
    u32.add_window(103, "FL Tooltip", 1234, is_visible=True, ex_style=WS_EX_TOOLWINDOW)

    wm = WindowManager(user32=u32, kernel32=k32)
    windows = wm.find_fl_windows()

    assert len(windows) == 1
    assert windows[0].hwnd == 101


def test_window_manager_find_main_window_caching_and_validation(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify WindowManager caches main window handle and validates with IsWindow.

    # req: ACT-01
    """
    u32, k32 = mock_win32_env
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    u32.add_window(101, "FL Studio 2024 - Demo.flp", 1234, is_visible=True)

    wm = WindowManager(user32=u32, kernel32=k32)
    assert wm.get_cached_window() is None

    main_win = wm.find_main_window()
    assert main_win is not None
    assert main_win.hwnd == 101

    # Returns cached window
    cached = wm.get_cached_window(validate=True)
    assert cached is not None
    assert cached.hwnd == 101

    # Simulate window closure
    del u32.windows[101]

    # With validation, cached window is invalidated and cleared
    invalidated = wm.get_cached_window(validate=True)
    assert invalidated is None
    assert wm.get_cached_window(validate=False) is None


def test_window_manager_handles_multiple_fl_installs(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify WindowManager can filter windows by specific fl_install_dir.

    # req: ACT-01
    """
    u32, k32 = mock_win32_env
    k32.add_process(1001, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    k32.add_process(2002, r"C:\Program Files\Image-Line\FL Studio 2025\FL64.exe")

    u32.add_window(101, "FL Studio 2024 - Project A.flp", 1001, is_visible=True)
    u32.add_window(202, "FL Studio 2025 - Project B.flp", 2002, is_visible=True)

    wm = WindowManager(user32=u32, kernel32=k32)

    # Filter for FL Studio 2025
    selected_2025 = wm.find_main_window(
        fl_install_dir=r"C:\Program Files\Image-Line\FL Studio 2025"
    )
    assert selected_2025 is not None
    assert selected_2025.hwnd == 202
    assert selected_2025.pid == 2002

    # Filter for FL Studio 2024
    selected_2024 = wm.find_main_window(
        fl_install_dir=r"C:\Program Files\Image-Line\FL Studio 2024"
    )
    assert selected_2024 is not None
    assert selected_2024.hwnd == 101


def test_window_manager_architecture_detection_arm64(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify process architecture detection correctly identifies ARM64 emulated x64.

    # req: ACT-01
    """
    u32, k32 = mock_win32_env
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe", arch="arm64")
    u32.add_window(101, "FL Studio 2024", 1234, is_visible=True)

    wm = WindowManager(user32=u32, kernel32=k32)
    win = wm.find_main_window()
    assert win is not None
    assert win.architecture == "x64"  # emulated x64 machine on ARM64


def test_window_manager_foreground_and_temporary_focus_restoration(
    mock_win32_env: tuple[MockUser32, MockKernel32],
) -> None:
    """Verify foreground detection, saving, and restoration via temporary_focus.

    # req: ACT-10
    """
    u32, k32 = mock_win32_env
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    k32.add_process(5678, r"C:\Program Files\Code\Code.exe")

    u32.add_window(101, "FL Studio 2024", 1234, is_visible=True)
    u32.add_window(202, "Visual Studio Code", 5678, is_visible=True)

    # Initial active foreground is Code
    u32.foreground_hwnd = 202

    wm = WindowManager(user32=u32, kernel32=k32)
    assert wm.is_fl_foreground(101) is False
    assert wm.get_foreground_window() == 202

    # 1. Without allow_focus_steal: focus is not changed
    with wm.temporary_focus(101, allow_focus_steal=False) as stolen:
        assert stolen is False
        assert wm.get_foreground_window() == 202

    assert wm.get_foreground_window() == 202

    # 2. With allow_focus_steal: focus moves to FL Studio and restores on exit
    with wm.temporary_focus(101, allow_focus_steal=True) as stolen:
        assert stolen is True
        assert wm.get_foreground_window() == 101

    # Restored to Code
    assert wm.get_foreground_window() == 202
