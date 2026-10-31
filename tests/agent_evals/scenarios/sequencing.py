"""Sequencing evaluation scenarios.

Exercises note injection, chord progressions, and drum programming.

Covers:
- Scenario 7: Piano roll note injection & verification (# req: EVAL-07)
- Scenario 8: Multi-bar chord progression sequencing (# req: EVAL-08)
- Scenario 9: Drum pattern velocity programming (# req: EVAL-09)
"""

from __future__ import annotations

from pathlib import Path

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-07-note-injection",
    name="Piano roll note injection & verification",
    description=(
        "Inspect channel, inject structured MIDI notes with timing and pitch, and verify receipt."
    ),
    requirement_id="EVAL-07",
)
def run_scenario_note_injection(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 7: Piano roll note injection & verification (# req: EVAL-07)."""
    # Turn 1: Inspect target channel
    res_chan = harness.step(
        "Inspect target channel 0 for note injection",
        [ToolCall(tool="channel_get", arguments={"channel": 0})],
    )
    assert not res_chan[0].is_error

    # Turn 2: Apply bassline notes
    notes_payload = [
        {"pos": 0, "len": 96, "key": 36, "velocity": 0.85},
        {"pos": 96, "len": 96, "key": 38, "velocity": 0.80},
        {"pos": 192, "len": 96, "key": 41, "velocity": 0.85},
        {"pos": 288, "len": 96, "key": 43, "velocity": 0.90},
    ]
    res_apply = harness.step(
        "Inject 4 bassline notes into pattern 1 channel 0",
        [
            ToolCall(
                tool="notes_apply",
                arguments={
                    "channel": 0,
                    "pattern": 1,
                    "notes": notes_payload,
                    "mode": "append",
                    "dry_run": True,
                },
            )
        ],
    )
    sc = res_apply[0].structured_content
    assert res_apply[0].is_error is False
    assert sc["notes_count"] == 4
    assert sc["channel"] == 0
    assert sc["pattern"] == 1
    assert sc["status"] in ("applied", "pending")
    assert "job_id" in sc

    # Turn 3: Inspect project snapshot to verify session integrity
    res_snap = harness.step(
        "Verify session snapshot after note injection",
        [ToolCall(tool="project_snapshot")],
    )
    assert not res_snap[0].is_error


@register_scenario(
    id="eval-08-chord-progression",
    name="Multi-bar chord progression sequencing",
    description=(
        "Sequence a 4-bar harmonic chord progression with multiple voices and duration offsets."
    ),
    requirement_id="EVAL-08",
)
def run_scenario_chord_progression(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 8: Multi-bar chord progression sequencing (# req: EVAL-08)."""
    # Turn 1: Inspect channel 1 (synth / keys)
    res_chan = harness.step(
        "Inspect channel 1 for chord progression",
        [ToolCall(tool="channel_get", arguments={"channel": 1})],
    )
    assert not res_chan[0].is_error

    # Turn 2: Construct 4-bar progression (C maj -> G maj -> A min -> F maj)
    # PPQ = 96, 1 bar = 4 * 96 = 384 ticks
    bar_ticks = 384
    progression: list[dict[str, int | float]] = [
        # Bar 1: C major (C4=60, E4=64, G4=67)
        {"pos": 0 * bar_ticks, "len": bar_ticks, "key": 60, "velocity": 0.75},
        {"pos": 0 * bar_ticks, "len": bar_ticks, "key": 64, "velocity": 0.70},
        {"pos": 0 * bar_ticks, "len": bar_ticks, "key": 67, "velocity": 0.72},
        # Bar 2: G major (G3=55, B3=59, D4=62)
        {"pos": 1 * bar_ticks, "len": bar_ticks, "key": 55, "velocity": 0.75},
        {"pos": 1 * bar_ticks, "len": bar_ticks, "key": 59, "velocity": 0.70},
        {"pos": 1 * bar_ticks, "len": bar_ticks, "key": 62, "velocity": 0.72},
        # Bar 3: A minor (A3=57, C4=60, E4=64)
        {"pos": 2 * bar_ticks, "len": bar_ticks, "key": 57, "velocity": 0.75},
        {"pos": 2 * bar_ticks, "len": bar_ticks, "key": 60, "velocity": 0.70},
        {"pos": 2 * bar_ticks, "len": bar_ticks, "key": 64, "velocity": 0.72},
        # Bar 4: F major (F3=53, A3=57, C4=60)
        {"pos": 3 * bar_ticks, "len": bar_ticks, "key": 53, "velocity": 0.75},
        {"pos": 3 * bar_ticks, "len": bar_ticks, "key": 57, "velocity": 0.70},
        {"pos": 3 * bar_ticks, "len": bar_ticks, "key": 60, "velocity": 0.72},
    ]

    res_apply = harness.step(
        "Apply 4-bar triad progression into pattern 2 channel 1",
        [
            ToolCall(
                tool="notes_apply",
                arguments={
                    "channel": 1,
                    "pattern": 2,
                    "notes": progression,
                    "mode": "replace_all",
                    "dry_run": True,
                },
            )
        ],
    )
    sc = res_apply[0].structured_content
    assert res_apply[0].is_error is False
    assert sc["notes_count"] == 12
    assert sc["channel"] == 1
    assert sc["pattern"] == 2
    assert sc["status"] in ("applied", "pending")


@register_scenario(
    id="eval-09-drum-programming",
    name="Drum pattern velocity programming",
    description=(
        "Program 16-step rhythm grid and sequence velocity-differentiated hi-hat subdivisions."
    ),
    requirement_id="EVAL-09",
)
def run_scenario_drum_programming(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 9: Drum pattern velocity programming (# req: EVAL-09)."""
    # Turn 1: Inspect drum channel 0
    harness.step("Inspect drum channel 0", [ToolCall(tool="channel_get", arguments={"channel": 0})])

    # Turn 2: Switch to write mode
    res_chal = harness.step(
        "Switch to write mode for sequencer editing",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    if token:
        harness.step(
            "Confirm write mode",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )

    # Turn 3: Create checkpoint
    harness.step(
        "Create checkpoint before programming drum pattern",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_drum_grid"})],
    )

    # Turn 4: Program 16-step kick rhythm (steps 0, 4, 8, 12 active)
    kick_steps = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    res_steps = harness.step(
        "Program four-on-the-floor kick pattern on channel 0",
        [ToolCall(tool="steps_set", arguments={"channel": 0, "steps": kick_steps})],
    )
    sc_steps = res_steps[0].structured_content
    assert sc_steps.get("verified") is True

    # Turn 5: Sequence 16th-note closed hi-hats with velocity accents
    # Accented downbeats at 0.90 velocity, unaccented ghost notes at 0.50
    hihat_notes: list[dict[str, int | float]] = []
    step_duration_ticks = 24  # 96 / 4 = 24 ticks per 16th note
    for step_idx in range(16):
        is_accent = step_idx % 4 == 0
        hihat_notes.append(
            {
                "pos": step_idx * step_duration_ticks,
                "len": 12,
                "key": 42,  # Closed Hi-Hat GM note
                "velocity": 0.90 if is_accent else 0.50,
            }
        )

    res_hh = harness.step(
        "Inject 16 velocity-accented hi-hat notes",
        [
            ToolCall(
                tool="notes_apply",
                arguments={
                    "channel": 0,
                    "pattern": 1,
                    "notes": hihat_notes,
                    "mode": "append",
                    "dry_run": True,
                },
            )
        ],
    )
    sc_hh = res_hh[0].structured_content
    assert not res_hh[0].is_error
    assert sc_hh["notes_count"] == 16
    assert sc_hh["status"] in ("applied", "pending")
