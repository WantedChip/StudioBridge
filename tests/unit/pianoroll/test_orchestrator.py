"""Unit tests for piano-roll note application orchestrator and tiered execution ladder.

Per spec 06_l0d_pianoroll_actuation_render.md §4, §6, §7 and [ACT-01], [ACT-02].
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio

from studiobridge.actuate.guards import ActuationGuards
from studiobridge.actuate.input import UIActuator
from studiobridge.actuate.win32 import FLWindowInfo, WindowManager
from studiobridge.core.config import StudioBridgeConfig
from studiobridge.pianoroll.midi import read_midi_notes
from studiobridge.pianoroll.oracle import MockNoteOracleParser, OracleVerifier
from studiobridge.pianoroll.orchestrator import NoteApplyOrchestrator, NoteApplyResult
from studiobridge.pianoroll.types import Note


class MockSession:
    """Mock session tracking calls and simulating return values."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.step_grid: list[int] = [0] * 16
        self.pattern_names: dict[int, str] = {1: "My Pattern", 2: "Lead", 3: "Drums"}
        self.covert_response: str | None = None

    async def call(self, op: str, args: dict[str, Any], **kwargs: Any) -> Any:
        self.calls.append((op, args))
        if op == "channels.getStepGrid":
            return list(self.step_grid)
        elif op == "channels.setStepGrid":
            self.step_grid = list(args.get("steps", [0] * 16))
            return None
        elif op == "patterns.getPatternName":
            idx = args.get("index", 1)
            if self.covert_response is not None:
                # First call before actuation returns original name
                # Second call after actuation returns covert response
                if not hasattr(self, "_covert_called"):
                    self._covert_called = True
                    return self.pattern_names.get(idx, f"Pattern {idx}")
                return self.covert_response
            return self.pattern_names.get(idx, f"Pattern {idx}")
        elif op == "patterns.setPatternName":
            idx = args.get("index", 1)
            name = args.get("name", "")
            self.pattern_names[idx] = name
            return None
        elif op == "project.saveNewVersion":
            return True
        return None


class MockWindowManager(WindowManager):
    """Mock window manager simulating foreground/background and window existence."""

    def __init__(self, hwnd: int = 12345, is_fg: bool = True) -> None:
        super().__init__(user32=None, kernel32=None)
        self._mock_hwnd = hwnd
        self._is_fg = is_fg

    def is_window_valid(self, hwnd: int) -> bool:
        return hwnd == self._mock_hwnd

    def find_main_window(self, fl_install_dir: Path | str | None = None) -> FLWindowInfo | None:
        if self._mock_hwnd:
            return FLWindowInfo(
                hwnd=self._mock_hwnd,
                title="FL Studio 21 - Test Project",
                pid=9999,
                image_path=r"C:\Program Files\Image-Line\FL Studio 21\FL64.exe",
                is_foreground=self._is_fg,
            )
        return None

    def get_cached_window(self, validate: bool = True) -> FLWindowInfo | None:
        return self.find_main_window()

    def is_fl_foreground(self, hwnd: int | None = None) -> bool:
        return self._is_fg

    def get_window_title(self, hwnd: int) -> str:
        return "FL Studio 21 - Test Project"


class MockGuards(ActuationGuards):
    """Mock actuation guards controlling readiness results."""

    def __init__(self, wm: WindowManager, ready: bool = True, failure_reason: str = "") -> None:
        super().__init__(window_manager=wm, user32=None, kernel32=None)
        self.ready = ready
        self.failure_reason = failure_reason

    def ensure_ready(
        self,
        target_hwnd: int,
        *,
        allow_focus_steal: bool = False,
        force: bool = False,
        threshold_ms: float | None = None,
    ) -> None:
        if not self.ready:
            from studiobridge.core.errors import FocusGuardError

            raise FocusGuardError(
                self.failure_reason or "FL Studio is not foreground window",
                code="E_ACT_FOCUS",
            )


def _make_ready_actuator(is_fg: bool = True, ready: bool = True, reason: str = "") -> UIActuator:
    wm = MockWindowManager(hwnd=12345, is_fg=is_fg)
    guards = MockGuards(wm=wm, ready=ready, failure_reason=reason)
    return UIActuator(window_manager=wm, guards=guards)


def test_stage1_channel_pattern_focus(tmp_path: Path) -> None:
    """Verify Stage 1 selects channel/pattern and focuses piano roll (# req: ACT-01)."""
    session = MockSession()
    actuator = _make_ready_actuator(is_fg=True, ready=True)
    orchestrator = NoteApplyOrchestrator(actuator=actuator, pyscript_dir=tmp_path)
    notes = [Note(pos=0, length=96, key=60)]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            session=session,
            channel=2,
            pattern=3,
            dry_run=True,
        )

    res = anyio.run(run)
    assert res.applied is True
    ops = [call[0] for call in session.calls]
    assert "patterns.jumpToPattern" in ops
    assert "channels.selectChannel" in ops
    assert "ui.showWindow" in ops
    assert "ui.setFocused" in ops

    # Check argument values
    jump_args = next(args for op, args in session.calls if op == "patterns.jumpToPattern")
    assert jump_args == {"index": 3}
    chan_args = next(args for op, args in session.calls if op == "channels.selectChannel")
    assert chan_args == {"index": 2, "value": 1}
    win_args = next(args for op, args in session.calls if op == "ui.showWindow")
    assert win_args == {"window": 3}


def test_stage2_pyscript_written(tmp_path: Path) -> None:
    """Verify Stage 2 writes SBridgeApply.pyscript with baked notes (# req: ACT-01)."""
    actuator = _make_ready_actuator(is_fg=True, ready=True)
    orchestrator = NoteApplyOrchestrator(actuator=actuator, pyscript_dir=tmp_path)
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=48, key=64),
    ]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(notes, dry_run=True)

    res = anyio.run(run)
    assert res.applied is True
    script_file = tmp_path / "SBridgeApply.pyscript"
    assert script_file.exists()
    content = script_file.read_text(encoding="utf-8")
    assert "import flpianoroll as fpr" in content
    assert f'JOB = "{res.job_id}"' in content
    assert "(0, 96, 60," in content
    assert "(96, 48, 64," in content


def test_ladder_t3_honest_status_when_unfocused(tmp_path: Path) -> None:
    """Verify unfocused FL returns pending (T3) without crashing (# req: ACT-01, ACT-02)."""
    # Configure mock actuator with unfocused FL and guards failing
    wm = MockWindowManager(hwnd=12345, is_fg=False)
    guards = MockGuards(wm=wm, ready=False, failure_reason="FL Studio is not foreground window")
    cfg = StudioBridgeConfig()
    cfg.actuation.allow_focus_steal = False

    actuator = UIActuator(config=cfg, window_manager=wm, guards=guards)
    orchestrator = NoteApplyOrchestrator(
        config=cfg,
        actuator=actuator,
        pyscript_dir=tmp_path,
    )

    notes = [Note(pos=0, length=96, key=60)]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            channel=1,
            pattern=2,
            dry_run=False,
        )

    res = anyio.run(run)

    # Must return honest status pending (T3) without throwing exception
    assert res.applied == "pending"
    assert res.trigger == "T3"
    assert res.status == "pending"
    assert res.verified == "none"
    assert res.notes_count == 1
    assert res.channel == 1
    assert res.pattern == 2
    assert len(res.instructions) >= 4
    assert any("Alt+Y" in inst or "Ctrl+Alt+Y" in inst for inst in res.instructions)
    assert "FL Studio is not foreground window" in res.details.get("reason", "")


def test_ladder_t2_guarded_actuation_when_ready(tmp_path: Path) -> None:
    """Verify guarded T2 actuation triggers hotkey when ready (# req: ACT-01, ACT-02)."""
    actuator = _make_ready_actuator(is_fg=True, ready=True)
    orchestrator = NoteApplyOrchestrator(
        actuator=actuator,
        pyscript_dir=tmp_path,
    )
    notes = [Note(pos=0, length=96, key=60)]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(notes, dry_run=True)

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "T2"
    assert res.status == "applied"
    assert res.notes_count == 1
    assert res.details.get("dry_run") is True


def test_ladder_t1_transport_trigger(tmp_path: Path) -> None:
    """Verify T1 triggers in-FL transport command when proven and enabled (# req: ACT-01)."""
    session = MockSession()
    orchestrator = NoteApplyOrchestrator(
        pyscript_dir=tmp_path,
        enable_t1=True,
        t1_command=99,
    )
    notes = [Note(pos=0, length=96, key=60)]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(notes, session=session)

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "T1"
    assert res.status == "applied"
    assert any(call[0] == "transport.globalTransport" for call in session.calls)


def test_fallback_step_grid_explicit(tmp_path: Path) -> None:
    """Verify step-grid fallback applies 16 steps with readback (# req: ACT-01, ACT-02)."""
    session = MockSession()
    orchestrator = NoteApplyOrchestrator(pyscript_dir=tmp_path)
    steps = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_step_grid(channel=0, steps=steps, session=session)

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "step_grid"
    assert res.status == "applied"
    assert res.verified == "step_grid"
    assert res.notes_count == 4
    assert session.step_grid == steps


def test_fallback_step_grid_from_notes(tmp_path: Path) -> None:
    """Verify step grid fallback quantizes Note objects into 16 steps (# req: ACT-01, ACT-02)."""
    session = MockSession()
    orchestrator = NoteApplyOrchestrator(pyscript_dir=tmp_path)
    # Notes at tick 0 (step 0), tick 96 (step 4), tick 192 (step 8)
    notes = [
        Note(pos=0, length=24, key=36),
        Note(pos=96, length=24, key=38),
        Note(pos=192, length=24, key=42),
    ]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            fallback="step_grid",
            channel=1,
            session=session,
        )

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "step_grid"
    assert res.verified == "step_grid"
    assert res.notes_count == 3
    assert session.step_grid[0] == 1
    assert session.step_grid[4] == 1
    assert session.step_grid[8] == 1
    assert session.step_grid[1] == 0


def test_fallback_midi_export(tmp_path: Path) -> None:
    """Verify MIDI file export fallback creates a valid SMF Format 0 file (# req: ACT-01)."""
    orchestrator = NoteApplyOrchestrator(pyscript_dir=tmp_path)
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=48, key=64),
    ]
    out_mid = tmp_path / "exported.mid"

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            fallback="midi",
            midi_out_path=out_mid,
        )

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "midi_export"
    assert res.status == "applied"
    assert out_mid.exists()

    # Read back and verify notes
    ppq, read_back = read_midi_notes(out_mid)
    assert ppq == 96
    assert len(read_back) == 2
    assert read_back[0].key == 60
    assert read_back[1].key == 64


def test_covert_status_channel_detection_and_restore(tmp_path: Path) -> None:
    """Verify covert channel detects JOB:OK:n and restores pattern name (# req: ACT-02)."""
    session = MockSession()
    # Configure simulated covert response: after actuation, pattern name becomes JOB:OK:2
    session.covert_response = "JOB:OK:2"

    actuator = _make_ready_actuator(is_fg=True, ready=True)
    orchestrator = NoteApplyOrchestrator(
        actuator=actuator,
        pyscript_dir=tmp_path,
    )
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            session=session,
            pattern=1,
            verify="covert",
            dry_run=True,
        )

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "T2"
    assert res.verified == "covert"

    # Verify original name was restored
    assert session.pattern_names[1] == "My Pattern"
    set_name_calls = [args for op, args in session.calls if op == "patterns.setPatternName"]
    assert len(set_name_calls) >= 1
    assert set_name_calls[-1]["name"] == "My Pattern"


def test_oracle_verification_on_t2_apply(tmp_path: Path) -> None:
    """Verify oracle verification integrates into apply_notes (# req: ACT-02)."""
    session = MockSession()
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]
    parser = MockNoteOracleParser(canned_notes=notes)
    verifier = OracleVerifier(parser=parser)

    actuator = _make_ready_actuator(is_fg=True, ready=True)
    orchestrator = NoteApplyOrchestrator(
        actuator=actuator,
        oracle_verifier=verifier,
        pyscript_dir=tmp_path,
    )

    async def run() -> NoteApplyResult:
        return await orchestrator.apply_notes(
            notes,
            session=session,
            verify="oracle",
            dry_run=True,
        )

    res = anyio.run(run)
    assert res.applied is True
    assert res.trigger == "T2"
    assert res.verified == "oracle"
    assert any(call[0] == "project.saveNewVersion" for call in session.calls)
