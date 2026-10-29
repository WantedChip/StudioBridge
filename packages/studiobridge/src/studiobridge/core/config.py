"""Typed configuration structures and layered resolution pipeline.

Precedence order (highest to lowest):
CLI overrides > Environment variables (SBRIDGE_*) > Project config (.sbridge.toml)
> User config (%LOCALAPPDATA%\\studiobridge\\config.toml) > Hardcoded defaults.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.core.paths import get_config_path

# Fallback for tomllib across Python 3.10 and 3.11+
try:
    import tomllib
except ImportError:
    import tomlkit as tomllib


@dataclass(slots=True)
class PortConfig:
    """MIDI port configuration for device communication."""

    name: str = "SBridge"
    backend: str = "auto"  # "auto", "wms", "winmm", "rtmidi", "fake"
    in_port_name: str | None = None
    out_port_name: str | None = None
    buffer_size: int = 4096
    chunk_delay_ms: float = 2.0


@dataclass(slots=True)
class BrokerConfig:
    """Broker daemon host, port, lease and scheduling configuration."""

    host: str = "127.0.0.1"
    port: int = 8123
    token: str | None = None
    lease_ttl_sec: float = 15.0
    idle_budget_ms: float = 8.0
    request_timeout_sec: float = 5.0


@dataclass(slots=True)
class SafetyConfig:
    """Session safety mode, mutation limits, and target protections."""

    mode: str = "read_only"  # "read_only", "write", "destructive"
    protected_targets: list[str] = field(default_factory=list)
    confirm_mutations: bool = True
    max_batch_size: int = 500
    tolerance: float = 0.005


@dataclass(slots=True)
class ActuationConfig:
    """UI actuation, keystroke injection, and focus guard configuration [ACT-10, ACT-11]."""

    enabled: bool = False  # [ACT-11]: default false for general actuation
    piano_roll_enabled: bool = True  # [ACT-11]: default true for piano-roll keystrokes (Ctrl+Alt+Y)
    allow_focus_steal: bool = False  # [ACT-10]: whether to temporarily steal and restore focus
    user_idle_threshold_ms: float = 1000.0  # [ACT-10]: idle threshold before refusing actuation
    key_delay_ms: float = 15.0  # 10-20 ms delay between modifier and key events


@dataclass(slots=True)
class RenderConfig:
    """Headless render orchestration configuration."""

    timeout_s: float = 900.0  # total render timeout in seconds
    idle_timeout_s: float = 120.0  # idle timeout in seconds (no file growth)
    timeout_multiplier: float = 1.5  # scaling factor on Windows ARM64 (Prism emulation)
    default_format: str = "wav"
    default_policy: str = "require_closed"
    min_disk_free_multiplier: float = 2.0  # [RND-01]: disk space must be >= 2x estimated output


@dataclass(slots=True)
class StudioBridgeConfig:
    """Unified StudioBridge root configuration."""

    port: PortConfig = field(default_factory=PortConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    actuation: ActuationConfig = field(default_factory=ActuationConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    toolsets: list[str] = field(
        default_factory=lambda: [
            "core",
            "inspect",
            "control",
            "notes",
            "safety",
            "render",
        ]
    )
    log_level: str = "INFO"
    log_dir: Path | None = None
    fl_user_dir: Path | None = None
    fl_install_dir: Path | None = None


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge source dictionary into target dictionary."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def _unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert dotted keys (e.g. 'safety.mode') into nested dictionaries."""
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return nested


def _read_toml_file(path: Path) -> dict[str, Any]:
    """Safely parse a TOML file if it exists, returning empty dict on failure or absence."""
    if not path.is_file():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
            return dict(data)
    except Exception:
        return {}


def _parse_env_vars(env: Mapping[str, str]) -> dict[str, Any]:
    """Extract and map SBRIDGE_* environment variables into a nested config dict."""
    extracted: dict[str, Any] = {}

    def _set_nested(keys: list[str], val: Any) -> None:
        curr = extracted
        for k in keys[:-1]:
            curr = curr.setdefault(k, {})
        curr[keys[-1]] = val

    for key, value in env.items():
        if not key.startswith("SBRIDGE_"):
            continue

        var = key[len("SBRIDGE_") :]
        val_str = value.strip()

        # Direct explicit environment variable mappings
        if var == "MODE":
            _set_nested(["safety", "mode"], val_str)
        elif var == "LOG_LEVEL":
            extracted["log_level"] = val_str
        elif var == "TOOLSETS":
            extracted["toolsets"] = [t.strip() for t in val_str.split(",") if t.strip()]
        elif var == "LOG_DIR":
            extracted["log_dir"] = Path(val_str)
        elif var == "FL_USER_DIR":
            extracted["fl_user_dir"] = Path(val_str)
        elif var == "FL_INSTALL_DIR":
            extracted["fl_install_dir"] = Path(val_str)
        elif var == "PORT_NAME":
            _set_nested(["port", "name"], val_str)
        elif var == "PORT_BACKEND":
            _set_nested(["port", "backend"], val_str)
        elif var == "PORT_IN":
            _set_nested(["port", "in_port_name"], val_str)
        elif var == "PORT_OUT":
            _set_nested(["port", "out_port_name"], val_str)
        elif var == "PORT_BUFFER_SIZE":
            with contextlib.suppress(ValueError):
                _set_nested(["port", "buffer_size"], int(val_str))
        elif var == "PORT_CHUNK_DELAY_MS":
            with contextlib.suppress(ValueError):
                _set_nested(["port", "chunk_delay_ms"], float(val_str))
        elif var == "BROKER_HOST":
            _set_nested(["broker", "host"], val_str)
        elif var == "BROKER_PORT":
            with contextlib.suppress(ValueError):
                _set_nested(["broker", "port"], int(val_str))
        elif var == "BROKER_TOKEN":
            _set_nested(["broker", "token"], val_str)
        elif var == "LEASE_TTL" or var == "LEASE_TTL_SEC":
            with contextlib.suppress(ValueError):
                _set_nested(["broker", "lease_ttl_sec"], float(val_str))
        elif var == "IDLE_BUDGET_MS":
            with contextlib.suppress(ValueError):
                _set_nested(["broker", "idle_budget_ms"], float(val_str))
        elif var == "REQUEST_TIMEOUT" or var == "REQUEST_TIMEOUT_SEC":
            with contextlib.suppress(ValueError):
                _set_nested(["broker", "request_timeout_sec"], float(val_str))
        elif var == "SAFETY_MODE":
            _set_nested(["safety", "mode"], val_str)
        elif var == "SAFETY_CONFIRM":
            _set_nested(
                ["safety", "confirm_mutations"],
                val_str.lower() in ("true", "1", "yes"),
            )
        elif var == "SAFETY_MAX_BATCH":
            with contextlib.suppress(ValueError):
                _set_nested(["safety", "max_batch_size"], int(val_str))
        elif var == "SAFETY_TOLERANCE":
            with contextlib.suppress(ValueError):
                _set_nested(["safety", "tolerance"], float(val_str))
        elif var == "SAFETY_PROTECTED":
            _set_nested(
                ["safety", "protected_targets"],
                [t.strip() for t in val_str.split(",") if t.strip()],
            )
        elif var == "ACTUATION_ENABLED":
            _set_nested(
                ["actuation", "enabled"],
                val_str.lower() in ("true", "1", "yes"),
            )
        elif var == "ACTUATION_PIANO_ROLL_ENABLED":
            _set_nested(
                ["actuation", "piano_roll_enabled"],
                val_str.lower() in ("true", "1", "yes"),
            )
        elif var == "ACTUATION_ALLOW_FOCUS_STEAL":
            _set_nested(
                ["actuation", "allow_focus_steal"],
                val_str.lower() in ("true", "1", "yes"),
            )
        elif var in ("ACTUATION_IDLE_THRESHOLD", "ACTUATION_IDLE_THRESHOLD_MS"):
            with contextlib.suppress(ValueError):
                _set_nested(["actuation", "user_idle_threshold_ms"], float(val_str))
        elif var in ("ACTUATION_KEY_DELAY", "ACTUATION_KEY_DELAY_MS"):
            with contextlib.suppress(ValueError):
                _set_nested(["actuation", "key_delay_ms"], float(val_str))

    return extracted


def config_from_dict(data: dict[str, Any]) -> StudioBridgeConfig:
    """Construct a StudioBridgeConfig dataclass instance from a dictionary."""
    port_data = data.get("port", {})
    port_cfg = PortConfig(
        name=port_data.get("name", "SBridge"),
        backend=port_data.get("backend", "auto"),
        in_port_name=port_data.get("in_port_name"),
        out_port_name=port_data.get("out_port_name"),
        buffer_size=int(port_data.get("buffer_size", 4096)),
        chunk_delay_ms=float(port_data.get("chunk_delay_ms", 2.0)),
    )

    broker_data = data.get("broker", {})
    broker_cfg = BrokerConfig(
        host=broker_data.get("host", "127.0.0.1"),
        port=int(broker_data.get("port", 8123)),
        token=broker_data.get("token"),
        lease_ttl_sec=float(broker_data.get("lease_ttl_sec", 15.0)),
        idle_budget_ms=float(broker_data.get("idle_budget_ms", 8.0)),
        request_timeout_sec=float(broker_data.get("request_timeout_sec", 5.0)),
    )

    safety_data = data.get("safety", {})
    protected = safety_data.get("protected_targets", [])
    safety_cfg = SafetyConfig(
        mode=safety_data.get("mode", "read_only"),
        protected_targets=list(protected) if isinstance(protected, list) else [],
        confirm_mutations=bool(safety_data.get("confirm_mutations", True)),
        max_batch_size=int(safety_data.get("max_batch_size", 500)),
        tolerance=float(safety_data.get("tolerance", 0.005)),
    )

    actuation_data = data.get("actuation", {})
    actuation_cfg = ActuationConfig(
        enabled=bool(actuation_data.get("enabled", False)),
        piano_roll_enabled=bool(actuation_data.get("piano_roll_enabled", True)),
        allow_focus_steal=bool(actuation_data.get("allow_focus_steal", False)),
        user_idle_threshold_ms=float(actuation_data.get("user_idle_threshold_ms", 1000.0)),
        key_delay_ms=float(actuation_data.get("key_delay_ms", 15.0)),
    )

    render_data = data.get("render", {})
    render_cfg = RenderConfig(
        timeout_s=float(render_data.get("timeout_s", 900.0)),
        idle_timeout_s=float(render_data.get("idle_timeout_s", 120.0)),
        timeout_multiplier=float(render_data.get("timeout_multiplier", 1.5)),
        default_format=str(render_data.get("default_format", "wav")),
        default_policy=str(render_data.get("default_policy", "require_closed")),
        min_disk_free_multiplier=float(render_data.get("min_disk_free_multiplier", 2.0)),
    )

    toolsets = data.get("toolsets", ["core", "inspect", "control", "notes", "safety", "render"])
    log_dir_raw = data.get("log_dir")
    fl_user_dir_raw = data.get("fl_user_dir")
    fl_install_dir_raw = data.get("fl_install_dir")

    return StudioBridgeConfig(
        port=port_cfg,
        broker=broker_cfg,
        safety=safety_cfg,
        actuation=actuation_cfg,
        render=render_cfg,
        toolsets=list(toolsets) if isinstance(toolsets, list) else [],
        log_level=str(data.get("log_level", "INFO")),
        log_dir=Path(log_dir_raw) if log_dir_raw else None,
        fl_user_dir=Path(fl_user_dir_raw) if fl_user_dir_raw else None,
        fl_install_dir=Path(fl_install_dir_raw) if fl_install_dir_raw else None,
    )


def to_dict(config: StudioBridgeConfig) -> dict[str, Any]:
    """Convert StudioBridgeConfig to a serializable dictionary."""
    raw = asdict(config)
    # Convert Path objects to strings
    for k in ("log_dir", "fl_user_dir", "fl_install_dir"):
        if raw.get(k) is not None:
            raw[k] = str(raw[k])
    return raw


def save_config(config: StudioBridgeConfig, path: Path) -> None:
    """Save configuration to a TOML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f'log_level = "{config.log_level}"',
        f"toolsets = {config.toolsets!r}",
    ]
    if config.log_dir:
        lines.append(f'log_dir = "{config.log_dir.as_posix()}"')
    if config.fl_user_dir:
        lines.append(f'fl_user_dir = "{config.fl_user_dir.as_posix()}"')
    if config.fl_install_dir:
        lines.append(f'fl_install_dir = "{config.fl_install_dir.as_posix()}"')

    lines.extend(
        [
            "",
            "[port]",
            f'name = "{config.port.name}"',
            f'backend = "{config.port.backend}"',
        ]
    )
    if config.port.in_port_name:
        lines.append(f'in_port_name = "{config.port.in_port_name}"')
    if config.port.out_port_name:
        lines.append(f'out_port_name = "{config.port.out_port_name}"')
    lines.extend(
        [
            f"buffer_size = {config.port.buffer_size}",
            f"chunk_delay_ms = {config.port.chunk_delay_ms}",
            "",
            "[broker]",
            f'host = "{config.broker.host}"',
            f"port = {config.broker.port}",
        ]
    )
    if config.broker.token:
        lines.append(f'token = "{config.broker.token}"')
    lines.extend(
        [
            f"lease_ttl_sec = {config.broker.lease_ttl_sec}",
            f"idle_budget_ms = {config.broker.idle_budget_ms}",
            f"request_timeout_sec = {config.broker.request_timeout_sec}",
            "",
            "[safety]",
            f'mode = "{config.safety.mode}"',
            f"protected_targets = {config.safety.protected_targets!r}",
            f"confirm_mutations = {str(config.safety.confirm_mutations).lower()}",
            f"max_batch_size = {config.safety.max_batch_size}",
            f"tolerance = {config.safety.tolerance}",
            "",
            "[actuation]",
            f"enabled = {str(config.actuation.enabled).lower()}",
            f"piano_roll_enabled = {str(config.actuation.piano_roll_enabled).lower()}",
            f"allow_focus_steal = {str(config.actuation.allow_focus_steal).lower()}",
            f"user_idle_threshold_ms = {config.actuation.user_idle_threshold_ms}",
            f"key_delay_ms = {config.actuation.key_delay_ms}",
            "",
            "[render]",
            f"timeout_s = {config.render.timeout_s}",
            f"idle_timeout_s = {config.render.idle_timeout_s}",
            f"timeout_multiplier = {config.render.timeout_multiplier}",
            f'default_format = "{config.render.default_format}"',
            f'default_policy = "{config.render.default_policy}"',
            f"min_disk_free_multiplier = {config.render.min_disk_free_multiplier}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(
    cli_overrides: dict[str, Any] | None = None,
    *,
    project_dir: Path | None = None,
    user_config_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> StudioBridgeConfig:
    """Load configuration with layered precedence.

    Order of precedence (highest to lowest):
    1. CLI overrides
    2. Environment variables (SBRIDGE_*)
    3. Project config (.sbridge.toml in project_dir or current directory)
    4. User config (%LOCALAPPDATA%\\studiobridge\\config.toml)
    5. Hardcoded defaults
    """
    # 5. Base defaults
    resolved: dict[str, Any] = to_dict(StudioBridgeConfig())

    # 4. User config
    u_path = user_config_path or get_config_path()
    if u_path.is_file():
        user_dict = _read_toml_file(u_path)
        _deep_merge(resolved, user_dict)

    # 3. Project config
    p_dir = project_dir or Path.cwd()
    project_file = p_dir / ".sbridge.toml"
    if project_file.is_file():
        project_dict = _read_toml_file(project_file)
        _deep_merge(resolved, project_dict)

    # 2. Environment variables
    active_env = env if env is not None else os.environ
    env_dict = _parse_env_vars(active_env)
    _deep_merge(resolved, env_dict)

    # 1. CLI overrides
    if cli_overrides:
        flat_cli: dict[str, Any] = {}
        for k, v in cli_overrides.items():
            if k == "mode":
                flat_cli["safety.mode"] = v
            else:
                flat_cli[k] = v
        cli_nested = _unflatten_dict(flat_cli)
        _deep_merge(resolved, cli_nested)

    return config_from_dict(resolved)
