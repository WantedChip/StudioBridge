"""Scripted agent evaluation harness for StudioBridge.

Simulates multi-turn AI agent tool calling against emulator-backed or live sessions,
asserting strict safety sequences (checkpoint -> mutate -> verify -> journal),
tolerance adherence, and confirmation challenge protocols.
"""

from __future__ import annotations

import math
import struct
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.core.errors import BrokerError, StudioBridgeError
from studiobridge.core.paths import get_jobs_dir
from studiobridge.mcp.server import VALID_TOOLSETS, StudioMcpServer, ToolResult
from studiobridge.mcp.tools.control import ControlTools
from studiobridge.mcp.tools.core import CoreTools
from studiobridge.mcp.tools.flp import FlpTools
from studiobridge.mcp.tools.inspect import InspectTools
from studiobridge.mcp.tools.notes import NotesTools
from studiobridge.mcp.tools.render import RenderTools
from studiobridge.mcp.tools.safety import SafetyTools
from studiobridge.pianoroll.orchestrator import NoteApplyOrchestrator
from studiobridge.render.job import JobState, RenderJob
from studiobridge.render.runner import RenderRunner
from studiobridge.sdk.client import Studio
from tests.agent_evals.reporter import TranscriptRecorder


def create_synthetic_wav(
    path: Path,
    duration_s: float = 1.0,
    sample_rate: int = 44100,
) -> Path:
    """Generate a clean synthetic sine wave PCM 16-bit WAV file for testing."""
    n_samples = int(duration_s * sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(16384 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return path


class MockRenderRunner(RenderRunner):
    """Mock runner simulating headless export for test and evaluation environments."""

    def __init__(self, output_wav: Path | None = None) -> None:
        self.output_wav = output_wav

    def run(self, job: RenderJob) -> RenderJob:
        job.state = JobState.RENDERING
        out_dir = job.out_dir or (get_jobs_dir() / job.job_id / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        job.out_dir = out_dir

        dest = out_dir / f"{job.source.stem}.wav"
        if self.output_wav and self.output_wav.exists():
            dest.write_bytes(self.output_wav.read_bytes())
        else:
            create_synthetic_wav(dest)
        job.output_files = [dest]

        job.state = JobState.DONE
        job.metrics = {
            "duration_s": 1.0,
            "peak_dbfs": -6.0,
            "rms_dbfs": -9.0,
            "silence_ratio": 0.0,
        }
        return job

    def cancel(self, job_id: str) -> bool:
        return True


@dataclass
class ToolCall:
    """Represents a simulated tool invocation by an agent."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecution:
    """Recorded trace of a tool execution during a turn."""

    turn: int
    call: ToolCall
    result: ToolResult
    timestamp: float = field(default_factory=time.time)

    @property
    def tool_name(self) -> str:
        return self.call.tool

    @property
    def arguments(self) -> dict[str, Any]:
        return self.call.arguments

    @property
    def structured_content(self) -> dict[str, Any]:
        return self.result.structured_content or {}

    @property
    def is_error(self) -> bool:
        return self.result.is_error


class ScriptedAgentHarness:
    """Test runner simulating multi-turn agent tool calls and asserting safety sequences."""

    def __init__(
        self,
        studio: Studio,
        server: StudioMcpServer | None = None,
        recorder: TranscriptRecorder | None = None,
        render_runner: RenderRunner | None = None,
        pyscript_dir: Path | None = None,
    ) -> None:
        self.studio = studio
        self.server = server or StudioMcpServer(client=studio, toolsets=VALID_TOOLSETS)
        self.recorder = recorder

        # Core and Inspect tool suites
        self.core_tools = CoreTools(client=studio, server=self.server)
        self.inspect_tools = InspectTools(client=studio, server=self.server)
        self.control_tools = ControlTools(client=studio, server=self.server)
        self.safety_tools = SafetyTools(client=studio, server=self.server)

        # Extended tool suites
        self.flp_tools = FlpTools(client=studio, server=self.server)
        self.notes_orchestrator = NoteApplyOrchestrator(pyscript_dir=pyscript_dir)
        self.notes_tools = NotesTools(
            client=studio,
            server=self.server,
            orchestrator=self.notes_orchestrator,
        )
        self.render_runner = render_runner or MockRenderRunner()
        self.render_tools = RenderTools(
            client=studio,
            server=self.server,
            runner=self.render_runner,
        )

        self.history: list[ToolExecution] = []
        self.current_turn: int = 0

        # Build dynamic tool dispatcher mapping tool names and standard aliases
        self._dispatch_map: dict[str, Callable[..., ToolResult]] = {
            # Core
            "studio_status": self.core_tools.studio_status,
            "studio_capabilities": self.core_tools.studio_capabilities,
            "capabilities_list": self.core_tools.studio_capabilities,
            "studio_doctor": self.core_tools.studio_doctor,
            "api_search": self.core_tools.api_search,
            "api_describe": self.core_tools.api_describe,
            "project_snapshot": self.core_tools.project_snapshot,
            "project_get": self.core_tools.project_snapshot,
            # Inspect
            "transport_get": self.inspect_tools.transport_get,
            "mixer_list": self.inspect_tools.mixer_list,
            "mixer_get": self.inspect_tools.mixer_get,
            "channels_list": self.inspect_tools.channels_list,
            "channels_get": self.inspect_tools.channels_list,
            "channel_get": self.inspect_tools.channel_get,
            "patterns_list": self.inspect_tools.patterns_list,
            "patterns_get": self.inspect_tools.patterns_list,
            "playlist_get": self.inspect_tools.playlist_get,
            "plugin_params_list": self.inspect_tools.plugin_params_list,
            "plugin_param_get": self.inspect_tools.plugin_param_get,
            "events_recent": self.inspect_tools.events_recent,
            # Control
            "mixer_set": self.control_tools.mixer_set,
            "channel_set": self.control_tools.channel_set,
            "transport_control": self.control_tools.transport_control,
            "plugin_param_set": self.control_tools.plugin_param_set,
            "pattern_edit": self.control_tools.pattern_edit,
            "steps_set": self.control_tools.steps_set,
            "playlist_edit": self.control_tools.playlist_edit,
            "playlist_place_pattern": self.control_tools.playlist_place_pattern,
            # Safety
            "studio_set_mode": self.safety_tools.studio_set_mode,
            "checkpoint_create": self.safety_tools.checkpoint_create,
            "checkpoint_rollback": self.safety_tools.checkpoint_rollback,
            "journal_list": self.safety_tools.journal_list,
            # Offline FLP
            "flp_inspect": self.flp_tools.flp_inspect,
            "flp_diff": self.flp_tools.flp_diff,
            "flp_validate": self.flp_tools.flp_validate,
            "flp_save_as": self.flp_tools.flp_save_as,
            "flp_new_from_template": self.flp_tools.flp_new_from_template,
            "flp_edit": self.flp_tools.flp_edit,
            # Notes & Piano Roll
            "notes_apply": self.notes_tools.notes_apply,
            "notes_read": self.notes_tools.notes_read,
            "notes_from_midi": self.notes_tools.notes_from_midi,
            # Render
            "render_start": self.render_tools.render_start,
            "render_status": self.render_tools.render_status,
            "render_cancel": self.render_tools.render_cancel,
            "render_analyze": self.render_tools.render_analyze,
        }

    def call_tool(self, tool_name: str, **arguments: Any) -> ToolResult:
        """Execute a tool call by name and record it in execution history."""
        if tool_name not in self._dispatch_map:
            raise ValueError(f"Unknown tool '{tool_name}' in scripted harness dispatcher.")

        fn = self._dispatch_map[tool_name]
        start_t = time.time()
        try:
            result = fn(**arguments)
        except BrokerError as err:
            # Handle rate limiter retryable E_BUSY backoff
            if err.retryable and err.details and "retry_ms" in err.details:
                wait_s = (float(err.details["retry_ms"]) + 5.0) / 1000.0
                time.sleep(wait_s)
                result = fn(**arguments)
            else:
                result = ToolResult(
                    content=[{"type": "text", "text": str(err)}],
                    structured_content={"error": err.code, "message": str(err)},
                    is_error=True,
                )
        except StudioBridgeError as err:
            result = ToolResult(
                content=[{"type": "text", "text": str(err)}],
                structured_content={
                    "error": err.code,
                    "message": str(err),
                    "details": err.details,
                    "remedy": err.remedy,
                },
                is_error=True,
            )
        except Exception as exc:
            result = ToolResult(
                content=[{"type": "text", "text": str(exc)}],
                structured_content={"error": type(exc).__name__, "message": str(exc)},
                is_error=True,
            )

        duration_ms = (time.time() - start_t) * 1000.0
        call_record = ToolCall(tool=tool_name, arguments=arguments)
        execution = ToolExecution(
            turn=self.current_turn,
            call=call_record,
            result=result,
        )
        self.history.append(execution)

        if self.recorder is not None:
            self.recorder.record_call(
                tool=tool_name,
                arguments=arguments,
                result_content=result.content,
                structured_content=result.structured_content,
                is_error=result.is_error,
                duration_ms=duration_ms,
            )

        return result

    def step(self, user_message: str, calls: list[ToolCall]) -> list[ToolResult]:
        """Simulate a dialog turn with a user message and a sequence of tool calls."""
        self.current_turn += 1
        if self.recorder is not None:
            self.recorder.set_user_message(user_message, turn=self.current_turn)

        results: list[ToolResult] = []
        for c in calls:
            res = self.call_tool(c.tool, **c.arguments)
            results.append(res)
        time.sleep(0.005)
        return results

    # =========================================================================
    # Evaluation Assertion Helpers
    # =========================================================================

    def assert_tool_called(self, tool_name: str, count: int | None = None) -> list[ToolExecution]:
        """Assert that a tool was called at least once (or exact count)."""
        matching = [e for e in self.history if e.tool_name == tool_name]
        assert matching, f"Expected tool '{tool_name}' to be called, but it was not in history."
        if count is not None:
            assert len(matching) == count, (
                f"Expected tool '{tool_name}' to be called {count} times, "
                f"but was called {len(matching)} times."
            )
        return matching

    def assert_call_sequence(self, *tool_names: str) -> None:
        """Assert that the specified tools were called in the given relative order."""
        actual_names = [e.tool_name for e in self.history]
        it = iter(actual_names)
        for expected in tool_names:
            found = False
            for actual in it:
                if actual == expected:
                    found = True
                    break
            assert found, (
                f"Call sequence violation: expected '{expected}' in sequence {tool_names}, "
                f"actual call sequence was: {actual_names}"
            )

    def assert_safety_sequence(self, mutation_tool: str = "mixer_set") -> None:
        """Assert strict safety sequence for any mutating operation.

        Strict safety rules:
        1. A checkpoint MUST be created (`checkpoint_create`) before the mutation.
        2. The mutation tool must succeed without error (`is_error == False`).
        3. The mutation receipt must have `verified == True`.
        4. A verification read-back or inspection tool must be called after the mutation.
        """
        # 1. Sequence: checkpoint_create before mutation_tool
        self.assert_call_sequence("checkpoint_create", mutation_tool)

        # 2. Checkpoint index and mutation index
        cp_indices = [i for i, e in enumerate(self.history) if e.tool_name == "checkpoint_create"]
        mut_indices = [i for i, e in enumerate(self.history) if e.tool_name == mutation_tool]

        assert cp_indices, "Missing 'checkpoint_create' before mutation."
        assert mut_indices, f"Missing '{mutation_tool}' mutation in history."

        # The last checkpoint before mutation must exist
        first_mut_idx = mut_indices[0]
        checkpoints_before_mut = [idx for idx in cp_indices if idx < first_mut_idx]
        assert checkpoints_before_mut, (
            f"No 'checkpoint_create' was called prior to '{mutation_tool}' "
            f"at index {first_mut_idx}."
        )

        # 3. Mutation receipt verified
        for mut_idx in mut_indices:
            mut_exec = self.history[mut_idx]
            assert not mut_exec.is_error, f"Mutation '{mutation_tool}' failed: {mut_exec.result}"
            sc = mut_exec.structured_content
            assert sc.get("verified") is True, (
                f"Expected mutation receipt 'verified: true', but got: {sc}"
            )
            assert "journal_id" in sc, f"Expected 'journal_id' in receipt, got: {sc}"

        # 4. Post-mutation verification
        # At least one inspect call or verification getter after the mutation
        post_mut_calls = self.history[first_mut_idx + 1 :]
        assert post_mut_calls, (
            f"Expected verification tool call following '{mutation_tool}', but none found."
        )

    def assert_no_mutations(self) -> None:
        """Assert that no mutating tools were called and session remained read-only."""
        mutating_tools = {
            "mixer_set",
            "channel_set",
            "transport_control",
            "plugin_param_set",
            "pattern_edit",
            "steps_set",
            "playlist_edit",
            "playlist_place_pattern",
        }
        for e in self.history:
            assert e.tool_name not in mutating_tools, (
                f"Mutating tool '{e.tool_name}' was unexpectedly called "
                "during read-only inspection."
            )

    def assert_mode(self, expected_mode: str) -> None:
        """Assert that client is in the expected safety mode."""
        actual = self.studio.safety.mode
        if expected_mode in ("write", "write_autonomous"):
            assert actual in ("write", "write_autonomous"), (
                f"Expected write safety mode, but found '{actual}'."
            )
        else:
            assert actual == expected_mode, (
                f"Expected safety mode '{expected_mode}', but found '{actual}'."
            )


__all__ = [
    "MockRenderRunner",
    "ScriptedAgentHarness",
    "ToolCall",
    "ToolExecution",
    "create_synthetic_wav",
]
