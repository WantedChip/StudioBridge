"""Headless render evaluation scenarios.

Exercises preflight checks, job supervision, and audio metrics.

Covers:
- Scenario 13: Headless render preflight checks (# req: EVAL-13)
- Scenario 14: Render job launch & progress polling (# req: EVAL-14)
- Scenario 15: Audio render validation (WAV format, RMS, peak metrics) (# req: EVAL-15)
"""

from __future__ import annotations

from pathlib import Path

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall, create_synthetic_wav
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-13-render-preflight",
    name="Headless render preflight checks",
    description=(
        "Perform preflight diagnostics: project validation, structural inspection, "
        "and doctor diagnostics."
    ),
    requirement_id="EVAL-13",
)
def run_scenario_render_preflight(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 13: Headless render preflight checks (# req: EVAL-13)."""
    flp_path = work_dir / "preflight_project.flp"

    # Turn 1: Inspect studio status
    res_status = harness.step(
        "Verify system bridge connectivity",
        [ToolCall(tool="studio_status")],
    )
    assert not res_status[0].is_error

    # Turn 2: Prepare project for preflight
    res_new = harness.step(
        "Prepare target project file for export preflight",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(flp_path),
                    "title": "Preflight Target",
                    "tempo": 128.0,
                },
            )
        ],
    )
    assert not res_new[0].is_error

    # Turn 3: Validate project invariants
    res_val = harness.step(
        "Validate project binary structure",
        [ToolCall(tool="flp_validate", arguments={"file": str(flp_path)})],
    )
    assert not res_val[0].is_error
    assert res_val[0].structured_content.get("is_valid") is True

    # Turn 4: Inspect project channels and metadata
    res_insp = harness.step(
        "Inspect project tracks and channels",
        [ToolCall(tool="flp_inspect", arguments={"file": str(flp_path)})],
    )
    assert not res_insp[0].is_error
    assert "channels" in res_insp[0].structured_content

    # Turn 5: Run studio doctor health preflight
    res_doc = harness.step(
        "Run system environment diagnostics",
        [ToolCall(tool="studio_doctor", arguments={"skip_live": True})],
    )
    assert "checks" in res_doc[0].structured_content
    assert "summary" in res_doc[0].structured_content


@register_scenario(
    id="eval-14-render-job-launch",
    name="Render job launch & progress polling",
    description=(
        "Launch headless render job in background, poll progress until completion, "
        "and retrieve output artifact."
    ),
    requirement_id="EVAL-14",
)
def run_scenario_render_job_launch(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 14: Render job launch & progress polling (# req: EVAL-14)."""
    source_flp = work_dir / "render_source.flp"

    # Setup source project
    harness.step(
        "Create source project for render launch",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(source_flp),
                    "title": "Render Source",
                    "tempo": 130.0,
                },
            )
        ],
    )

    # Turn 1: Launch background render job
    res_start = harness.step(
        "Launch background headless render export",
        [
            ToolCall(
                tool="render_start",
                arguments={
                    "source": str(source_flp),
                    "formats": ["wav"],
                    "wait": True,
                },
            )
        ],
    )
    assert not res_start[0].is_error
    sc_start = res_start[0].structured_content
    job_id = sc_start["job_id"]
    assert job_id.startswith("rnd-")

    # Turn 2: Poll render job status
    res_status = harness.step(
        f"Poll status for render job {job_id}",
        [ToolCall(tool="render_status", arguments={"job_id": job_id})],
    )
    assert not res_status[0].is_error
    sc_status = res_status[0].structured_content
    assert sc_status["job_id"] == job_id
    assert sc_status["state"] == "done"
    assert len(sc_status["output_files"]) >= 1


@register_scenario(
    id="eval-15-audio-render-validation",
    name="Audio render validation (WAV format, RMS, peak metrics)",
    description=(
        "Run acoustic validation analysis on rendered audio file, "
        "verifying RMS, peak, and duration metrics."
    ),
    requirement_id="EVAL-15",
)
def run_scenario_audio_render_validation(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 15: Audio render validation (WAV format, RMS, peak metrics) (# req: EVAL-15)."""
    wav_path = work_dir / "rendered_output.wav"
    create_synthetic_wav(wav_path, duration_s=1.0, sample_rate=44100)

    # Turn 1: Run acoustic signal quality analysis
    res_analyze = harness.step(
        f"Analyze audio properties and acoustic metrics of '{wav_path.name}'",
        [
            ToolCall(
                tool="render_analyze",
                arguments={
                    "path": str(wav_path),
                    "min_duration_s": 0.5,
                    "max_silence_ratio": 0.98,
                    "allow_clipping": False,
                },
            )
        ],
    )
    assert not res_analyze[0].is_error
    sc_an = res_analyze[0].structured_content
    assert sc_an["is_valid"] is True
    assert sc_an["validation_status"] == "passed"

    metrics = sc_an["metrics"]
    assert metrics["duration_s"] >= 0.5
    assert metrics["peak_dbfs"] <= 0.0
    assert metrics["rms_dbfs"] > -60.0
    assert metrics["channels"] >= 1
