"""Unit tests for control and safety CLI commands.

Verifies:
1. 'sbridge transport play|stop|record|tempo|pos'.
2. 'sbridge mixer set <track> [--vol/--pan/--mute/--solo/--name]'.
3. 'sbridge channels set <channel> [--vol/--pan/--name/--mute/--solo/--steps]'.
4. 'sbridge patterns select <n>' and 'sbridge patterns rename <n> <name>'.
5. 'sbridge safety mode|checkpoint|rollback|journal'.
6. 'sbridge call <module.fn> [args...]'.
7. 'sbridge batch <file.json>'.
8. Structured write receipts ({verified: bool, plane: str, journal_id: int}) and --json output.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Generator

import pytest

from studiobridge.cli.commands.control import set_default_client as set_control_client
from studiobridge.cli.commands.inspect import set_default_client as set_inspect_client
from studiobridge.cli.commands.safety import set_default_client as set_safety_client
from studiobridge.cli.main import cli_entry
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.client import Studio


@pytest.fixture(scope="module")
def cli_ctrl_secret() -> str:
    return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="module")
def cli_ctrl_emulator_bundle(
    tmp_path_factory: pytest.TempPathFactory, cli_ctrl_secret: str
) -> pathlib.Path:
    tmp_path = tmp_path_factory.mktemp("cli_ctrl_bundle")
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="0.3.2-cli",
        secret=cli_ctrl_secret,
    )
    gen.generate_multi_file(tmp_path)
    return tmp_path


@pytest.fixture
def cli_studio(
    cli_ctrl_emulator_bundle: pathlib.Path, cli_ctrl_secret: str
) -> Generator[Studio, None, None]:
    emulator = DeviceEmulator(
        script_dir=cli_ctrl_emulator_bundle, device_name="TestDevice", enforce_sandbox=False
    )
    emulator.start()

    port_sdk, port_device = FakeMidiPort.create_pair(
        name_a="CliCtrl Loopback (A)",
        name_b="CliCtrl Loopback (B)",
    )

    def on_device_sysex(data: bytes) -> None:
        emulator.send_sysex(data)
        for out_frame in emulator.get_sent_sysex():
            port_device.send_sysex(out_frame)
        emulator.clear_sent_sysex()

    port_device.on_sysex(on_device_sysex)

    with Studio.connect(embedded=True, port=port_sdk, secret=cli_ctrl_secret, mode="write") as fl:
        set_control_client(fl)
        set_safety_client(fl)
        set_inspect_client(fl)
        try:
            yield fl
        finally:
            set_control_client(None)
            set_safety_client(None)
            set_inspect_client(None)
            emulator.stop()


class TestTransportCliCommands:
    """Verifies 'sbridge transport' control commands."""

    def test_transport_play_and_stop_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge transport play and stop emit structured write receipts in --json mode."""
        code = cli_entry(["transport", "play", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True
        assert data["plane"] == "live"
        assert isinstance(data["journal_id"], int)
        assert data["action"] == "play"

        code = cli_entry(["transport", "stop", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data_stop = json.loads(out)
        assert data_stop["verified"] is True
        assert data_stop["action"] == "stop"

    def test_transport_record_and_pos(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge transport record and pos execute with human-readable output."""
        code = cli_entry(["transport", "record"])
        assert code == 0
        out, _ = capsys.readouterr()
        assert "Recording mode" in out
        assert "[verified=True, plane=live" in out

        code = cli_entry(["transport", "pos", "0.25", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True


class TestMixerAndChannelsCliCommands:
    """Verifies 'sbridge mixer set' and 'sbridge channels set'."""

    def test_mixer_set_json(self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge mixer set <track> --vol ... --pan ... --name ... emits receipt."""
        code = cli_entry(
            [
                "mixer",
                "set",
                "1",
                "--vol",
                "0.75",
                "--pan",
                "0.2",
                "--name",
                "Lead Vocal",
                "--json",
            ]
        )
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True
        assert data["plane"] == "live"
        assert isinstance(data["journal_id"], int)
        assert data["track_count"] == 1

    def test_channels_set_with_steps(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge channels set modifies volume, pan, and 16-step grid."""
        steps_arg = "1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0"
        code = cli_entry(
            [
                "channels",
                "set",
                "0",
                "--vol",
                "0.8",
                "--pan",
                "-0.1",
                "--name",
                "Kick",
                "--steps",
                steps_arg,
                "--json",
            ]
        )
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True
        assert data["channel"] == 0
        assert isinstance(data["journal_id"], int)


class TestPatternsAndSafetyCliCommands:
    """Verifies 'sbridge patterns', 'sbridge safety', 'sbridge call', 'sbridge batch'."""

    def test_patterns_select_and_rename(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge patterns select and rename."""
        code = cli_entry(["patterns", "rename", "1", "Chorus Hook", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True
        assert data["pattern"] == 1
        assert data["action"] == "rename"

        code = cli_entry(["patterns", "select", "1", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data_sel = json.loads(out)
        assert data_sel["verified"] is True

    def test_safety_checkpoint_and_rollback(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge safety checkpoint and rollback."""
        # 1. Create checkpoint
        code = cli_entry(["safety", "checkpoint", "pre_drop", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data_cp = json.loads(out)
        assert data_cp["verified"] is True
        cp_id = data_cp["checkpoint_id"]

        # 2. Mutate state
        cli_entry(["mixer", "set", "1", "--vol", "0.3"])
        capsys.readouterr()  # clear buffer

        # 3. Rollback
        code = cli_entry(["safety", "rollback", cp_id, "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data_rb = json.loads(out)
        assert data_rb["verified"] is True
        assert data_rb["restored_count"] >= 1

    def test_safety_journal(self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge safety journal lists entries in --json mode."""
        # Ensure there is at least one mutation entry
        cli_entry(["transport", "play"])
        capsys.readouterr()  # clear buffer

        code = cli_entry(["safety", "journal", "--limit", "10", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert "entries" in data
        assert data["count"] >= 1

    def test_call_raw_api(self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge call invokes allowlisted function."""
        code = cli_entry(["call", "mixer.getTrackVolume", "index=0", "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["verified"] is True
        assert data["function"] == "mixer.getTrackVolume"
        assert "result" in data

    def test_batch_execution_with_rollback_on_error(
        self, cli_studio: Studio, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge batch applies mutations and rolls back cleanly on error."""
        batch_file = tmp_path / "test_batch.json"
        # 1. Successful batch
        batch_data = [
            {"op": "mixer.setTrackVolume", "args": {"index": 1, "volume": 0.7}},
            {"op": "mixer.setTrackPan", "args": {"index": 1, "pan": 0.2}},
        ]
        batch_file.write_text(json.dumps(batch_data), encoding="utf-8")

        code = cli_entry(["batch", str(batch_file), "--json"])
        assert code == 0
        out, _ = capsys.readouterr()
        data = json.loads(out)
        assert data["status"] == "ok"
        assert data["operations_count"] == 2

        # 2. Batch with invalid operation triggers rollback
        failing_batch = [
            {"op": "mixer.setTrackVolume", "args": {"index": 1, "volume": 0.5}},
            {"op": "nonexistent.function", "args": {}},
        ]
        batch_file.write_text(json.dumps(failing_batch), encoding="utf-8")

        code_fail = cli_entry(["batch", str(batch_file), "--json"])
        assert code_fail == 1
        out_fail, _ = capsys.readouterr()
        data_fail = json.loads(out_fail)
        assert data_fail["status"] == "error"
        assert data_fail["rolled_back"] is True
