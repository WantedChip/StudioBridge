"""Transport evaluation scenarios exercising playback, tempo manipulation, and timeline seeks.

Covers:
- Scenario 4: Transport play / stop / pause lifecycle (# req: EVAL-04)
- Scenario 5: Transport tempo adjustment & validation (# req: EVAL-05)
- Scenario 6: Transport song position seek (# req: EVAL-06)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-04-transport-lifecycle",
    name="Transport play / stop / pause lifecycle",
    description=(
        "Inspect transport state, start playback, verify playing status, and stop playback."
    ),
    requirement_id="EVAL-04",
)
def run_scenario_transport_lifecycle(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 4: Transport play / stop / pause lifecycle (# req: EVAL-04)."""
    # Turn 1: Inspect initial transport state
    res_init = harness.step(
        "Inspect initial transport playback status",
        [ToolCall(tool="transport_get")],
    )
    assert res_init[0].structured_content["is_playing"] is False

    # Turn 2: Switch to write mode
    res_chal = harness.step(
        "Switch to write mode for transport control",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    if token:
        harness.step(
            "Confirm write mode",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )

    # Turn 3: Start playback
    res_play = harness.step(
        "Start playback",
        [ToolCall(tool="transport_control", arguments={"action": "play"})],
    )
    assert res_play[0].structured_content.get("verified") is True
    assert res_play[0].structured_content.get("action") == "play"

    # Turn 4: Verify playback started
    res_vplay = harness.step(
        "Verify transport is playing",
        [ToolCall(tool="transport_get")],
    )
    assert res_vplay[0].structured_content["is_playing"] is True

    # Turn 5: Stop playback
    res_stop = harness.step(
        "Stop playback",
        [ToolCall(tool="transport_control", arguments={"action": "stop"})],
    )
    assert res_stop[0].structured_content.get("verified") is True
    assert res_stop[0].structured_content.get("action") == "stop"

    # Turn 6: Verify playback stopped
    res_vstop = harness.step(
        "Verify transport is stopped",
        [ToolCall(tool="transport_get")],
    )
    assert res_vstop[0].structured_content["is_playing"] is False

    harness.assert_call_sequence("transport_get", "transport_control", "transport_get")


@register_scenario(
    id="eval-05-transport-tempo",
    name="Transport tempo adjustment & validation",
    description=(
        "Inspect tempo, navigate protected interlocks with confirmation tokens, "
        "and verify BPM target."
    ),
    requirement_id="EVAL-05",
)
def run_scenario_transport_tempo(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 5: Transport tempo adjustment & validation (# req: EVAL-05)."""
    # Turn 1: Inspect current tempo
    res_init = harness.step(
        "Read project initial tempo",
        [ToolCall(tool="transport_get")],
    )
    initial_bpm = res_init[0].structured_content["tempo"]
    assert initial_bpm == pytest.approx(120.0, abs=1.0)

    # Turn 2: Switch to write mode
    res_chal = harness.step(
        "Switch to write mode",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    if token:
        harness.step(
            "Confirm write mode",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )

    # Turn 3: Create checkpoint before tempo modification
    harness.step(
        "Create checkpoint before modifying global tempo",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_tempo_change"})],
    )

    # Turn 4: Attempt tempo change without allow_protected -> E_PROTECTED error
    res_err = harness.step(
        "Set tempo without allow_protected (triggers E_PROTECTED)",
        [ToolCall(tool="transport_control", arguments={"action": "tempo", "tempo": 135.0})],
    )
    assert res_err[0].is_error is True
    assert res_err[0].structured_content.get("error") == "E_PROTECTED"

    # Turn 4b: Supply allow_protected=True -> triggers confirmation challenge
    res_prot = harness.step(
        "Supply allow_protected=True to request confirmation challenge",
        [
            ToolCall(
                tool="transport_control",
                arguments={"action": "tempo", "tempo": 135.0, "allow_protected": True},
            )
        ],
    )
    assert res_prot[0].structured_content.get("needs_confirmation") is True
    confirm_token = res_prot[0].structured_content.get("confirm_token")
    assert confirm_token is not None

    # Turn 5: Re-invoke with allow_protected=True and confirm_token
    res_apply = harness.step(
        "Apply tempo change with confirmation token",
        [
            ToolCall(
                tool="transport_control",
                arguments={
                    "action": "tempo",
                    "tempo": 135.0,
                    "allow_protected": True,
                    "confirm_token": confirm_token,
                },
            )
        ],
    )
    assert res_apply[0].structured_content.get("verified") is True

    # Turn 6: Read back and verify updated tempo
    res_final = harness.step(
        "Verify updated project tempo",
        [ToolCall(tool="transport_get")],
    )
    assert res_final[0].structured_content["tempo"] == pytest.approx(135.0, abs=0.1)


@register_scenario(
    id="eval-06-transport-seek",
    name="Transport song position seek",
    description=(
        "Inspect playback position, seek song position to specified fraction, and reset cleanly."
    ),
    requirement_id="EVAL-06",
)
def run_scenario_transport_seek(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 6: Transport song position seek (# req: EVAL-06)."""
    # Turn 1: Inspect initial position
    harness.step("Inspect transport state", [ToolCall(tool="transport_get")])

    # Turn 2: Switch to write mode
    res_chal = harness.step(
        "Switch to write mode",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    if token:
        harness.step(
            "Confirm write mode",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )

    # Turn 3: Seek song position to 0.5 (halfway)
    res_seek = harness.step(
        "Seek song position to 0.50",
        [ToolCall(tool="transport_control", arguments={"action": "seek", "position": 0.5})],
    )
    assert res_seek[0].structured_content.get("verified") is True
    assert res_seek[0].structured_content.get("action") == "seek"

    # Turn 4: Verify seek executed
    res_vseek = harness.step(
        "Inspect transport position",
        [ToolCall(tool="transport_get")],
    )
    assert not res_vseek[0].is_error

    # Turn 5: Seek back to start (0.0)
    res_reset = harness.step(
        "Reset song position to 0.0",
        [ToolCall(tool="transport_control", arguments={"action": "seek", "position": 0.0})],
    )
    assert res_reset[0].structured_content.get("verified") is True

    # Turn 6: Verify reset
    res_vreset = harness.step(
        "Inspect transport position after reset",
        [ToolCall(tool="transport_get")],
    )
    assert not res_vreset[0].is_error
