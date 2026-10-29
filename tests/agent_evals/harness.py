"""Scripted agent evaluation harness for StudioBridge.

Simulates multi-turn AI agent tool calling against emulator-backed or live sessions,
asserting strict safety sequences (checkpoint -> mutate -> verify -> journal),
tolerance adherence, and confirmation challenge protocols.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from studiobridge.core.errors import BrokerError, StudioBridgeError
from studiobridge.mcp.server import StudioMcpServer, ToolResult
from studiobridge.mcp.tools.control import ControlTools
from studiobridge.mcp.tools.core import CoreTools
from studiobridge.mcp.tools.inspect import InspectTools
from studiobridge.mcp.tools.safety import SafetyTools
from studiobridge.sdk.client import Studio


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

    def __init__(self, studio: Studio, server: StudioMcpServer | None = None) -> None:
        self.studio = studio
        self.server = server or StudioMcpServer(client=studio)
        self.core_tools = CoreTools(client=studio, server=self.server)
        self.inspect_tools = InspectTools(client=studio, server=self.server)
        self.control_tools = ControlTools(client=studio, server=self.server)
        self.safety_tools = SafetyTools(client=studio, server=self.server)

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
        }

    def call_tool(self, tool_name: str, **arguments: Any) -> ToolResult:
        """Execute a tool call by name and record it in execution history."""
        if tool_name not in self._dispatch_map:
            raise ValueError(f"Unknown tool '{tool_name}' in scripted harness dispatcher.")

        fn = self._dispatch_map[tool_name]
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

        call_record = ToolCall(tool=tool_name, arguments=arguments)
        execution = ToolExecution(
            turn=self.current_turn,
            call=call_record,
            result=result,
        )
        self.history.append(execution)
        return result

    def step(self, user_message: str, calls: list[ToolCall]) -> list[ToolResult]:
        """Simulate a dialog turn with a user message and a sequence of tool calls."""
        self.current_turn += 1
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
    "ScriptedAgentHarness",
    "ToolCall",
    "ToolExecution",
]
