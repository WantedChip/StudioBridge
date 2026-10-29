"""Unit tests for inspection CLI commands.

Verifies:
1. 'sbridge api search <query>', 'sbridge api describe <fn>', 'sbridge api list [module]',
   and 'sbridge api export'.
2. 'sbridge transport get', 'sbridge mixer list', 'sbridge mixer get <track>',
   'sbridge channels list', 'sbridge channels get <channel>', and 'sbridge patterns list'.
3. Human-readable and machine-readable '--json' output modes.
4. Conformance of '--json' outputs against frozen MCP tool JSON schemas.
"""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest

from studiobridge.cli.commands.inspect import set_default_client
from studiobridge.cli.main import cli_entry
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.mcp.schemas import get_schema, validate_schema
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.client import Studio


@pytest.fixture(scope="module")
def cli_secret() -> str:
    return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="module")
def cli_emulator_bundle(tmp_path_factory: pytest.TempPathFactory, cli_secret: str):
    tmp_path = tmp_path_factory.mktemp("cli_emulator_bundle")
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="0.3.1-cli",
        secret=cli_secret,
    )
    gen.generate_multi_file(tmp_path)
    return tmp_path


@pytest.fixture
def cli_studio(cli_emulator_bundle, cli_secret: str) -> Generator[Studio, None, None]:
    emulator = DeviceEmulator(
        script_dir=cli_emulator_bundle, device_name="TestDevice", enforce_sandbox=False
    )
    emulator.start()

    port_sdk, port_device = FakeMidiPort.create_pair(
        name_a="CliTest Loopback (A)",
        name_b="CliTest Loopback (B)",
    )

    def on_device_sysex(data: bytes) -> None:
        emulator.send_sysex(data)
        for out_frame in emulator.get_sent_sysex():
            port_device.send_sysex(out_frame)
        emulator.clear_sent_sysex()

    port_device.on_sysex(on_device_sysex)

    with Studio.connect(embedded=True, port=port_sdk, secret=cli_secret, mode="write") as fl:
        set_default_client(fl)
        yield fl
        set_default_client(None)

    emulator.stop()


class TestApiCommands:
    """Tests for 'sbridge api' subcommands."""

    def test_api_search_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "search", "volume"])
        assert code == 0
        captured = capsys.readouterr().out
        assert "API Search Results" in captured
        assert "mixer.setTrackVolume" in captured

    def test_api_search_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "search", "volume", "--json"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["total"] >= 4

        schema = get_schema("api_search")
        validate_schema(data, schema["outputSchema"])

    def test_api_describe_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "describe", "mixer.setTrackVolume"])
        assert code == 0
        captured = capsys.readouterr().out
        assert "mixer.setTrackVolume" in captured
        assert "Signature:" in captured
        assert "Parameters:" in captured

    def test_api_describe_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "describe", "mixer.setTrackVolume", "--json"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["module"] == "mixer"
        assert data["function"] == "setTrackVolume"

        schema = get_schema("api_describe")
        validate_schema(data, schema["outputSchema"])

    def test_api_list_modules(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "list", "--json"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert "modules" in data
        assert data["total"] > 5

    def test_api_list_module_functions(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "list", "mixer", "--json"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["module"] == "mixer"
        assert "setTrackVolume" in data["functions"]

    def test_api_export_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_entry(["api", "export", "--format", "json", "--json"])
        assert code == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["status"] == "ok"
        assert data["format"] == "json"


class TestInspectCommandsWithClient:
    """Tests for live inspection commands against connected Studio client."""

    def test_transport_get_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["transport", "get"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "FL Studio Transport Status:" in text_out
        assert "Tempo:" in text_out

        # 2. JSON mode
        code_json = cli_entry(["transport", "get", "--json"])
        assert code_json == 0
        json_out = capsys.readouterr().out
        data = json.loads(json_out)
        assert isinstance(data["tempo"], float)
        assert isinstance(data["is_playing"], bool)

        schema = get_schema("transport_get")
        validate_schema(data, schema["outputSchema"])

    def test_mixer_list_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["mixer", "list", "--limit", "10"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "Mixer Tracks" in text_out
        assert "Master" in text_out

        # 2. JSON mode
        code_json = cli_entry(["mixer", "list", "--limit", "10", "--json"])
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["tracks"]) == 10
        assert data["total"] >= 16

        schema = get_schema("mixer_list")
        validate_schema(data, schema["outputSchema"])

    def test_mixer_get_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["mixer", "get", "0"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "Mixer Track 0: 'Master'" in text_out

        # 2. JSON mode
        code_json = cli_entry(["mixer", "get", "0", "--json"])
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert data["index"] == 0
        assert data["name"] == "Master"
        assert "volume_db" in data

        schema = get_schema("mixer_get")
        validate_schema(data, schema["outputSchema"])

    def test_channels_list_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["channels", "list"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "Channels" in text_out

        # 2. JSON mode
        code_json = cli_entry(["channels", "list", "--json"])
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert "channels" in data
        assert isinstance(data["total"], int)

        schema = get_schema("channels_list")
        validate_schema(data, schema["outputSchema"])

    def test_channels_get_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["channels", "get", "0"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "Channel 0:" in text_out

        # 2. JSON mode
        code_json = cli_entry(["channels", "get", "0", "--json"])
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert data["index"] == 0
        assert "volume" in data
        assert "step_bits" in data

        schema = get_schema("channel_get")
        validate_schema(data, schema["outputSchema"])

    def test_patterns_list_text_and_json(
        self, cli_studio: Studio, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 1. Text mode
        code_text = cli_entry(["patterns", "list"])
        assert code_text == 0
        text_out = capsys.readouterr().out
        assert "Patterns" in text_out

        # 2. JSON mode
        code_json = cli_entry(["patterns", "list", "--json"])
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert "patterns" in data
        assert isinstance(data["active_pattern"], int)

        schema = get_schema("patterns_list")
        validate_schema(data, schema["outputSchema"])
