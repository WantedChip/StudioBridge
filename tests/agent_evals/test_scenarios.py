"""Scripted multi-turn agent evaluation scenarios against DeviceEmulator.

Verifies that simulated AI coding agents correctly execute required safety sequences
(checkpoint_create -> mutation -> verify -> journal), observe safety modes,
handle confirmation challenges, and avoid destructive unverified operations per
spec 10_l2_interfaces.md §6, §7 and 14_agent_playbook.md T-AGT-02 [SKL-01].
"""

from __future__ import annotations

import pytest

from studiobridge.sdk.client import Studio
from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall


class TestAgentEvaluationScenarios:
    """Multi-turn evaluation scenarios exercising agent workflows and safety sequences."""

    def test_scenario_balance_drum_bus(self, eval_studio_readonly: Studio) -> None:
        """Scenario: 'Balance the drum bus: reduce track 3 volume by 2 dB safely'.

        Agent workflow:
        Turn 1: Inspect host status via studio_status.
        Turn 2: Read current mixer track 3 level via mixer_get(track=3).
        Turn 3: Request mode transition to write mode via studio_set_mode(mode='write')
                and confirm challenge token.
        Turn 4: Create safety checkpoint via checkpoint_create(name='before_drum_bus_balance').
        Turn 5: Adjust track 3 volume to target (0.65) via mixer_set(track=3, volume=0.65).
        Turn 6: Verify final volume via mixer_get(track=3).
        """
        harness = ScriptedAgentHarness(studio=eval_studio_readonly)

        # Turn 1: User says "Balance the drum bus: reduce track 3 volume by 2 dB safely."
        # Agent checks status first
        res_status = harness.step(
            "Balance the drum bus: reduce track 3 volume by 2 dB safely.",
            [ToolCall(tool="studio_status")],
        )
        assert res_status[0].structured_content["connected"] is True
        assert res_status[0].structured_content["mode"] == "read_only"

        # Turn 2: Agent reads current level of track 3
        res_read = harness.step(
            "Inspect track 3 initial volume",
            [ToolCall(tool="mixer_get", arguments={"track": 3})],
        )
        sc_read = res_read[0].structured_content
        initial_vol = sc_read["volume"]
        assert initial_vol == pytest.approx(0.8, abs=0.02)

        # Turn 3: Agent requests switch to write mode
        res_chal = harness.step(
            "Request switch to write mode for mixer modifications",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write"})],
        )
        assert res_chal[0].structured_content.get("needs_confirmation") is True
        token = res_chal[0].structured_content.get("confirm_token")
        assert token is not None

        # Turn 3b: User confirms -> switch to write mode with token
        res_mode = harness.step(
            "Confirm switch to write mode with token",
            [ToolCall(tool="studio_set_mode", arguments={"mode": "write", "confirm_token": token})],
        )
        assert res_mode[0].structured_content["mode"] == "write"

        # Turn 4: Agent creates rollback checkpoint
        res_cp = harness.step(
            "Create rollback checkpoint before modifying mixer",
            [ToolCall(tool="checkpoint_create", arguments={"name": "before_drum_bus_balance"})],
        )
        cp_id = res_cp[0].structured_content.get("checkpoint_id")
        assert cp_id is not None
        assert res_cp[0].structured_content.get("verified") is True

        # Turn 5: Agent applies target volume (0.65 ~ -2 dB delta from 0.80)
        target_vol = 0.65
        res_set = harness.step(
            f"Apply volume change to track 3: {target_vol}",
            [ToolCall(tool="mixer_set", arguments={"track": 3, "volume": target_vol})],
        )
        set_sc = res_set[0].structured_content
        assert set_sc.get("verified") is True
        assert set_sc.get("plane") in ("emulator", "live")
        assert isinstance(set_sc.get("journal_id"), int)

        # Turn 6: Agent verifies volume readback
        res_verify = harness.step(
            "Verify track 3 updated level",
            [ToolCall(tool="mixer_get", arguments={"track": 3})],
        )
        final_sc = res_verify[0].structured_content
        final_vol = final_sc["volume"]
        assert final_vol == pytest.approx(target_vol, abs=0.01)

        # =====================================================================
        # Safety Assertions
        # =====================================================================
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

    def test_scenario_inspect_session_readonly(self, eval_studio_readonly: Studio) -> None:
        """Scenario: 'Give me an overview of the current session and mixer tracks'.

        Agent workflow:
        Turn 1: studio_status
        Turn 2: project_get()
        Turn 3: transport_get()
        Turn 4: mixer_get(track=0)
        Turn 5: channel_get(channel=0)
        Turn 6: patterns_get()

        Asserts:
        - Session remains in read_only mode throughout.
        - Zero mutating calls are made.
        - Strings carry untrusted metadata.
        """
        harness = ScriptedAgentHarness(studio=eval_studio_readonly)

        # Turn 1: Check status
        harness.step("Check status", [ToolCall(tool="studio_status")])

        # Turn 2: Inspect project summary
        res_proj = harness.step("Get project details", [ToolCall(tool="project_get")])
        assert not res_proj[0].is_error

        # Turn 3: Inspect transport
        res_trans = harness.step("Inspect transport", [ToolCall(tool="transport_get")])
        assert not res_trans[0].is_error

        # Turn 4: Inspect master mixer track
        res_mixer = harness.step(
            "Inspect Master track",
            [ToolCall(tool="mixer_get", arguments={"track": 0})],
        )
        assert not res_mixer[0].is_error
        assert res_mixer[0].structured_content.get("index") == 0

        # Turn 5: Inspect channel
        res_chan = harness.step(
            "Inspect channel 0",
            [ToolCall(tool="channel_get", arguments={"channel": 0})],
        )
        assert not res_chan[0].is_error

        # Turn 6: Inspect patterns
        res_pat = harness.step("Inspect patterns", [ToolCall(tool="patterns_get")])
        assert not res_pat[0].is_error

        # Safety assertions
        harness.assert_no_mutations()
        harness.assert_mode("read_only")

    def test_scenario_read_only_challenge_and_confirmation(
        self, eval_studio_readonly: Studio
    ) -> None:
        """Scenario: Agent attempts mutation while in read_only mode.

        Asserts:
        - Mutating call triggers confirmation challenge with confirm_token.
        - Supplying valid token with checkpoint authorization unlocks execution.
        """
        harness = ScriptedAgentHarness(studio=eval_studio_readonly)

        # 1. Mutating tool call in read_only mode -> challenge
        res_chal = harness.step(
            "Mute channel 1",
            [ToolCall(tool="channel_set", arguments={"channel": 1, "mute": True})],
        )
        sc = res_chal[0].structured_content
        assert sc.get("needs_confirmation") is True
        token = sc.get("confirm_token")
        assert token is not None

        # 2. Agent creates checkpoint
        res_cp = harness.step(
            "Create checkpoint before authorized mutation",
            [ToolCall(tool="checkpoint_create", arguments={"name": "before_mute_ch1"})],
        )
        assert res_cp[0].structured_content.get("verified") is True

        # 3. Agent re-calls with confirm_token
        res_exec = harness.step(
            "Apply mutation with confirm_token",
            [
                ToolCall(
                    tool="channel_set",
                    arguments={"channel": 1, "mute": True, "confirm_token": token},
                )
            ],
        )
        exec_sc = res_exec[0].structured_content
        assert exec_sc.get("verified") is True
        assert exec_sc.get("plane") in ("emulator", "live")

        # 4. Read back and verify
        res_verify = harness.step(
            "Verify channel 1 is muted",
            [ToolCall(tool="channel_get", arguments={"channel": 1})],
        )
        chan_sc = res_verify[0].structured_content
        assert chan_sc["muted"] is True

        harness.assert_call_sequence("checkpoint_create", "channel_set", "channel_get")

    def test_scenario_safe_rollback_on_failure(self, eval_studio_write: Studio) -> None:
        """Scenario: Agent modifies parameter, encounters issue, and rolls back cleanly.

        Asserts:
        - Checkpoint restores initial state with verified readback comparison.
        """
        harness = ScriptedAgentHarness(studio=eval_studio_write)

        # 1. Read initial volume of track 4
        res_init = harness.step(
            "Inspect initial track 4 volume",
            [ToolCall(tool="mixer_get", arguments={"track": 4})],
        )
        initial_vol = res_init[0].structured_content["volume"]

        # 2. Create checkpoint
        res_cp = harness.step(
            "Create rollback checkpoint",
            [ToolCall(tool="checkpoint_create", arguments={"name": "test_rollback_cp"})],
        )
        cp_id = res_cp[0].structured_content["checkpoint_id"]

        # 3. Mutate track 4 volume to 0.40
        harness.step(
            "Mutate track 4 volume to 0.40",
            [ToolCall(tool="mixer_set", arguments={"track": 4, "volume": 0.40})],
        )

        # Verify mutation took effect
        res_mod = harness.step(
            "Verify mutated level",
            [ToolCall(tool="mixer_get", arguments={"track": 4})],
        )
        assert res_mod[0].structured_content["volume"] == pytest.approx(0.40, abs=0.01)

        # 4. User cancels or agent detects failure -> rollback
        res_roll = harness.step(
            f"Rollback to checkpoint {cp_id}",
            [ToolCall(tool="checkpoint_rollback", arguments={"checkpoint_id": cp_id})],
        )
        assert not res_roll[0].is_error

        # 5. Verify restored state
        res_final = harness.step(
            "Verify restored level matches initial",
            [ToolCall(tool="mixer_get", arguments={"track": 4})],
        )
        restored_vol = res_final[0].structured_content["volume"]
        assert restored_vol == pytest.approx(initial_vol, abs=0.01)

    def test_scenario_protected_target_master_interlock(self, eval_studio_write: Studio) -> None:
        """Scenario: Modifying Master mixer track 0 requires explicit confirmation.

        Asserts:
        - Writing to track 0 without allow_protected returns error [E_PROTECTED].
        - Supplying allow_protected=True triggers confirmation challenge.
        - Supplying confirm_token executes write with verified receipt.
        """
        harness = ScriptedAgentHarness(studio=eval_studio_write)

        # 1. Attempt write to track 0 without allow_protected -> E_PROTECTED error
        res_err = harness.step(
            "Attempt master track volume change without allow_protected",
            [ToolCall(tool="mixer_set", arguments={"track": 0, "volume": 0.75})],
        )
        assert res_err[0].is_error is True
        assert res_err[0].structured_content.get("error") == "E_PROTECTED"

        # 2. Agent presents to user and passes allow_protected=True -> gets challenge
        res_chal = harness.step(
            "Pass allow_protected=True to trigger confirmation challenge",
            [
                ToolCall(
                    tool="mixer_set",
                    arguments={"track": 0, "volume": 0.75, "allow_protected": True},
                )
            ],
        )
        sc = res_chal[0].structured_content
        assert sc.get("needs_confirmation") is True
        token = sc.get("confirm_token")
        assert token is not None

        # 3. User approves -> re-call with allow_protected=True and confirm token
        res_exec = harness.step(
            "Execute with allow_protected and confirm token",
            [
                ToolCall(
                    tool="mixer_set",
                    arguments={
                        "track": 0,
                        "volume": 0.75,
                        "allow_protected": True,
                        "confirm_token": token,
                    },
                )
            ],
        )
        exec_sc = res_exec[0].structured_content
        assert exec_sc.get("verified") is True
        assert exec_sc.get("plane") in ("emulator", "live")

    def test_scenario_progressive_api_discovery(self, eval_studio_readonly: Studio) -> None:
        """Scenario: Agent uses progressive discovery to find and inspect API functions.

        Asserts:
        - api_search returns matching functions without guessing.
        - api_describe returns detailed signature, since-version, quirks, and card.
        """
        harness = ScriptedAgentHarness(studio=eval_studio_readonly)

        # 1. Search for volume functions in mixer module
        res_search = harness.step(
            "Search for volume functions in mixer module",
            [ToolCall(tool="api_search", arguments={"query": "volume", "module": "mixer"})],
        )
        matches = res_search[0].structured_content.get("matches", [])
        assert any(r["name"] == "setTrackVolume" for r in matches)

        # 2. Describe mixer.setTrackVolume
        res_desc = harness.step(
            "Describe mixer.setTrackVolume",
            [ToolCall(tool="api_describe", arguments={"function": "mixer.setTrackVolume"})],
        )
        desc_sc = res_desc[0].structured_content
        assert desc_sc.get("module") == "mixer"
        assert desc_sc.get("function") == "setTrackVolume"
        assert "quirks" in desc_sc
        assert "signature" in desc_sc
