"""Unit tests for StudioBridge configuration structures and layered resolution.

# req: CFG-01
"""

from __future__ import annotations

from pathlib import Path

from studiobridge.core.config import (
    BrokerConfig,
    PortConfig,
    SafetyConfig,
    StudioBridgeConfig,
    load_config,
    save_config,
    to_dict,
)


def test_default_config_values():
    """Verify standard default configuration values.

    # req: CFG-01
    """
    cfg = StudioBridgeConfig()
    assert cfg.port.name == "SBridge"
    assert cfg.port.backend == "auto"
    assert cfg.port.buffer_size == 4096
    assert cfg.port.chunk_delay_ms == 2.0

    assert cfg.broker.host == "127.0.0.1"
    assert cfg.broker.port == 8123
    assert cfg.broker.token is None
    assert cfg.broker.lease_ttl_sec == 15.0
    assert cfg.broker.idle_budget_ms == 8.0
    assert cfg.broker.request_timeout_sec == 5.0

    assert cfg.safety.mode == "read_only"
    assert cfg.safety.confirm_mutations is True
    assert cfg.safety.max_batch_size == 500
    assert cfg.safety.tolerance == 0.005

    assert cfg.log_level == "INFO"
    assert "core" in cfg.toolsets
    assert "render" in cfg.toolsets


def test_user_config_overrides_defaults(tmp_path: Path):
    """Verify user config (%LOCALAPPDATA%\\studiobridge\\config.toml) overrides defaults.

    # req: CFG-01
    """
    user_cfg_file = tmp_path / "config.toml"
    user_cfg_file.write_text(
        """
        log_level = "DEBUG"
        toolsets = ["core", "inspect"]

        [port]
        name = "UserMidiPort"
        buffer_size = 8192

        [broker]
        port = 9000

        [safety]
        mode = "write"
        confirm_mutations = false
        """,
        encoding="utf-8",
    )

    cfg = load_config(user_config_path=user_cfg_file, env={}, project_dir=tmp_path / "empty")
    assert cfg.log_level == "DEBUG"
    assert cfg.toolsets == ["core", "inspect"]
    assert cfg.port.name == "UserMidiPort"
    assert cfg.port.buffer_size == 8192
    assert cfg.broker.port == 9000
    assert cfg.safety.mode == "write"
    assert cfg.safety.confirm_mutations is False

    # Non-overridden values remain defaults
    assert cfg.broker.host == "127.0.0.1"
    assert cfg.port.backend == "auto"


def test_project_config_overrides_user_config(tmp_path: Path):
    """Verify local project .sbridge.toml overrides user config.

    # req: CFG-01
    """
    user_cfg_file = tmp_path / "user_config.toml"
    user_cfg_file.write_text(
        """
        [port]
        name = "UserPort"

        [safety]
        mode = "write"
        """,
        encoding="utf-8",
    )

    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()
    proj_cfg_file = proj_dir / ".sbridge.toml"
    proj_cfg_file.write_text(
        """
        [port]
        name = "ProjectPort"

        [safety]
        mode = "destructive"
        tolerance = 0.001
        """,
        encoding="utf-8",
    )

    cfg = load_config(user_config_path=user_cfg_file, project_dir=proj_dir, env={})
    assert cfg.port.name == "ProjectPort"
    assert cfg.safety.mode == "destructive"
    assert cfg.safety.tolerance == 0.001


def test_environment_variables_override_project_config(tmp_path: Path):
    """Verify SBRIDGE_* environment variables override project .sbridge.toml.

    # req: CFG-01
    """
    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()
    (proj_dir / ".sbridge.toml").write_text(
        """
        [port]
        name = "ProjectPort"
        backend = "wms"

        [broker]
        port = 8123

        [safety]
        mode = "read_only"
        """,
        encoding="utf-8",
    )

    env = {
        "SBRIDGE_PORT_NAME": "EnvPort",
        "SBRIDGE_PORT_BACKEND": "winmm",
        "SBRIDGE_BROKER_PORT": "9999",
        "SBRIDGE_MODE": "write",
        "SBRIDGE_LOG_LEVEL": "WARNING",
        "SBRIDGE_TOOLSETS": "core,control,render",
        "SBRIDGE_SAFETY_CONFIRM": "false",
        "SBRIDGE_SAFETY_MAX_BATCH": "100",
        "SBRIDGE_SAFETY_PROTECTED": "Master,Current",
    }

    cfg = load_config(project_dir=proj_dir, env=env)
    assert cfg.port.name == "EnvPort"
    assert cfg.port.backend == "winmm"
    assert cfg.broker.port == 9999
    assert cfg.safety.mode == "write"
    assert cfg.log_level == "WARNING"
    assert cfg.toolsets == ["core", "control", "render"]
    assert cfg.safety.confirm_mutations is False
    assert cfg.safety.max_batch_size == 100
    assert cfg.safety.protected_targets == ["Master", "Current"]


def test_cli_overrides_everything(tmp_path: Path):
    """Verify CLI overrides take highest precedence over Env, Project, User, and Defaults.

    # req: CFG-01
    """
    user_cfg = tmp_path / "user.toml"
    user_cfg.write_text('[port]\nname = "UserPort"\n[safety]\nmode = "read_only"', encoding="utf-8")

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / ".sbridge.toml").write_text(
        '[port]\nname = "ProjPort"\n[safety]\nmode = "write"', encoding="utf-8"
    )

    env = {
        "SBRIDGE_PORT_NAME": "EnvPort",
        "SBRIDGE_MODE": "write",
        "SBRIDGE_LOG_LEVEL": "DEBUG",
    }

    cli = {
        "port.name": "CliPort",
        "mode": "destructive",
        "log_level": "ERROR",
        "broker": {"port": 12345},
    }

    cfg = load_config(
        cli_overrides=cli,
        project_dir=proj_dir,
        user_config_path=user_cfg,
        env=env,
    )

    # CLI strictly wins
    assert cfg.port.name == "CliPort"
    assert cfg.safety.mode == "destructive"
    assert cfg.log_level == "ERROR"
    assert cfg.broker.port == 12345


def test_save_and_reload_config_roundtrip(tmp_path: Path):
    """Verify save_config writes valid TOML that can be reloaded without loss.

    # req: CFG-01
    """
    out_file = tmp_path / "saved_config.toml"
    orig = StudioBridgeConfig(
        port=PortConfig(name="CustomPort", backend="wms", buffer_size=8192),
        broker=BrokerConfig(port=9123, lease_ttl_sec=30.0),
        safety=SafetyConfig(mode="write", protected_targets=["Track 1", "Master"]),
        log_level="DEBUG",
        toolsets=["core", "inspect"],
        fl_user_dir=tmp_path / "fl_user",
    )

    save_config(orig, out_file)
    assert out_file.exists()

    loaded = load_config(user_config_path=out_file, env={}, project_dir=tmp_path / "empty")
    assert loaded.port.name == "CustomPort"
    assert loaded.port.backend == "wms"
    assert loaded.port.buffer_size == 8192
    assert loaded.broker.port == 9123
    assert loaded.broker.lease_ttl_sec == 30.0
    assert loaded.safety.mode == "write"
    assert loaded.safety.protected_targets == ["Track 1", "Master"]
    assert loaded.log_level == "DEBUG"
    assert loaded.toolsets == ["core", "inspect"]
    assert loaded.fl_user_dir == tmp_path / "fl_user"


def test_to_dict_serialization():
    """Verify to_dict produces JSON/serializable dictionary.

    # req: CFG-01
    """
    cfg = StudioBridgeConfig(log_dir=Path("/var/log/sbridge"))
    d = to_dict(cfg)
    assert isinstance(d, dict)
    assert d["port"]["name"] == "SBridge"
    assert d["broker"]["port"] == 8123
    assert d["safety"]["mode"] == "read_only"
    assert d["log_dir"] == "/var/log/sbridge" or d["log_dir"] == "\\var\\log\\sbridge"


def test_corrupt_toml_file_handling(tmp_path: Path):
    """Verify corrupted TOML file fails gracefully and falls back to defaults.

    # req: CFG-01
    """
    corrupt_file = tmp_path / "corrupt.toml"
    corrupt_file.write_text("invalid_toml_syntax = [unclosed_bracket", encoding="utf-8")

    cfg = load_config(user_config_path=corrupt_file, env={}, project_dir=tmp_path / "empty")
    assert cfg.port.name == "SBridge"


def test_exhaustive_env_vars_and_invalid_numbers(tmp_path: Path):
    """Verify all SBRIDGE_* environment variables and resilient parsing of invalid numbers.

    # req: CFG-01
    """
    env = {
        "SBRIDGE_PORT_IN": "InPort",
        "SBRIDGE_PORT_OUT": "OutPort",
        "SBRIDGE_PORT_BUFFER_SIZE": "invalid_int",
        "SBRIDGE_PORT_CHUNK_DELAY_MS": "invalid_float",
        "SBRIDGE_BROKER_HOST": "192.168.1.50",
        "SBRIDGE_BROKER_PORT": "not_an_int",
        "SBRIDGE_BROKER_TOKEN": "token_abc_123",
        "SBRIDGE_LEASE_TTL": "invalid_ttl",
        "SBRIDGE_IDLE_BUDGET_MS": "16.5",
        "SBRIDGE_REQUEST_TIMEOUT": "8.5",
        "SBRIDGE_SAFETY_MODE": "write",
        "SBRIDGE_SAFETY_TOLERANCE": "0.002",
        "SBRIDGE_LOG_DIR": str(tmp_path / "logs"),
        "SBRIDGE_FL_USER_DIR": str(tmp_path / "user"),
        "SBRIDGE_FL_INSTALL_DIR": str(tmp_path / "install"),
    }

    cfg = load_config(env=env, project_dir=tmp_path / "empty")
    assert cfg.port.in_port_name == "InPort"
    assert cfg.port.out_port_name == "OutPort"
    assert cfg.port.buffer_size == 4096  # retained default due to ValueError
    assert cfg.port.chunk_delay_ms == 2.0  # retained default
    assert cfg.broker.host == "192.168.1.50"
    assert cfg.broker.port == 8123  # retained default
    assert cfg.broker.token == "token_abc_123"
    assert cfg.broker.lease_ttl_sec == 15.0  # retained default
    assert cfg.broker.idle_budget_ms == 16.5
    assert cfg.broker.request_timeout_sec == 8.5
    assert cfg.safety.mode == "write"
    assert cfg.safety.tolerance == 0.002
    assert cfg.log_dir == tmp_path / "logs"
    assert cfg.fl_user_dir == tmp_path / "user"
    assert cfg.fl_install_dir == tmp_path / "install"


def test_save_config_all_optional_fields(tmp_path: Path):
    """Verify save_config serializes all optional fields.

    # req: CFG-01
    """
    out_file = tmp_path / "full_config.toml"
    cfg = StudioBridgeConfig(
        port=PortConfig(in_port_name="InA", out_port_name="OutB"),
        broker=BrokerConfig(token="secret_token"),
        log_dir=tmp_path / "logs",
        fl_install_dir=tmp_path / "fl_install",
    )
    save_config(cfg, out_file)
    text = out_file.read_text(encoding="utf-8")
    assert 'in_port_name = "InA"' in text
    assert 'out_port_name = "OutB"' in text
    assert 'token = "secret_token"' in text
    assert "log_dir =" in text
    assert "fl_install_dir =" in text
