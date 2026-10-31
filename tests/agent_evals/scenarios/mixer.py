"""Mixer evaluation scenarios exercising stem balancing, panning, and track isolation.

Covers:
- Scenario 1: Mixer stem balancing & volume adjustment (# req: EVAL-01)
- Scenario 2: Mixer panning & stereo placement (# req: EVAL-02)
- Scenario 3: Track mute & solo toggling (# req: EVAL-03)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-01-mixer-balance",
    name="Mixer stem balancing & volume adjustment",
    description=(
        "Inspect drum bus volume, switch to write mode, checkpoint, and balance track level safely."
    ),
    requirement_id="EVAL-01",
)
def run_scenario_mixer_balance(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 1: Mixer stem balancing & volume adjustment (# req: EVAL-01)."""
    # Turn 1: Inspect host status
    res_status = harness.step(
        "Balance the drum bus: reduce track 3 volume by 2 dB safely.",
        [ToolCall(tool="studio_status")],
    )
    assert res_status[0].structured_content["connected"] is True
    assert res_status[0].structured_content["mode"] == "read_only"

    # Turn 2: Read current mixer track 3 volume
    res_read = harness.step(
        "Inspect track 3 initial volume",
        [ToolCall(tool="mixer_get", arguments={"track": 3})],
    )
    initial_vol = res_read[0].structured_content["volume"]
    assert initial_vol == pytest.approx(0.8, abs=0.02)

    # Turn 3: Request mode switch to write
    res_chal = harness.step(
        "Request switch to write mode for mixer modifications",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    assert token is not None

    # Turn 3b: Confirm mode switch
    res_mode = harness.step(
        "Confirm switch to write mode with token",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
    )
    assert res_mode[0].structured_content["mode"] == "write"

    # Turn 4: Create rollback checkpoint
    res_cp = harness.step(
        "Create rollback checkpoint before modifying mixer",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_drum_bus_balance"})],
    )
    assert res_cp[0].structured_content.get("verified") is True

    # Turn 5: Apply target volume (0.65)
    target_vol = 0.65
    res_set = harness.step(
        f"Apply volume change to track 3: {target_vol}",
        [ToolCall(tool="mixer_set", arguments={"track": 3, "volume": target_vol})],
    )
    set_sc = res_set[0].structured_content
    assert set_sc.get("verified") is True
    assert isinstance(set_sc.get("journal_id"), int)

    # Turn 6: Verify volume readback
    res_verify = harness.step(
        "Verify track 3 updated level",
        [ToolCall(tool="mixer_get", arguments={"track": 3})],
    )
    final_vol = res_verify[0].structured_content["volume"]
    assert final_vol == pytest.approx(target_vol, abs=0.01)

    harness.assert_call_sequence(
        "studio_status",
        "mixer_get",
        "studio_set_mode",
        "checkpoint_create",
        "mixer_set",
        "mixer_get",
    )
    harness.assert_safety_sequence(mutation_tool="mixer_set")
    harness.assert_mode("write")


@register_scenario(
    id="eval-02-mixer-panning",
    name="Mixer panning & stereo placement",
    description=(
        "Inspect track stereo placement, create checkpoint, and set stereo pan left and right."
    ),
    requirement_id="EVAL-02",
)
def run_scenario_mixer_panning(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 2: Mixer panning & stereo placement (# req: EVAL-02)."""
    # Turn 1: Inspect host status
    harness.step("Check studio status", [ToolCall(tool="studio_status")])

    # Turn 2: Inspect initial pan of track 2
    res_init = harness.step(
        "Read track 2 initial stereo pan",
        [ToolCall(tool="mixer_get", arguments={"track": 2})],
    )
    assert res_init[0].structured_content["pan"] == pytest.approx(0.0, abs=0.05)

    # Turn 3: Switch to write mode with confirmation
    res_chal = harness.step(
        "Request switch to write mode",
        [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
    )
    token = res_chal[0].structured_content.get("confirm_token")
    if token:
        harness.step(
            "Confirm switch to write mode",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )

    # Turn 4: Create checkpoint
    res_cp = harness.step(
        "Create checkpoint before panning adjustment",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_pan_adjust"})],
    )
    assert res_cp[0].structured_content.get("verified") is True

    # Turn 5: Set pan left (-0.5)
    res_left = harness.step(
        "Pan track 2 to left position (-0.5)",
        [ToolCall(tool="mixer_set", arguments={"track": 2, "pan": -0.5})],
    )
    assert res_left[0].structured_content.get("verified") is True

    # Turn 6: Verify left pan
    res_vleft = harness.step(
        "Verify left pan on track 2",
        [ToolCall(tool="mixer_get", arguments={"track": 2})],
    )
    assert res_vleft[0].structured_content["pan"] == pytest.approx(-0.5, abs=0.02)

    # Turn 7: Set pan right (0.5)
    res_right = harness.step(
        "Pan track 2 to right position (0.5)",
        [ToolCall(tool="mixer_set", arguments={"track": 2, "pan": 0.5})],
    )
    assert res_right[0].structured_content.get("verified") is True

    # Turn 8: Verify right pan
    res_vright = harness.step(
        "Verify right pan on track 2",
        [ToolCall(tool="mixer_get", arguments={"track": 2})],
    )
    assert res_vright[0].structured_content["pan"] == pytest.approx(0.5, abs=0.02)

    harness.assert_safety_sequence(mutation_tool="mixer_set")


@register_scenario(
    id="eval-03-mixer-mute-solo",
    name="Track mute & solo toggling",
    description="Isolate and mute mixer tracks safely with checkpoints and readback verification.",
    requirement_id="EVAL-03",
)
def run_scenario_mixer_mute_solo(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 3: Track mute & solo toggling (# req: EVAL-03)."""
    # Turn 1: Inspect initial state
    res_init = harness.step(
        "Inspect track 4 mute/solo state",
        [ToolCall(tool="mixer_get", arguments={"track": 4})],
    )
    assert res_init[0].structured_content["muted"] is False
    assert res_init[0].structured_content["solo"] is False

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

    # Turn 3: Create checkpoint
    harness.step(
        "Create checkpoint before mute/solo toggle",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_mute_solo"})],
    )

    # Turn 4: Mute track 4
    res_mute = harness.step(
        "Mute track 4",
        [ToolCall(tool="mixer_set", arguments={"track": 4, "mute": True})],
    )
    assert res_mute[0].structured_content.get("verified") is True

    # Turn 5: Verify track is muted
    res_vmute = harness.step(
        "Verify track 4 is muted",
        [ToolCall(tool="mixer_get", arguments={"track": 4})],
    )
    assert res_vmute[0].structured_content["muted"] is True

    # Turn 6: Solo track 4
    res_solo = harness.step(
        "Solo track 4",
        [ToolCall(tool="mixer_set", arguments={"track": 4, "solo": True})],
    )
    assert res_solo[0].structured_content.get("verified") is True

    # Turn 7: Verify track is soloed
    res_vsolo = harness.step(
        "Verify track 4 is soloed",
        [ToolCall(tool="mixer_get", arguments={"track": 4})],
    )
    assert res_vsolo[0].structured_content["solo"] is True

    # Turn 8: Unmute and unsolo track 4
    res_restore = harness.step(
        "Restore track 4 mute and solo to False",
        [ToolCall(tool="mixer_set", arguments={"track": 4, "mute": False, "solo": False})],
    )
    assert res_restore[0].structured_content.get("verified") is True

    # Turn 9: Verify restored state
    res_vrest = harness.step(
        "Verify track 4 restored state",
        [ToolCall(tool="mixer_get", arguments={"track": 4})],
    )
    assert res_vrest[0].structured_content["muted"] is False
    assert res_vrest[0].structured_content["solo"] is False

    harness.assert_safety_sequence(mutation_tool="mixer_set")
