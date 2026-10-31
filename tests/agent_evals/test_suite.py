"""Automated evaluation test runner executing all scripted agent production workflows.

Executes all modular evaluation scenarios against DeviceEmulator and MCP tool suites,
scoring safety sequence adherence, confirmation tokens, error recovery, and generating
structured JSON and Markdown evaluation reports.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.sdk.client import Studio
from tests.agent_evals.harness import ScriptedAgentHarness
from tests.agent_evals.reporter import TranscriptRecorder
from tests.agent_evals.scenarios.registry import ScenarioDefinition, ScenarioRegistry

# Reference requirement IDs in test comments
# req: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
# req: EVAL-07, EVAL-08, EVAL-09, EVAL-10, EVAL-11, EVAL-12
# req: EVAL-13, EVAL-14, EVAL-15, EVAL-16, EVAL-17, EVAL-18
# req: EVAL-19, EVAL-20, EVAL-21, EVAL-REP, EVAL-RUN


@pytest.mark.parametrize(
    "scenario",
    ScenarioRegistry.list_all(),
    ids=lambda s: s.id,
)
def test_agent_scenario_execution(
    scenario: ScenarioDefinition,
    eval_studio_readonly: Studio,
    tmp_path: Path,
) -> None:
    """Execute each modular agent evaluation scenario individually (# req: EVAL-RUN)."""
    recorder = TranscriptRecorder()
    harness = ScriptedAgentHarness(
        studio=eval_studio_readonly,
        recorder=recorder,
        pyscript_dir=tmp_path / "pyscripts",
    )

    result = ScenarioRegistry.run_scenario(
        scenario=scenario,
        harness=harness,
        work_dir=tmp_path,
        recorder=recorder,
    )

    assert result.passed is True, (
        f"Scenario '{scenario.id}' ({scenario.name}) failed: {result.error_message}"
    )
    assert result.score >= 90.0, f"Scenario '{scenario.id}' score below threshold: {result.score}%"
    assert len(result.transcript) > 0, (
        f"Scenario '{scenario.id}' produced an empty execution transcript."
    )


def test_full_evaluation_suite_report(
    eval_studio_readonly: Studio,
    tmp_path: Path,
) -> None:
    """Execute complete evaluation suite, verify 100% pass rate, and generate report artifacts.

    Ref: # req: EVAL-REP
    """
    pyscripts_dir = tmp_path / "pyscripts"
    pyscripts_dir.mkdir(parents=True, exist_ok=True)

    def harness_factory(recorder: TranscriptRecorder) -> ScriptedAgentHarness:
        # Reset studio safety mode to read_only before each scenario run
        eval_studio_readonly.safety.mode = "read_only"
        return ScriptedAgentHarness(
            studio=eval_studio_readonly,
            recorder=recorder,
            pyscript_dir=pyscripts_dir,
        )

    report = ScenarioRegistry.run_all(
        harness_factory=harness_factory,
        work_dir=tmp_path,
        session_id="agent-eval-ci-suite",
    )

    # Verify suite metrics
    assert report.total_scenarios >= 20, (
        f"Expected at least 20 evaluation scenarios, found {report.total_scenarios}."
    )
    assert report.failed_count == 0, (
        f"Evaluation suite had {report.failed_count} failing scenarios: "
        f"{[s.scenario_id for s in report.scenarios if not s.passed]}"
    )
    assert report.passed_count == report.total_scenarios
    assert report.pass_rate == 100.0
    assert report.overall_score >= 95.0

    # Save artifacts into tmp_path and build/reports/
    json_path = tmp_path / "agent_eval_report.json"
    md_path = tmp_path / "agent_eval_report.md"
    report.save(json_path=json_path, md_path=md_path)

    # Also archive into build/reports if directory exists
    build_reports = Path("build/reports")
    try:
        build_reports.mkdir(parents=True, exist_ok=True)
        report.save(
            json_path=build_reports / "agent_eval_report.json",
            md_path=build_reports / "agent_eval_report.md",
        )
    except OSError:
        pass

    # Verify generated report artifacts
    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["total_scenarios"] == report.total_scenarios
    assert data["summary"]["passed"] == report.total_scenarios
    assert data["summary"]["pass_rate_pct"] == 100.0

    md_content = md_path.read_text(encoding="utf-8")
    assert "# StudioBridge Agent Evaluation Report" in md_content
    assert "100.0%" in md_content
