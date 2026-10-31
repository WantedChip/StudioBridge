"""Evaluation scoring, transcript recording, and report generation for agent evaluations.

Provides structured transcript recording, safety sequence tracking, confirmation flow
verification, and evaluation report generation in JSON and Markdown formats.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TranscriptEntry:
    """Single recorded tool call trace within a scenario turn."""

    turn: int
    user_message: str
    tool: str
    arguments: dict[str, Any]
    result_content: list[dict[str, Any]]
    structured_content: dict[str, Any]
    is_error: bool
    duration_ms: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize transcript entry to dictionary."""
        return {
            "turn": self.turn,
            "user_message": self.user_message,
            "tool": self.tool,
            "arguments": self.arguments,
            "result_content": self.result_content,
            "structured_content": self.structured_content,
            "is_error": self.is_error,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class ScenarioMetrics:
    """Aggregated execution metrics for a single evaluation scenario."""

    total_turns: int = 0
    total_tool_calls: int = 0
    successful_calls: int = 0
    error_calls: int = 0
    confirmations_requested: int = 0
    confirmations_completed: int = 0
    checkpoints_created: int = 0
    checkpoints_rolled_back: int = 0
    mutations_count: int = 0
    verified_mutations_count: int = 0
    untrusted_data_encountered: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to dictionary."""
        return asdict(self)


@dataclass
class ScenarioResult:
    """Outcome and execution trace of an agent evaluation scenario."""

    scenario_id: str
    name: str
    description: str
    requirement_id: str
    passed: bool
    duration_ms: float
    metrics: ScenarioMetrics
    transcript: list[TranscriptEntry] = field(default_factory=list)
    error_message: str | None = None
    score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize scenario result to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "requirement_id": self.requirement_id,
            "passed": self.passed,
            "score": round(self.score, 1),
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "metrics": self.metrics.to_dict(),
            "transcript_length": len(self.transcript),
            "transcript": [entry.to_dict() for entry in self.transcript],
        }


class TranscriptRecorder:
    """Records and scores multi-turn tool interaction transcripts."""

    def __init__(self) -> None:
        self.entries: list[TranscriptEntry] = []
        self.current_user_message: str = ""
        self.current_turn: int = 0
        self._scenario_start_time: float = time.time()

    def reset(self) -> None:
        """Reset the recorder for a new scenario run."""
        self.entries.clear()
        self.current_user_message = ""
        self.current_turn = 0
        self._scenario_start_time = time.time()

    def set_user_message(self, message: str, turn: int | None = None) -> None:
        """Update current dialog turn user prompt."""
        self.current_user_message = message
        if turn is not None:
            self.current_turn = turn
        else:
            self.current_turn += 1

    def record_call(
        self,
        tool: str,
        arguments: dict[str, Any],
        result_content: list[dict[str, Any]],
        structured_content: dict[str, Any] | None,
        is_error: bool,
        duration_ms: float,
    ) -> TranscriptEntry:
        """Record an executed tool invocation trace."""
        entry = TranscriptEntry(
            turn=self.current_turn,
            user_message=self.current_user_message,
            tool=tool,
            arguments=arguments,
            result_content=result_content,
            structured_content=structured_content or {},
            is_error=is_error,
            duration_ms=duration_ms,
        )
        self.entries.append(entry)
        return entry

    def compute_metrics(self) -> ScenarioMetrics:
        """Compute aggregated metrics from recorded execution history."""
        metrics = ScenarioMetrics(
            total_turns=len({e.turn for e in self.entries}),
            total_tool_calls=len(self.entries),
            successful_calls=sum(1 for e in self.entries if not e.is_error),
            error_calls=sum(1 for e in self.entries if e.is_error),
        )

        mutating_tools = {
            "mixer_set",
            "channel_set",
            "transport_control",
            "plugin_param_set",
            "pattern_edit",
            "steps_set",
            "playlist_edit",
            "playlist_place_pattern",
            "notes_apply",
            "flp_edit",
        }

        for entry in self.entries:
            sc = entry.structured_content

            # Confirmations
            is_challenge = bool(
                sc.get("needs_confirmation") is True or sc.get("confirmation_required") is True
            )
            if is_challenge:
                metrics.confirmations_requested += 1
            if "confirm_token" in entry.arguments:
                metrics.confirmations_completed += 1

            # Checkpoints
            if entry.tool == "checkpoint_create" and not entry.is_error:
                metrics.checkpoints_created += 1
            elif entry.tool == "checkpoint_rollback" and not entry.is_error:
                metrics.checkpoints_rolled_back += 1

            # Mutations (only count actual mutating executions, not errors or challenges)
            if entry.tool in mutating_tools and not entry.is_error and not is_challenge:
                metrics.mutations_count += 1
                if (
                    sc.get("verified") is True
                    or sc.get("is_valid") is True
                    or sc.get("applied") in (True, "applied", "pending")
                    or sc.get("status") in ("applied", "pending")
                ):
                    metrics.verified_mutations_count += 1

            # Untrusted data
            if sc.get("untrusted") is True or any(
                isinstance(v, dict) and v.get("untrusted") is True for v in sc.values()
            ):
                metrics.untrusted_data_encountered += 1

        return metrics

    def build_result(
        self,
        scenario_id: str,
        name: str,
        description: str,
        requirement_id: str,
        passed: bool,
        error_message: str | None = None,
    ) -> ScenarioResult:
        """Compile a complete ScenarioResult from recorded transcript and metrics."""
        duration_ms = (time.time() - self._scenario_start_time) * 1000.0
        metrics = self.compute_metrics()

        # Score computation:
        # Base 100. Deduct if failed, or if mutations were unverified without explicit failure.
        score = 100.0 if passed else 0.0
        if (
            passed
            and metrics.mutations_count > 0
            and metrics.verified_mutations_count < metrics.mutations_count
        ):
            # Deduct proportionally for unverified mutations
            unverified = metrics.mutations_count - metrics.verified_mutations_count
            deduction = (unverified / metrics.mutations_count) * 40.0
            score = max(0.0, 100.0 - deduction)

        return ScenarioResult(
            scenario_id=scenario_id,
            name=name,
            description=description,
            requirement_id=requirement_id,
            passed=passed,
            duration_ms=duration_ms,
            metrics=metrics,
            transcript=list(self.entries),
            error_message=error_message,
            score=score,
        )


@dataclass
class EvaluationReport:
    """Full evaluation suite execution summary and artifact generator."""

    session_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    environment: str = "DeviceEmulator (Clean Room)"
    scenarios: list[ScenarioResult] = field(default_factory=list)

    @property
    def total_scenarios(self) -> int:
        return len(self.scenarios)

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.scenarios if s.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.scenarios if not s.passed)

    @property
    def pass_rate(self) -> float:
        if not self.scenarios:
            return 0.0
        return (self.passed_count / self.total_scenarios) * 100.0

    @property
    def overall_score(self) -> float:
        if not self.scenarios:
            return 0.0
        return sum(s.score for s in self.scenarios) / len(self.scenarios)

    @property
    def total_duration_ms(self) -> float:
        return sum(s.duration_ms for s in self.scenarios)

    @property
    def total_tool_calls(self) -> int:
        return sum(s.metrics.total_tool_calls for s in self.scenarios)

    def add_scenario(self, result: ScenarioResult) -> None:
        """Add a scenario result to the evaluation report."""
        self.scenarios.append(result)

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete report to structured dictionary."""
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "summary": {
                "total_scenarios": self.total_scenarios,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "pass_rate_pct": round(self.pass_rate, 1),
                "overall_score": round(self.overall_score, 1),
                "total_duration_ms": round(self.total_duration_ms, 2),
                "total_tool_calls": self.total_tool_calls,
            },
            "scenarios": [s.to_dict() for s in self.scenarios],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to indented JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Generate structured human-readable Markdown summary report."""
        lines: list[str] = [
            "# StudioBridge Agent Evaluation Report",
            "",
            f"- **Session ID:** `{self.session_id}`",
            f"- **Timestamp:** {self.timestamp}",
            f"- **Environment:** {self.environment}",
            f"- **Scenarios Evaluated:** {self.total_scenarios}",
            f"- **Passed:** {self.passed_count} / {self.total_scenarios} ({self.pass_rate:.1f}%)",
            f"- **Failed:** {self.failed_count}",
            f"- **Overall Score:** {self.overall_score:.1f}%",
            f"- **Total Tool Calls:** {self.total_tool_calls}",
            f"- **Total Duration:** {self.total_duration_ms:.1f} ms",
            "",
            "## Scenario Breakdown",
            "",
            "| # | ID | Scenario Name | Req ID | Status | Score | Calls | Duration |",
            "|---|---|---|---|---|---|---|---|",
        ]

        for i, s in enumerate(self.scenarios, 1):
            status = "PASS" if s.passed else "**FAIL**"
            score_str = f"{s.score:.0f}%"
            dur_str = f"{s.duration_ms:.0f} ms"
            lines.append(
                f"| {i} | `{s.scenario_id}` | {s.name} | `{s.requirement_id}` | "
                f"{status} | {score_str} | {s.metrics.total_tool_calls} | {dur_str} |"
            )

        if self.failed_count > 0:
            lines.extend(["", "## Failure Details", ""])
            for s in self.scenarios:
                if not s.passed:
                    lines.append(f"### `{s.scenario_id}`: {s.name}")
                    lines.append(f"- **Requirement:** `{s.requirement_id}`")
                    lines.append(f"- **Error:** {s.error_message or 'Unknown error'}")
                    lines.append("")

        return "\n".join(lines) + "\n"

    def save(self, json_path: Path | str, md_path: Path | str | None = None) -> None:
        """Save report to JSON file and optional Markdown file."""
        jp = Path(json_path)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(self.to_json(), encoding="utf-8")

        if md_path is not None:
            mp = Path(md_path)
            mp.parent.mkdir(parents=True, exist_ok=True)
            mp.write_text(self.to_markdown(), encoding="utf-8")


__all__ = [
    "EvaluationReport",
    "ScenarioMetrics",
    "ScenarioResult",
    "TranscriptEntry",
    "TranscriptRecorder",
]
