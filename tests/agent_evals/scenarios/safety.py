"""Safety evaluation scenarios.

Exercises read-only interlocks, journal checkpoints, and rollback guarantees.

Covers:
- Scenario 16: Read-only session safety enforcement (# req: EVAL-16)
- Scenario 17: Mutation journal checkpoint & rollback verification (# req: EVAL-17)
- Scenario 18: Recovery from unverified / failing writes (# req: EVAL-18)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-16-read-only-safety",
    name="Read-only session safety enforcement",
    description=(
        "Verify mutating calls in read-only mode trigger confirmation challenge, "
        "blocking unauthorized execution."
    ),
    requirement_id="EVAL-16",
)
def run_scenario_read_only_safety(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 16: Read-only session safety enforcement (# req: EVAL-16)."""
    # Turn 1: Verify session is in read-only mode
    res_status = harness.step(
        "Verify read-only session mode",
        [ToolCall(tool="studio_status")],
    )
    assert res_status[0].structured_content["mode"] == "read_only"

    # Turn 2: Attempt mutation without confirmation token -> challenge issued
    res_chal = harness.step(
        "Attempt channel mute in read-only mode",
        [ToolCall(tool="channel_set", arguments={"channel": 1, "mute": True})],
    )
    sc = res_chal[0].structured_content
    assert sc.get("needs_confirmation") is True
    token = sc.get("confirm_token")
    assert token is not None

    # Turn 3: Verify state was NOT changed
    res_read = harness.step(
        "Verify channel 1 is still unmuted",
        [ToolCall(tool="channel_get", arguments={"channel": 1})],
    )
    assert res_read[0].structured_content["muted"] is False

    # Turn 4: Create safety checkpoint
    res_cp = harness.step(
        "Create rollback checkpoint before authorized mutation",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_mute_ch1"})],
    )
    assert res_cp[0].structured_content.get("verified") is True

    # Turn 5: Re-invoke with confirm_token
    res_exec = harness.step(
        "Apply mutation with confirm_token",
        [
            ToolCall(
                tool="channel_set",
                arguments={"channel": 1, "mute": True, "confirm_token": token},
            )
        ],
    )
    assert res_exec[0].structured_content.get("verified") is True

    # Turn 6: Verify channel is now muted
    res_verify = harness.step(
        "Verify channel 1 is muted after confirmation",
        [ToolCall(tool="channel_get", arguments={"channel": 1})],
    )
    assert res_verify[0].structured_content["muted"] is True


@register_scenario(
    id="eval-17-journal-rollback",
    name="Mutation journal checkpoint & rollback verification",
    description=(
        "Create named checkpoint, apply parameter modifications, "
        "inspect journal, and execute verified rollback."
    ),
    requirement_id="EVAL-17",
)
def run_scenario_journal_rollback(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 17: Mutation journal checkpoint & rollback verification (# req: EVAL-17)."""
    # Turn 1: Inspect initial track 5 volume
    res_init = harness.step(
        "Inspect initial track 5 volume",
        [ToolCall(tool="mixer_get", arguments={"track": 5})],
    )
    initial_vol = res_init[0].structured_content["volume"]

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
    res_cp = harness.step(
        "Create checkpoint before volume modification",
        [ToolCall(tool="checkpoint_create", arguments={"name": "test_rollback_point"})],
    )
    cp_id = res_cp[0].structured_content["checkpoint_id"]

    # Turn 4: Mutate volume to 0.35
    harness.step(
        "Mutate track 5 volume to 0.35",
        [ToolCall(tool="mixer_set", arguments={"track": 5, "volume": 0.35})],
    )

    # Turn 5: Verify mutated level
    res_mod = harness.step(
        "Verify mutated level on track 5",
        [ToolCall(tool="mixer_get", arguments={"track": 5})],
    )
    assert res_mod[0].structured_content["volume"] == pytest.approx(0.35, abs=0.01)

    # Turn 6: Inspect mutation journal entries
    res_j = harness.step("Inspect journal entries", [ToolCall(tool="journal_list")])
    assert not res_j[0].is_error
    assert len(res_j[0].structured_content.get("entries", [])) >= 1

    # Turn 7: Rollback to checkpoint
    res_roll = harness.step(
        f"Rollback to checkpoint {cp_id}",
        [ToolCall(tool="checkpoint_rollback", arguments={"checkpoint_id": cp_id})],
    )
    assert not res_roll[0].is_error

    # Turn 8: Verify restored level
    res_final = harness.step(
        "Verify restored level matches initial volume",
        [ToolCall(tool="mixer_get", arguments={"track": 5})],
    )
    assert res_final[0].structured_content["volume"] == pytest.approx(initial_vol, abs=0.01)


@register_scenario(
    id="eval-18-error-recovery",
    name="Recovery from unverified / failing writes",
    description=(
        "Handle protected target and out-of-bounds errors gracefully, "
        "recovering safely via valid alternative paths."
    ),
    requirement_id="EVAL-18",
)
def run_scenario_error_recovery(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 18: Recovery from unverified / failing writes (# req: EVAL-18)."""
    # Turn 1: Switch to write mode
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

    # Turn 2: Attempt illegal write to master track 0 without allow_protected -> returns E_PROTECTED
    res_err = harness.step(
        "Attempt modifying master track 0 without allow_protected",
        [ToolCall(tool="mixer_set", arguments={"track": 0, "volume": 0.70})],
    )
    assert res_err[0].is_error is True
    assert res_err[0].structured_content.get("error") == "E_PROTECTED"

    # Turn 3: Agent inspects error remedy and switches target to valid stem track 3
    res_inspect = harness.step(
        "Inspect track 3 initial volume before alternative write",
        [ToolCall(tool="mixer_get", arguments={"track": 3})],
    )
    assert not res_inspect[0].is_error

    # Turn 4: Create safety checkpoint for alternative write
    harness.step(
        "Create checkpoint for safe alternative write",
        [ToolCall(tool="checkpoint_create", arguments={"name": "before_recovered_write"})],
    )

    # Turn 5: Apply valid mutation to track 3
    target_vol = 0.60
    res_valid = harness.step(
        f"Apply valid volume to track 3: {target_vol}",
        [ToolCall(tool="mixer_set", arguments={"track": 3, "volume": target_vol})],
    )
    assert res_valid[0].is_error is False
    assert res_valid[0].structured_content.get("verified") is True

    # Turn 6: Verify readback
    res_verify = harness.step(
        "Verify recovered write readback",
        [ToolCall(tool="mixer_get", arguments={"track": 3})],
    )
    assert res_verify[0].structured_content["volume"] == pytest.approx(target_vol, abs=0.01)
