"""Unit tests for KeystrokeDispatcher, UIActuator, and session journal [ACT-01, ACT-10, ACT-11]."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from studiobridge.actuate.guards import ActuationGuards
from studiobridge.actuate.input import (
    KEYEVENTF_KEYUP,
    KEYEVENTF_SCANCODE,
    VK_CONTROL,
    VK_MENU,
    VK_Y,
    ActuationResult,
    KeystrokeDispatcher,
    UIActuator,
    dispatch_pianoroll_rerun,
)
from studiobridge.actuate.win32 import WindowManager
from studiobridge.core.config import ActuationConfig, StudioBridgeConfig
from studiobridge.core.errors import (
    ActuationDisabledError,
    FocusGuardError,
)
from studiobridge.sdk.journal import MutationJournal
from tests.unit.actuate.test_guards import MockGuardsKernel32, MockGuardsUser32


class MockInputUser32(MockGuardsUser32):
    """Mock user32 DLL tracking injected SendInput events and keyboard layout."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_events: list[dict[str, Any]] = []
        self.scancode_map: dict[int, int] = {
            VK_CONTROL: 0x1D,
            VK_MENU: 0x38,
            VK_Y: 0x15,
        }

    def MapVirtualKeyExW(self, vk: int, u_map_type: int, hkl: Any) -> int:
        return self.scancode_map.get(vk, 0)

    def GetKeyboardLayout(self, tid: int) -> int:
        return 0x04090409  # US English layout

    def SendInput(self, n_inputs: int, inputs_ptr: Any, cb_size: int) -> int:
        inp = None
        if inputs_ptr is not None:
            if hasattr(inputs_ptr, "_obj"):
                inp = inputs_ptr._obj
            elif hasattr(inputs_ptr, "contents"):
                inp = inputs_ptr.contents
        if inp is not None:
            self.sent_events.append(
                {
                    "type": inp.type,
                    "scan": inp.u.ki.wScan,
                    "flags": inp.u.ki.dwFlags,
                }
            )
        return n_inputs


@pytest.fixture
def input_fixture(
    tmp_path: Path,
) -> tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]]:
    u32 = MockInputUser32()
    k32 = MockGuardsKernel32()

    # Register FL Studio process and window
    k32.add_process(1234, r"C:\Program Files\Image-Line\FL Studio 2024\FL64.exe")
    u32.add_window(101, "FL Studio 2024 - Project.flp", 1234, is_visible=True, is_enabled=True)
    u32.foreground_hwnd = 101  # FL Studio active by default

    # Register human idle state (10s idle)
    k32.current_tick = 110000
    u32.last_input_time_tick = 100000

    recorded_sleeps: list[float] = []

    def mock_sleep(sec: float) -> None:
        recorded_sleeps.append(sec)

    cfg = StudioBridgeConfig(
        actuation=ActuationConfig(
            enabled=False,  # default false for generic actuation [ACT-11]
            piano_roll_enabled=True,  # default true for piano-roll [ACT-11]
            allow_focus_steal=False,
            user_idle_threshold_ms=1000.0,
            key_delay_ms=15.0,  # 15ms modifier gap
        )
    )

    journal = MutationJournal(session_id="test_actuate", journal_dir=tmp_path / "journal")
    wm = WindowManager(user32=u32, kernel32=k32, config=cfg)
    guards = ActuationGuards(wm, user32=u32, kernel32=k32, user_idle_threshold_ms=1000.0)
    dispatcher = KeystrokeDispatcher(
        wm,
        guards=guards,
        user32=u32,
        key_delay_ms=15.0,
        sleeper=mock_sleep,
        journal=journal,
        config=cfg,
    )

    actuator = UIActuator(
        config=cfg,
        window_manager=wm,
        guards=guards,
        dispatcher=dispatcher,
        journal=journal,
        sleeper=mock_sleep,
    )

    return u32, k32, actuator, recorded_sleeps


def test_keystroke_dispatcher_scancode_resolution(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify hardware scancodes are resolved via MapVirtualKeyExW with fallback [ACT-10].

    # req: ACT-10
    """
    u32, _k32, actuator, _sleeps = input_fixture

    # Standard mappings
    assert actuator.dispatcher.resolve_scancode(VK_CONTROL, 101) == 0x1D
    assert actuator.dispatcher.resolve_scancode(VK_MENU, 101) == 0x38
    assert actuator.dispatcher.resolve_scancode(VK_Y, 101) == 0x15

    # Fallback when MapVirtualKey returns 0
    u32.scancode_map.clear()
    assert actuator.dispatcher.resolve_scancode(VK_CONTROL, 101) == 0x1D
    assert actuator.dispatcher.resolve_scancode(VK_MENU, 101) == 0x38
    assert actuator.dispatcher.resolve_scancode(VK_Y, 101) == 0x15


def test_keystroke_dispatcher_sequence_and_delays(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify Ctrl+Alt+Y sends exact sequence with 10-20ms modifier gaps [ACT-10].

    # req: ACT-10
    """
    u32, _k32, actuator, sleeps = input_fixture

    scancodes = actuator.dispatcher.dispatch_ctrl_alt_y(101)
    assert scancodes == {"ctrl": 0x1D, "alt": 0x38, "y": 0x15}

    # Verify 6 distinct keyboard events sent:
    # 1. Ctrl down
    # 2. Alt down
    # 3. Y down
    # 4. Y up
    # 5. Alt up
    # 6. Ctrl up
    events = u32.sent_events
    assert len(events) == 6

    assert events[0]["scan"] == 0x1D
    assert events[0]["flags"] == KEYEVENTF_SCANCODE

    assert events[1]["scan"] == 0x38
    assert events[1]["flags"] == KEYEVENTF_SCANCODE

    assert events[2]["scan"] == 0x15
    assert events[2]["flags"] == KEYEVENTF_SCANCODE

    assert events[3]["scan"] == 0x15
    assert events[3]["flags"] == (KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)

    assert events[4]["scan"] == 0x38
    assert events[4]["flags"] == (KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)

    assert events[5]["scan"] == 0x1D
    assert events[5]["flags"] == (KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)

    # Verify 5 delay gaps of 15ms (0.015s)
    assert len(sleeps) == 5
    assert all(pytest.approx(s, rel=1e-3) == 0.015 for s in sleeps)


def test_actuation_defaults_piano_roll_enabled_generic_disabled(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify actuation policy defaults per [ACT-11]: true for piano-roll, false for general.

    # req: ACT-11
    """
    _u32, _k32, actuator, _sleeps = input_fixture

    # Default policy checks
    assert actuator.is_actuation_enabled("pianoroll_rerun") is True
    assert actuator.is_actuation_enabled("ctrl_alt_y") is True
    assert actuator.is_actuation_enabled("notes_apply") is True
    assert actuator.is_actuation_enabled("save") is False
    assert actuator.is_actuation_enabled("generic") is False

    # Attempting a generic action raises ActuationDisabledError
    with pytest.raises(ActuationDisabledError) as exc_info:
        actuator.trigger_pianoroll_rerun(action_type="save")
    assert "disabled by policy" in str(exc_info.value)
    assert "[ACT-11]" in str(exc_info.value)

    # When general actuation is explicitly enabled, it passes
    actuator.config.actuation.enabled = True
    assert actuator.is_actuation_enabled("save") is True


def test_actuation_auditing_into_mutation_journal(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify actuation events record to MutationJournal with title and payload hash [ACT-11].

    # req: ACT-11
    """
    _u32, _k32, actuator, _sleeps = input_fixture

    fake_pyscript = "# name=SBridge Apply\nimport flpianoroll as fpr\n"
    expected_hash = hashlib.sha256(fake_pyscript.encode("utf-8")).hexdigest()

    result = actuator.trigger_pianoroll_rerun(
        pyscript_source=fake_pyscript,
        dry_run=False,
    )

    assert isinstance(result, ActuationResult)
    assert result.success is True
    assert result.hotkey == "Ctrl+Alt+Y"
    assert result.target_hwnd == 101
    assert "FL Studio 2024" in result.window_title
    assert result.payload_hash == expected_hash
    assert result.journal_id is not None
    assert result.details["scancodes"]["ctrl"] == 0x1D

    # Verify journal file was written
    assert actuator.journal is not None
    entries = actuator.journal.list()
    assert len(entries) >= 1
    last_entry = entries[-1]
    assert last_entry.op == "actuate.pianoroll"
    assert last_entry.target == "hwnd:101"
    assert last_entry.details.get("payload_hash") == expected_hash
    assert last_entry.details.get("window_title") == "FL Studio 2024 - Project.flp"
    assert last_entry.details.get("scancodes") == {"ctrl": 0x1D, "alt": 0x38, "y": 0x15}


def test_actuation_dry_run_mode(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify dry_run executes guards and logs to journal without sending keystrokes [ACT-11].

    # req: ACT-11
    """
    u32, _k32, actuator, _sleeps = input_fixture

    result = actuator.trigger_pianoroll_rerun(
        pyscript_source="# dummy script",
        dry_run=True,
    )

    assert result.success is True
    assert result.dry_run is True
    # Zero keystrokes sent
    assert len(u32.sent_events) == 0

    # Journal still records the planned actuation
    assert actuator.journal is not None
    entries = actuator.journal.list()
    assert len(entries) >= 1
    assert entries[-1].details.get("dry_run") is True


def test_actuation_temporary_focus_steal_and_restore(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
) -> None:
    """Verify foreground focus is saved and restored when focus steal is exercised [ACT-10].

    # req: ACT-10
    """
    u32, k32, actuator, _sleeps = input_fixture

    # Register an external active application window (e.g. editor)
    k32.add_process(9999, r"C:\Program Files\Editor\editor.exe")
    u32.add_window(505, "Editor Window", 9999, is_visible=True, is_enabled=True)
    u32.foreground_hwnd = 505  # Editor is foreground, FL is background

    # 1. Without allow_focus_steal: FocusGuardError is raised
    with pytest.raises(FocusGuardError):
        actuator.trigger_pianoroll_rerun(allow_focus_steal=False)

    # 2. With allow_focus_steal=True: focus transfers to FL Studio and restores to Editor
    result = actuator.trigger_pianoroll_rerun(allow_focus_steal=True)
    assert result.success is True
    assert result.focus_stolen is True

    # Focus restored back to 505
    assert actuator.wm.get_foreground_window() == 505


def test_convenience_dispatch_pianoroll_rerun(
    input_fixture: tuple[MockInputUser32, MockGuardsKernel32, UIActuator, list[float]],
    tmp_path: Path,
) -> None:
    """Verify module-level convenience function dispatch_pianoroll_rerun [ACT-01, ACT-11].

    # req: ACT-01, ACT-11
    """
    u32, _k32, actuator, _sleeps = input_fixture
    u32.foreground_hwnd = 101

    res = dispatch_pianoroll_rerun(
        hwnd=101,
        pyscript_source="# quick test",
        dry_run=True,
        journal=actuator.journal,
        config=actuator.config,
        window_manager=actuator.wm,
    )
    assert res.success is True
    assert res.target_hwnd == 101
