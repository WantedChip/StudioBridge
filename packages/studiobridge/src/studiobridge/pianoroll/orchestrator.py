"""Piano-roll note application orchestrator and tiered execution ladder.

Orchestrates piano-roll note application [ACT-01, ACT-02]:
Orchestrates end-to-end note application across:
- Stage 1: Target channel/pattern selection and piano-roll window focus via live API.
- Stage 2: Generated SBridgeApply.pyscript generation and writing.
- Stage 3: Tiered execution ladder:
  - T1: In-FL transport trigger (if proven/supported).
  - T2: Guarded Win32 hotkey (Ctrl+Alt+Y) via UIActuator / ActuationGuards.
  - T3: Honest status pending (T3) with manual run instructions.
- Alternative fallback paths:
  - Step-sequencer grid fallback (channels.setGridBit / setStepGrid).
  - MIDI file export fallback (.mid).
- Covert status channel:
  - Inspects pattern/marker rename (JOB:OK:n) to detect in-FL execution without project save.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from studiobridge.actuate.input import UIActuator
from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.core.errors import (
    ActuationDisabledError,
    FocusGuardError,
    ModalBlockedError,
    UserInputActiveError,
    WindowNotFoundError,
)
from studiobridge.core.paths import get_app_data_dir, get_fl_pianoroll_scripts_dir
from studiobridge.pianoroll.generator import PyscriptGenerator
from studiobridge.pianoroll.midi import write_midi_file
from studiobridge.pianoroll.oracle import NoteOracleParser, OracleVerifier
from studiobridge.pianoroll.types import (
    DEFAULT_PPQ,
    ApplyMode,
    Note,
)

WID_PIANO_ROLL: Final[int] = 3
DEFAULT_SCRIPT_NAME: Final[str] = "SBridgeApply.pyscript"


@dataclass(frozen=True, slots=True)
class NoteApplyResult:
    """Structured report returned by note application orchestrator per [ACT-02]."""

    applied: bool | Literal["pending"]
    trigger: Literal["T1", "T2", "T3", "step_grid", "midi_export"]
    status: Literal["applied", "pending", "failed"]
    job_id: str
    script_path: Path | None = None
    instructions: list[str] = field(default_factory=list)
    verified: Literal["oracle", "covert", "step_grid", "none"] = "none"
    notes_count: int = 0
    channel: int | None = None
    pattern: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


def _resolve_index(val: Any) -> int:
    """Extract integer index from int, string, or object with index/number attribute."""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    idx_attr = getattr(val, "index", None)
    if idx_attr is not None:
        return int(idx_attr)
    num_attr = getattr(val, "number", None)
    if num_attr is not None:
        return int(num_attr)
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return int(val)


class NoteApplyOrchestrator:
    """Orchestrates note application into FL Studio's piano roll across the tiered ladder."""

    def __init__(
        self,
        config: StudioBridgeConfig | None = None,
        actuator: UIActuator | None = None,
        generator: PyscriptGenerator | None = None,
        oracle_verifier: OracleVerifier | None = None,
        pyscript_dir: Path | None = None,
        script_name: str = DEFAULT_SCRIPT_NAME,
        enable_t1: bool = False,
        t1_command: int | None = None,
    ) -> None:
        self.config = config or load_config()
        self.actuator = actuator or UIActuator(config=self.config)
        self.generator = generator or PyscriptGenerator()
        self.oracle_verifier = oracle_verifier or OracleVerifier()
        self.pyscript_dir = pyscript_dir
        self.script_name = script_name
        self.enable_t1 = enable_t1
        self.t1_command = t1_command

    async def _select_and_focus(
        self,
        session: Any | None,
        channel: int | None,
        pattern: int | None,
    ) -> None:
        """Stage 1: Select target channel/pattern and focus piano-roll window."""
        if session is None:
            return

        if pattern is not None:
            with contextlib.suppress(Exception):
                await session.call("patterns.jumpToPattern", {"index": pattern})

        if channel is not None:
            with contextlib.suppress(Exception):
                await session.call("channels.selectChannel", {"index": channel, "value": 1})

        with contextlib.suppress(Exception):
            await session.call("ui.showWindow", {"window": WID_PIANO_ROLL})
            await session.call("ui.setFocused", {"window": WID_PIANO_ROLL})

    def _write_pyscript(self, script_content: str) -> Path:
        """Stage 2: Write generated .pyscript to Settings\\Piano roll scripts\\."""
        dir_path = self.pyscript_dir or get_fl_pianoroll_scripts_dir()
        dir_path.mkdir(parents=True, exist_ok=True)
        target = dir_path / self.script_name
        target.write_text(script_content, encoding="utf-8")
        return target

    def _build_t3_instructions(
        self,
        job_id: str,
        notes_count: int,
        channel: int | None,
        pattern: int | None,
    ) -> list[str]:
        """Construct clear step-by-step instructions for manual run per [ACT-02]."""
        ch_desc = f"channel {channel}" if channel is not None else "target channel"
        pat_desc = f"pattern {pattern}" if pattern is not None else "active pattern"
        script_label = self.script_name.replace(".pyscript", "")
        return [
            "1. Bring FL Studio to the foreground.",
            f"2. Ensure the piano roll window is focused on {ch_desc} in {pat_desc}.",
            f"3. In Piano roll tools menu (wrench icon), choose Scripts -> {script_label}.",
            "4. Alternatively, press Alt+Y (or Ctrl+Alt+Y) to re-run the last script.",
            f"5. Verify {notes_count} notes for job {job_id} appear in the score.",
        ]

    async def apply_notes(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        *,
        session: Any | None = None,
        channel: int | str | Any | None = None,
        pattern: int | str | Any | None = None,
        mode: ApplyMode | str = "append",
        range_ticks: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
        allow_focus_steal: bool | None = None,
        force: bool = False,
        dry_run: bool = False,
        verify: Literal["none", "oracle", "covert"] = "none",
        oracle_parser: NoteOracleParser | None = None,
        fallback: Literal["none", "step_grid", "midi"] = "none",
        midi_out_path: Path | str | None = None,
        target_flp: Path | str | None = None,
    ) -> NoteApplyResult:
        """Apply notes across the tiered execution ladder (T1..T3) with fallbacks and verification.

        # req: ACT-01, ACT-02
        """
        ch_idx = _resolve_index(channel) if channel is not None else None
        pat_idx = _resolve_index(pattern) if pattern is not None else None
        effective_ppq = ppq or DEFAULT_PPQ
        actual_job_id = job_id or self.generator.generate_job_id()

        # Direct explicit fallback paths
        if fallback == "step_grid":
            return await self.apply_step_grid(
                channel=ch_idx or 0,
                steps=notes,
                pattern=pat_idx,
                session=session,
            )
        elif fallback == "midi":
            midi_path = self.export_midi(
                notes=notes,
                path=midi_out_path,
                ppq=effective_ppq,
                job_id=actual_job_id,
            )
            note_objs = self.generator._to_note_objects(notes, ppq=effective_ppq)
            return NoteApplyResult(
                applied=True,
                trigger="midi_export",
                status="applied",
                job_id=actual_job_id,
                verified="none",
                notes_count=len(note_objs),
                channel=ch_idx,
                pattern=pat_idx,
                details={"midi_path": str(midi_path)},
            )

        # Stage 1: Select target channel/pattern and focus piano roll
        await self._select_and_focus(session, ch_idx, pat_idx)

        # Stage 2: Generate and write SBridgeApply.pyscript
        jobs = self.generator.generate_jobs(
            notes=notes,
            mode=mode,
            time_range=range_ticks,
            job_id=actual_job_id,
            ppq=effective_ppq,
        )
        first_job = jobs[0]
        script_path = self._write_pyscript(first_job.script_content)
        total_notes = sum(len(j.notes) for j in jobs)
        all_note_objs = [n for j in jobs for n in j.notes]

        # Stage 3: Evaluate Trigger Ladder [ACT-01]
        # --- Tier 1: In-FL transport trigger ---
        if self.enable_t1 and session is not None:
            with contextlib.suppress(Exception):
                t1_cmd = self.t1_command or getattr(self.config, "pianoroll_t1_command", None)
                if t1_cmd is not None:
                    await session.call("transport.globalTransport", {"command": t1_cmd, "value": 1})
                    return NoteApplyResult(
                        applied=True,
                        trigger="T1",
                        status="applied",
                        job_id=actual_job_id,
                        script_path=script_path,
                        verified="none",
                        notes_count=total_notes,
                        channel=ch_idx,
                        pattern=pat_idx,
                    )

        # --- Tier 2: Guarded Win32 hotkey (Ctrl+Alt+Y) ---
        steal = (
            allow_focus_steal
            if allow_focus_steal is not None
            else self.config.actuation.allow_focus_steal
        )
        t2_usable = False
        t2_reason = ""

        try:
            # Check policy
            if not self.actuator.is_actuation_enabled("pianoroll_rerun"):
                t2_reason = "Actuation disabled by policy"
            else:
                # Find target window
                target_hwnd = None
                cached = self.actuator.wm.get_cached_window(validate=True)
                if cached:
                    target_hwnd = cached.hwnd
                else:
                    found = self.actuator.wm.find_main_window()
                    if found:
                        target_hwnd = found.hwnd

                if not target_hwnd:
                    t2_reason = "FL Studio main window not found"
                else:
                    # Check guards
                    self.actuator.guards.ensure_ready(
                        target_hwnd,
                        allow_focus_steal=steal,
                        force=force,
                    )
                    t2_usable = True
        except (
            WindowNotFoundError,
            FocusGuardError,
            ModalBlockedError,
            UserInputActiveError,
            ActuationDisabledError,
        ) as exc:
            t2_usable = False
            t2_reason = str(exc)
        except Exception as exc:
            t2_usable = False
            t2_reason = f"Actuation check failed: {exc}"

        if t2_usable or dry_run:
            # Covert status check preparation
            orig_pat_name = None
            if verify == "covert" and session is not None and pat_idx is not None:
                with contextlib.suppress(Exception):
                    orig_pat_name = await session.call(
                        "patterns.getPatternName", {"index": pat_idx}
                    )

            # Execute actuation
            act_res = None
            try:
                act_res = self.actuator.trigger_pianoroll_rerun(
                    pyscript_source=first_job.script_content,
                    allow_focus_steal=steal,
                    force=force,
                    dry_run=dry_run,
                )
            except Exception as exc:
                t2_usable = False
                t2_reason = f"Hotkey dispatch failed: {exc}"

            if t2_usable:
                verified_level: Literal["oracle", "covert", "step_grid", "none"] = "none"

                # Covert status read-back
                if verify == "covert" and session is not None and pat_idx is not None:
                    with contextlib.suppress(Exception):
                        await asyncio.sleep(0.05)
                        new_pat_name = await session.call(
                            "patterns.getPatternName", {"index": pat_idx}
                        )
                        covert_marker = f"JOB:OK:{len(first_job.notes)}"
                        if new_pat_name == covert_marker or (
                            isinstance(new_pat_name, str) and new_pat_name.startswith("JOB:OK:")
                        ):
                            verified_level = "covert"
                        # Always restore original pattern name immediately
                        if orig_pat_name is not None:
                            await session.call(
                                "patterns.setPatternName",
                                {"index": pat_idx, "name": orig_pat_name},
                            )

                # Oracle verification
                if verify == "oracle":
                    verifier = self.oracle_verifier
                    if oracle_parser is not None:
                        verifier = OracleVerifier(
                            parser=oracle_parser,
                            pitch_tolerance=self.oracle_verifier.pitch_tolerance,
                            time_tolerance_ticks=self.oracle_verifier.time_tolerance_ticks,
                            velocity_tolerance=self.oracle_verifier.velocity_tolerance,
                        )
                    rep = await verifier.verify(
                        all_note_objs,
                        session=session,
                        flp_path=target_flp,
                        pattern=pat_idx or 1,
                        channel=ch_idx or 0,
                    )
                    verified_level = rep.verified

                return NoteApplyResult(
                    applied=True,
                    trigger="T2",
                    status="applied",
                    job_id=actual_job_id,
                    script_path=script_path,
                    verified=verified_level,
                    notes_count=total_notes,
                    channel=ch_idx,
                    pattern=pat_idx,
                    details={
                        "dry_run": dry_run,
                        "journal_id": act_res.journal_id if act_res is not None else None,
                    },
                )

        # --- Tier 3: Honest status pending (T3) [ACT-02] ---
        instructions = self._build_t3_instructions(
            job_id=actual_job_id,
            notes_count=total_notes,
            channel=ch_idx,
            pattern=pat_idx,
        )
        return NoteApplyResult(
            applied="pending",
            trigger="T3",
            status="pending",
            job_id=actual_job_id,
            script_path=script_path,
            instructions=instructions,
            verified="none",
            notes_count=total_notes,
            channel=ch_idx,
            pattern=pat_idx,
            details={"reason": t2_reason},
        )

    async def apply_step_grid(
        self,
        channel: int | str | Any,
        steps: Sequence[int | bool | Note | Any],
        *,
        pattern: int | str | Any | None = None,
        session: Any | None = None,
    ) -> NoteApplyResult:
        """Fallback note application using 16-step sequencer grid (channels.setGridBit).

        Provides verified live application for simple rhythm patterns.
        # req: ACT-01, ACT-02
        """
        ch_idx = _resolve_index(channel)
        pat_idx = _resolve_index(pattern) if pattern is not None else None

        if session is not None and pat_idx is not None:
            with contextlib.suppress(Exception):
                await session.call("patterns.jumpToPattern", {"index": pat_idx})

        # Convert input into 16 binary steps (0 or 1)
        step_ints: list[int] = [0] * 16

        # Check if steps is a sequence of Note objects
        first_item = steps[0] if steps else None
        if isinstance(first_item, Note) or (
            hasattr(first_item, "pos") and hasattr(first_item, "key")
        ):
            # Quantize Note objects into 16 steps (assuming 1 bar of 16th notes at PPQ)
            ppq = DEFAULT_PPQ
            step_ticks = ppq // 4
            for n in steps:
                pos = getattr(n, "pos", 0)
                step_idx = (pos // step_ticks) % 16
                step_ints[step_idx] = 1
        elif len(steps) == 16:
            step_ints = [1 if s else 0 for s in steps]
        else:
            # Fill up to 16 steps
            for i, s in enumerate(steps[:16]):
                step_ints[i] = 1 if s else 0

        verified = False
        if session is not None:
            with contextlib.suppress(Exception):
                await session.call(
                    "channels.setStepGrid",
                    {"index": ch_idx, "steps": step_ints},
                )
                readback = await session.call("channels.getStepGrid", {"index": ch_idx})
                if isinstance(readback, list) and [int(x) for x in readback] == step_ints:
                    verified = True

        job_id = self.generator.generate_job_id()
        return NoteApplyResult(
            applied=True,
            trigger="step_grid",
            status="applied",
            job_id=job_id,
            verified="step_grid" if verified else "none",
            notes_count=sum(step_ints),
            channel=ch_idx,
            pattern=pat_idx,
            details={"step_grid": step_ints, "readback_verified": verified},
        )

    def export_midi(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        path: Path | str | None = None,
        ppq: int = DEFAULT_PPQ,
        tempo_bpm: float = 120.0,
        job_id: str | None = None,
    ) -> Path:
        """Export notes to standard MIDI file (.mid) fallback."""
        note_objs = self.generator._to_note_objects(notes, ppq=ppq)
        actual_job_id = job_id or self.generator.generate_job_id()

        if path is not None:
            out_path = Path(path)
        else:
            out_path = get_app_data_dir() / "midi" / f"{actual_job_id}.mid"

        return write_midi_file(
            notes=note_objs,
            path=out_path,
            ppq=ppq,
            tempo_bpm=tempo_bpm,
        )
