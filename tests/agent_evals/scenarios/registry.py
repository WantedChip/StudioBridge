"""Modular evaluation scenario registry and execution runner.

Manages registration and execution of scripted end-to-end agent workflows
against DeviceEmulator and StudioBridge MCP tool suites.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.agent_evals.harness import ScriptedAgentHarness
from tests.agent_evals.reporter import EvaluationReport, ScenarioResult, TranscriptRecorder

logger = logging.getLogger(__name__)


@dataclass
class ScenarioDefinition:
    """Specification of a scripted multi-turn evaluation scenario."""

    id: str
    name: str
    description: str
    requirement_id: str
    run_fn: Callable[[ScriptedAgentHarness, Path], Any]


class ScenarioRegistry:
    """Central registry for all scripted agent evaluation scenarios."""

    _scenarios: dict[str, ScenarioDefinition] = {}

    @classmethod
    def register(cls, scenario: ScenarioDefinition) -> None:
        """Register a scenario definition."""
        cls._scenarios[scenario.id] = scenario

    @classmethod
    def get(cls, scenario_id: str) -> ScenarioDefinition:
        """Retrieve scenario definition by identifier."""
        if scenario_id not in cls._scenarios:
            raise KeyError(f"Scenario '{scenario_id}' not found in registry.")
        return cls._scenarios[scenario_id]

    @classmethod
    def list_all(cls) -> list[ScenarioDefinition]:
        """Return all registered scenarios in insertion order."""
        return list(cls._scenarios.values())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered scenarios (useful for testing)."""
        cls._scenarios.clear()

    @classmethod
    def run_scenario(
        cls,
        scenario: ScenarioDefinition | str,
        harness: ScriptedAgentHarness,
        work_dir: Path,
        recorder: TranscriptRecorder | None = None,
    ) -> ScenarioResult:
        """Execute a single evaluation scenario and compile structured result."""
        defn = cls.get(scenario) if isinstance(scenario, str) else scenario
        rec = recorder or harness.recorder or TranscriptRecorder()
        harness.recorder = rec
        rec.reset()

        passed = True
        error_msg: str | None = None

        try:
            defn.run_fn(harness, work_dir)
        except Exception as exc:
            passed = False
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception("Scenario '%s' failed: %s", defn.id, exc)

        return rec.build_result(
            scenario_id=defn.id,
            name=defn.name,
            description=defn.description,
            requirement_id=defn.requirement_id,
            passed=passed,
            error_message=error_msg,
        )

    @classmethod
    def run_all(
        cls,
        harness_factory: Callable[[TranscriptRecorder], ScriptedAgentHarness],
        work_dir: Path,
        session_id: str = "eval-session-full",
    ) -> EvaluationReport:
        """Execute all registered evaluation scenarios and generate evaluation report."""
        report = EvaluationReport(session_id=session_id)
        recorder = TranscriptRecorder()

        for scenario in cls.list_all():
            harness = harness_factory(recorder)
            result = cls.run_scenario(
                scenario=scenario,
                harness=harness,
                work_dir=work_dir,
                recorder=recorder,
            )
            report.add_scenario(result)

        return report


ScenarioFn = Callable[[ScriptedAgentHarness, Path], Any]


def register_scenario(
    id: str,
    name: str,
    description: str,
    requirement_id: str,
) -> Callable[[ScenarioFn], ScenarioFn]:
    """Decorator to declare and register an evaluation scenario."""

    def decorator(fn: ScenarioFn) -> ScenarioFn:
        scenario = ScenarioDefinition(
            id=id,
            name=name,
            description=description,
            requirement_id=requirement_id,
            run_fn=fn,
        )
        ScenarioRegistry.register(scenario)
        return fn

    return decorator


__all__ = [
    "ScenarioDefinition",
    "ScenarioRegistry",
    "register_scenario",
]
