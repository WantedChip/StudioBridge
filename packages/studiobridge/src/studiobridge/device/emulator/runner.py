"""Device script emulator harness hosting controller scripts in simulated FL Studio sandbox.

Runs device scripts under Python 3.9-constrained environment per [DEV-30] and
05_l0c_device_script_manifest.md §9.
"""

from __future__ import annotations

import contextlib
import pathlib
import sys
import types
from typing import Any

from studiobridge.device.emulator.mock_fl import (
    FORBIDDEN_MODULES,
    MockFLState,
    SandboxImportBlocker,
    create_mock_fl_modules,
)


class MockSysExEvent:
    """Mock event passed to OnSysEx(event) by FL Studio."""

    def __init__(self, sysex: bytes | bytearray) -> None:
        self.sysex = bytes(sysex)
        self.handled = False


class DeviceEmulator:
    """Harness hosting and testing FL Studio controller scripts."""

    def __init__(
        self,
        script_dir: pathlib.Path | str | None = None,
        script_file: pathlib.Path | str | None = None,
        script_code: str | None = None,
        device_name: str = "StudioBridge",
        enforce_sandbox: bool = True,
    ) -> None:
        self.script_dir = pathlib.Path(script_dir) if script_dir else None
        self.script_file = pathlib.Path(script_file) if script_file else None
        self.script_code = script_code
        self.device_name = device_name
        self.enforce_sandbox = enforce_sandbox

        self.state: MockFLState = MockFLState()
        self.blocker: SandboxImportBlocker = SandboxImportBlocker()
        self.script_mod: types.ModuleType | None = None

        self._installed_mod_names: list[str] = []
        self._stashed_modules: dict[str, types.ModuleType] = {}
        self._orig_sys_path: list[str] = []
        self._is_running: bool = False

    @property
    def fl(self) -> MockFLState:
        """Access mock FL Studio state."""
        return self.state

    def start(self) -> DeviceEmulator:
        """Start the emulator, install mocks, load the script, and invoke OnInit()."""
        if self._is_running:
            return self

        self._orig_sys_path = list(sys.path)

        if self.enforce_sandbox:
            # Stash forbidden modules currently in sys.modules
            self._stashed_modules = {}
            for mod_name in list(sys.modules.keys()):
                root = mod_name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    self._stashed_modules[mod_name] = sys.modules.pop(mod_name)

        # 1. Install mock FL modules
        mock_mods = create_mock_fl_modules(self.state)
        self._installed_mod_names = list(mock_mods.keys())
        for name, mod in mock_mods.items():
            sys.modules[name] = mod

        # 2. Install sandbox import blocker
        if self.enforce_sandbox and self.blocker not in sys.meta_path:
            sys.meta_path.insert(0, self.blocker)

        # 3. Configure sys.path
        if self.script_dir:
            sys.path.insert(0, str(self.script_dir))
        elif self.script_file:
            sys.path.insert(0, str(self.script_file.parent))

        # 4. Resolve and execute script code
        mod_name = f"device_{self.device_name}"
        self.script_mod = types.ModuleType(mod_name)
        sys.modules[mod_name] = self.script_mod
        self._installed_mod_names.append(mod_name)

        target_file_path: str = ""
        if self.script_code is not None:
            code = self.script_code
            if self.script_file:
                target_file_path = str(self.script_file)
            elif self.script_dir:
                target_file_path = str(self.script_dir / f"{mod_name}.py")
            else:
                target_file_path = "device.py"
        elif self.script_file is not None:
            code = self.script_file.read_text(encoding="utf-8")
            target_file_path = str(self.script_file)
        elif self.script_dir is not None:
            entry_path = self.script_dir / f"{mod_name}.py"
            if not entry_path.exists():
                raise FileNotFoundError(f"Entry script not found at {entry_path}")
            code = entry_path.read_text(encoding="utf-8")
            target_file_path = str(entry_path)
        else:
            raise ValueError("Must provide script_dir, script_file, or script_code")

        self.script_mod.__file__ = target_file_path

        # Execute script in its module namespace
        exec(compile(code, target_file_path, "exec"), self.script_mod.__dict__)

        # 5. Call OnInit()
        if hasattr(self.script_mod, "OnInit"):
            self.script_mod.OnInit()

        self._is_running = True
        return self

    def stop(self) -> None:
        """Call OnDeInit(), restore sys.modules, sys.meta_path, and sys.path."""
        if not self._is_running:
            return

        # 1. Call OnDeInit()
        if self.script_mod and hasattr(self.script_mod, "OnDeInit"):
            with contextlib.suppress(Exception):
                self.script_mod.OnDeInit()

        # 2. Remove mock modules from sys.modules
        for name in self._installed_mod_names:
            sys.modules.pop(name, None)

        if self.enforce_sandbox:
            # Restore stashed forbidden modules
            for mod_name, mod in self._stashed_modules.items():
                sys.modules[mod_name] = mod
            self._stashed_modules.clear()

            # 3. Remove import blocker
            if self.blocker in sys.meta_path:
                sys.meta_path.remove(self.blocker)

        # 4. Restore sys.path
        sys.path = self._orig_sys_path
        self._is_running = False

    def __enter__(self) -> DeviceEmulator:
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def send_sysex(self, data: bytes | bytearray) -> bool:
        """Send SysEx frame to the script's OnSysEx handler.

        Returns:
            True if the script marked the event as handled, False otherwise.
        """
        if not self._is_running or not self.script_mod:
            raise RuntimeError("DeviceEmulator is not running")

        event = MockSysExEvent(data)
        if hasattr(self.script_mod, "OnSysEx"):
            self.script_mod.OnSysEx(event)
        return event.handled

    def idle(self, ticks: int = 1) -> None:
        """Trigger one or more OnIdle() ticks."""
        if not self._is_running or not self.script_mod:
            raise RuntimeError("DeviceEmulator is not running")

        if hasattr(self.script_mod, "OnIdle"):
            for _ in range(ticks):
                self.script_mod.OnIdle()

    def project_load(self, status: int = 0) -> None:
        """Trigger OnProjectLoad() event."""
        if not self._is_running or not self.script_mod:
            raise RuntimeError("DeviceEmulator is not running")

        if hasattr(self.script_mod, "OnProjectLoad"):
            self.script_mod.OnProjectLoad(status)

    def refresh(self, flags: int = 0) -> None:
        """Trigger OnRefresh() event."""
        if not self._is_running or not self.script_mod:
            raise RuntimeError("DeviceEmulator is not running")

        if hasattr(self.script_mod, "OnRefresh"):
            self.script_mod.OnRefresh(flags)

    def get_sent_sysex(self) -> list[bytes]:
        """Retrieve all SysEx frames sent by the device script."""
        return list(self.state.device_sent_sysex)

    def clear_sent_sysex(self) -> None:
        """Clear the captured outgoing SysEx frames."""
        self.state.device_sent_sysex.clear()
