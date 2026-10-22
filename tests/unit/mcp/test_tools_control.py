"""Unit tests for StudioBridge control and safety MCP tools per 10_l2_interfaces.md §2.4.

Verifies:
1. Tool catalog, annotations, and token budget for all control and safety tools.
2. Mode interlocks: mutating calls in read-only mode prompt for mode change and confirmation.
3. Challenge token authorization unlocks queued writes.
4. Protected target interlocks for master track 0 and tempo.
5. Checkpoint creation and rollback returning modified states to prior recorded values.
6. Structured write receipts ({verified: bool, plane: str, journal_id: int}) on all mutating tools.
7. Schema validation against frozen JSON schemas.
"""

from __future__ import annotations

import pytest

from studiobridge.core.capabilities import CapabilityState
from studiobridge.core.errors import ProtectedTargetError
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.mcp.tools.control import ControlTools, get_control_tools, get_raw_tools
from studiobridge.mcp.tools.safety import SafetyTools, get_safety_tools
from studiobridge.sdk.client import Studio


class TestControlAndSafetyMetadata:
    """Verifies catalog, annotations, and token budget for control and safety tools."""

    def test_control_tools_catalog_and_annotations(self) -> None:
        """Control tools are defined with correct read_only=False and annotations."""
        tools = get_control_tools()
        assert len(tools) == 8
        names = {t.name for t in tools}
        expected = {
            "transport_control",
            "mixer_set",
            "channel_set",
            "plugin_param_set",
            "pattern_edit",
            "steps_set",
            "playlist_edit",
            "playlist_place_pattern",
        }
        assert names == expected

        for t in tools:
            assert t.toolset == "control"
            assert t.read_only is False
            assert t.title is not None
            mcp_dict = t.to_mcp_dict()
            assert mcp_dict["name"] == t.name
            assert mcp_dict["annotations"]["readOnlyHint"] is False

    def test_safety_and_raw_tools_catalog(self) -> None:
        """Safety tools and raw execution tool are defined with correct annotations."""
        safety_tools = get_safety_tools()
        assert len(safety_tools) == 4
        s_names = {t.name for t in safety_tools}
        assert s_names == {
            "studio_set_mode",
            "checkpoint_create",
            "checkpoint_rollback",
            "journal_list",
        }

        raw_tools = get_raw_tools()
        assert len(raw_tools) == 1
        assert raw_tools[0].name == "fl_call"
        assert raw_tools[0].toolset == "raw"

    def test_description_token_budget(self) -> None:
        """Every tool description is <= 250 tokens (~180 words)."""
        all_tools = get_control_tools() + get_safety_tools() + get_raw_tools()
        for t in all_tools:
            words = t.description.split()
            assert len(words) <= 100, (
                f"Tool {t.name} description exceeds budget: {len(words)} words"
            )


class TestControlToolsExecution:
    """Functional tests against DeviceEmulator."""

    def test_read_only_mode_prompts_for_confirmation(self, studio: Studio) -> None:
        """Control operations in read_only mode prompt for mode change and confirmation."""
        studio.safety.mode = "read_only"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # Mutating tool call in read_only mode
        res = tools.transport_control(action="play")
        sc = res.structured_content

        assert sc is not None
        assert sc.get("needs_confirmation") is True
        assert "challenge" in sc
        assert "confirm_token" in sc
        assert studio.safety.mode == "read_only"

    def test_challenge_token_authorizes_and_executes(self, studio: Studio) -> None:
        """Providing valid challenge token authorizes the write and switches mode to write."""
        studio.safety.mode = "read_only"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # 1. Trigger challenge
        challenge_res = tools.transport_control(action="play")
        token = challenge_res.structured_content["confirm_token"]

        # 2. Re-call with confirm_token
        exec_res = tools.transport_control(action="play", confirm_token=token)
        sc = exec_res.structured_content

        assert sc["verified"] is True
        assert sc["plane"] == "live"
        assert isinstance(sc["journal_id"], int)
        assert studio.safety.mode in ("write", "write_autonomous")

    def test_transport_control_play_stop_record(self, studio: Studio) -> None:
        """transport_control executes play, stop, record, seek with write receipts."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # Play
        res_play = tools.transport_control(action="play")
        assert res_play.structured_content["verified"] is True
        assert res_play.structured_content["plane"] == "live"
        assert isinstance(res_play.structured_content["journal_id"], int)

        # Stop
        res_stop = tools.transport_control(action="stop")
        assert res_stop.structured_content["verified"] is True

        # Record
        res_rec = tools.transport_control(action="record")
        assert res_rec.structured_content["verified"] is True

        # Seek position
        res_pos = tools.transport_control(action="pos", position=0.5)
        assert res_pos.structured_content["verified"] is True

    def test_transport_tempo_protected_target(self, studio: Studio) -> None:
        """Setting tempo targets protected parameter requiring confirmation."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # Without allow_protected: raises ProtectedTargetError
        with pytest.raises(ProtectedTargetError):
            tools.transport_control(action="tempo", tempo=135.0, allow_protected=False)

        # With allow_protected=True but without token: returns challenge
        res_chal = tools.transport_control(action="tempo", tempo=135.0, allow_protected=True)
        assert res_chal.structured_content["needs_confirmation"] is True
        token = res_chal.structured_content["confirm_token"]

        # With allow_protected=True and valid confirm_token: succeeds
        res_exec = tools.transport_control(
            action="tempo", tempo=135.0, allow_protected=True, confirm_token=token
        )
        assert res_exec.structured_content["verified"] is True
        assert res_exec.structured_content["plane"] == "live"

    def test_mixer_set_single_and_array(self, studio: Studio) -> None:
        """mixer_set adjusts volume, pan, mute, solo, name with structured receipts."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # Single track adjustment
        res_single = tools.mixer_set(track=1, volume=0.75, pan=0.1, name="Bass")
        sc = res_single.structured_content
        assert sc["verified"] is True
        assert sc["plane"] == "live"
        assert isinstance(sc["journal_id"], int)
        assert sc["track_count"] == 1

        # Array of track adjustments
        res_array = tools.mixer_set(
            tracks=[
                {"track": 2, "volume": 0.6, "mute": False},
                {"track": 3, "volume": 0.7, "solo": True},
            ]
        )
        sc_arr = res_array.structured_content
        assert sc_arr["verified"] is True
        assert sc_arr["track_count"] == 2
        assert len(sc_arr["receipts"]) == 2

    def test_mixer_set_master_track_protection(self, studio: Studio) -> None:
        """Track 0 (master track) is protected; requires allow_protected=True and confirmation."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # Blocked without allow_protected
        with pytest.raises(ProtectedTargetError):
            tools.mixer_set(track=0, volume=0.9, allow_protected=False)

        # Prompt with allow_protected=True
        chal = tools.mixer_set(track=0, volume=0.9, allow_protected=True)
        assert chal.structured_content["needs_confirmation"] is True
        token = chal.structured_content["confirm_token"]

        # Succeeded with confirm_token
        res = tools.mixer_set(track=0, volume=0.9, allow_protected=True, confirm_token=token)
        assert res.structured_content["verified"] is True

    def test_channel_set_and_steps_set(self, studio: Studio) -> None:
        """channel_set and steps_set modify channel rack and 16-step grid."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # channel_set
        res_chan = tools.channel_set(channel=0, volume=0.85, pan=-0.2, name="Lead Synth")
        sc = res_chan.structured_content
        assert sc["verified"] is True
        assert sc["plane"] == "live"
        assert isinstance(sc["journal_id"], int)

        # steps_set (16 steps)
        steps = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        res_steps = tools.steps_set(channel=0, steps=steps)
        sc_steps = res_steps.structured_content
        assert sc_steps["verified"] is True
        assert sc_steps["step_grid"] == steps

    def test_pattern_edit_and_playlist_edit(self, studio: Studio) -> None:
        """pattern_edit and playlist_edit execute modifications."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        # pattern_edit rename
        res_pat = tools.pattern_edit(pattern=1, action="rename", name="Intro Verse")
        assert res_pat.structured_content["verified"] is True
        assert res_pat.structured_content["pattern"] == 1

        # pattern_edit select
        res_sel = tools.pattern_edit(pattern=1, action="select")
        assert res_sel.structured_content["verified"] is True

        # playlist_edit
        res_play = tools.playlist_edit(track=1, name="Kick Track", mute=True)
        assert res_play.structured_content["verified"] is True
        assert res_play.structured_content["track"] == 1

        # playlist_place_pattern
        studio.caps.update("experimental.playlist_place", CapabilityState.AVAILABLE)
        res_place = tools.playlist_place_pattern(track=1, pattern=1, time=0.0)
        assert res_place.structured_content["verified"] is True

    def test_fl_call_raw_execution(self, studio: Studio) -> None:
        """fl_call executes allowlisted function with verification."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        tools = ControlTools(client=studio, server=server)

        res = tools.fl_call("mixer.getTrackVolume", {"index": 0})
        sc = res.structured_content
        assert sc["verified"] is True
        assert sc["plane"] == "live"
        assert "result" in sc


class TestSafetyToolsAndCheckpointRollback:
    """Verifies mode switching, checkpoint creation, and rollback guarantees."""

    def test_studio_set_mode_requires_confirmation_for_write(self, studio: Studio) -> None:
        """studio_set_mode to 'write' requires human confirmation."""
        studio.safety.mode = "read_only"
        server = StudioMcpServer(client=studio)
        safety = SafetyTools(client=studio, server=server)

        # 1. Without token: returns challenge
        chal = safety.studio_set_mode(mode="write", reason="Starting mixdown")
        sc = chal.structured_content
        assert sc["needs_confirmation"] is True
        token = sc["confirm_token"]
        assert studio.safety.mode == "read_only"

        # 2. With token: switches mode
        res = safety.studio_set_mode(mode="write", confirm_token=token)
        assert res.structured_content["status"] == "ok"
        assert res.structured_content["mode"] == "write"
        assert studio.safety.mode in ("write", "write_autonomous")

        # 3. Switching back to read_only is safe without token
        res_ro = safety.studio_set_mode(mode="read_only")
        assert res_ro.structured_content["mode"] == "read_only"
        assert studio.safety.mode == "read_only"

    def test_checkpoint_rollback_restores_mixer_and_channel_states(self, studio: Studio) -> None:
        """Checkpoint rollback restores modified states to prior recorded values."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        control = ControlTools(client=studio, server=server)
        safety = SafetyTools(client=studio, server=server)

        # Initial baseline states
        studio.mixer.set_volume(1, 0.8)
        studio.mixer.set_pan(1, 0.0)
        studio.channels.set_volume(0, 0.75)

        initial_mix_vol = studio.mixer.get_volume(1)
        initial_chan_vol = studio.channels.get_volume(0)

        # 1. Create named checkpoint
        cp_res = safety.checkpoint_create(name="mix_baseline")
        cp_id = cp_res.structured_content["checkpoint_id"]
        assert cp_id is not None

        # 2. Mutate mixer and channels
        control.mixer_set(track=1, volume=0.35, pan=-0.5)
        control.channel_set(channel=0, volume=0.2)

        # Assert values changed
        assert abs(studio.mixer.get_volume(1) - 0.35) < 0.05
        assert abs(studio.channels.get_volume(0) - 0.2) < 0.05

        # 3. Rollback to checkpoint
        rb_res = safety.checkpoint_rollback(checkpoint_id=cp_id)
        sc_rb = rb_res.structured_content
        assert sc_rb["verified"] is True
        assert sc_rb["guarantee"] in ("verified", "best_effort")
        assert sc_rb["restored_count"] >= 2

        # 4. Assert mixer and channel restored to initial recorded values
        restored_mix_vol = studio.mixer.get_volume(1)
        restored_chan_vol = studio.channels.get_volume(0)
        assert abs(restored_mix_vol - initial_mix_vol) < 0.05
        assert abs(restored_chan_vol - initial_chan_vol) < 0.05

    def test_journal_list(self, studio: Studio) -> None:
        """journal_list retrieves recent audit journal entries."""
        studio.safety.mode = "write"
        server = StudioMcpServer(client=studio)
        control = ControlTools(client=studio, server=server)
        safety = SafetyTools(client=studio, server=server)

        control.transport_control(action="play")
        res = safety.journal_list(limit=10)
        sc = res.structured_content
        assert sc["count"] >= 1
        assert len(sc["entries"]) >= 1


class TestControlToolsSchemaConformity:
    """Verifies all control, safety, and raw tools adhere to frozen JSON schemas."""

    def test_all_13_schemas_exist_and_validate(self) -> None:
        """All 13 new tool schemas can be loaded and validated."""
        schema_names = [
            "transport_control",
            "mixer_set",
            "channel_set",
            "plugin_param_set",
            "pattern_edit",
            "steps_set",
            "playlist_edit",
            "playlist_place_pattern",
            "fl_call",
            "studio_set_mode",
            "checkpoint_create",
            "checkpoint_rollback",
            "journal_list",
        ]
        for name in schema_names:
            schema = get_schema(name)
            assert schema["name"] == name
            assert "inputSchema" in schema
            assert "outputSchema" in schema
            assert schema["inputSchema"]["type"] == "object"
