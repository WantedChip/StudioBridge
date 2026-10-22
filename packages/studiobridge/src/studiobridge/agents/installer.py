"""Agent configuration templates, detection, and installation engine.

Implements automated MCP server installer across all Tier-1 supported AI coding agents
and IDEs per spec 10_l2_interfaces.md §5 and requirements [AGT-01] through [AGT-04].
"""

from __future__ import annotations

import contextlib
import difflib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import tomlkit

logger = logging.getLogger("studiobridge.agents.installer")

# Default brand token identifiers
DEFAULT_DIST: Final[str] = "studiobridge"
DEFAULT_CLI: Final[str] = "sbridge"
DEFAULT_MCPNAME: Final[str] = "studiobridge"

# Templates directory inside package
TEMPLATES_DIR: Final[Path] = Path(__file__).parent / "templates"

# Project scope security warning per [AGT-04]
PROJECT_SCOPE_SECURITY_WARNING: Final[str] = (
    "SECURITY WARNING [AGT-04]: Project-scoped configuration files execute local commands "
    "when opening repositories. Do not open untrusted repositories with agent tools enabled "
    "without reviewing configuration."
)


@dataclass(frozen=True)
class AgentTarget:
    """Specification of an AI coding agent or IDE configuration target."""

    id: str
    display_name: str
    tier: int  # 1 (first-class installer) or 2 (generic snippet)
    config_format: str  # "json" or "toml"
    config_section: str  # "mcpServers", "servers", "context_servers", "mcp", "mcp_servers"
    default_scope: str  # "user" or "project"
    template_file: str
    aliases: tuple[str, ...] = ()
    next_steps: str = ""


@dataclass(frozen=True)
class DetectResult:
    """Result of agent presence and configuration detection."""

    target: AgentTarget
    detected: bool
    detected_by: str  # "config_file", "directory", "executable", "none"
    config_path: Path
    scope: str
    configured: bool  # whether studiobridge server entry is already in config


@dataclass(frozen=True)
class VerifyResult:
    """Result of post-install server startup verification."""

    passed: bool
    tools_count: int
    output: str
    error: str | None = None


@dataclass
class InstallResult:
    """Result of agent installation operation."""

    success: bool
    changed: bool
    message: str
    target: AgentTarget
    config_path: Path
    scope: str
    diff: str = ""
    backup_path: Path | None = None
    dry_run: bool = False
    verify_result: VerifyResult | None = None
    warnings: list[str] = field(default_factory=list)
    next_steps: str = ""


def get_appdata_dir() -> Path:
    """Return local or roaming AppData directory on Windows or cross-platform equivalent."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".config"


def get_localappdata_dir() -> Path:
    """Return LocalAppData directory on Windows or cross-platform equivalent."""
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return Path(localappdata)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".local" / "share"


# Tier-1 and Tier-2 Agent Target Definitions per 10_l2_interfaces.md §5.2
TARGETS_LIST: Final[list[AgentTarget]] = [
    AgentTarget(
        id="claude-code",
        display_name="Claude Code",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="project",
        template_file="claude_code.json",
        aliases=("claude_code", "claude"),
        next_steps="Run 'claude' in this folder and approve the MCP server if prompted.",
    ),
    AgentTarget(
        id="claude-desktop",
        display_name="Claude Desktop",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="user",
        template_file="claude_desktop.json",
        aliases=("claude_desktop", "claude-desktop-app"),
        next_steps="Restart Claude Desktop to connect to the studiobridge MCP server.",
    ),
    AgentTarget(
        id="codex",
        display_name="Codex",
        tier=1,
        config_format="toml",
        config_section="mcp_servers",
        default_scope="user",
        template_file="codex.toml",
        aliases=("codex-cli", "codex_cli"),
        next_steps="Run 'codex' or open your Codex IDE session.",
    ),
    AgentTarget(
        id="cursor",
        display_name="Cursor",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="project",
        template_file="cursor.json",
        aliases=("cursor-ai", "cursor_ide"),
        next_steps=(
            "Reload Cursor window (Ctrl+Shift+P > Developer: Reload Window) or restart Cursor."
        ),
    ),
    AgentTarget(
        id="windsurf",
        display_name="Windsurf",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="user",
        template_file="windsurf.json",
        aliases=("codeium-windsurf", "windsurf_ide"),
        next_steps="Restart Windsurf or refresh Cascade MCP tools.",
    ),
    AgentTarget(
        id="zed",
        display_name="Zed",
        tier=1,
        config_format="json",
        config_section="context_servers",
        default_scope="user",
        template_file="zed.json",
        aliases=("zed-editor", "zed_ide"),
        next_steps="Restart Zed to activate the studiobridge context server.",
    ),
    AgentTarget(
        id="opencode",
        display_name="opencode",
        tier=1,
        config_format="json",
        config_section="mcp",
        default_scope="project",
        template_file="opencode.json",
        aliases=("open-code", "opencode-cli"),
        next_steps="Run 'opencode' in this folder.",
    ),
    AgentTarget(
        id="antigravity",
        display_name="Antigravity",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="user",
        template_file="antigravity.json",
        aliases=("agy", "google-antigravity"),
        next_steps="In Antigravity, click 'View raw config' / refresh MCP servers in the UI.",
    ),
    AgentTarget(
        id="gemini",
        display_name="Gemini CLI",
        tier=1,
        config_format="json",
        config_section="mcpServers",
        default_scope="user",
        template_file="gemini.json",
        aliases=("gemini-cli", "gemini_cli"),
        next_steps="Run 'gemini' to start using studiobridge tools.",
    ),
    AgentTarget(
        id="vscode",
        display_name="VS Code",
        tier=1,
        config_format="json",
        config_section="servers",
        default_scope="project",
        template_file="vscode.json",
        aliases=("code", "copilot", "github-copilot"),
        next_steps=("Restart VS Code or reload window to start GitHub Copilot MCP server."),
    ),
    AgentTarget(
        id="generic",
        display_name="Generic MCP Client",
        tier=2,
        config_format="json",
        config_section="mcpServers",
        default_scope="user",
        template_file="generic.json",
        aliases=("cline", "roo", "continue", "kiro", "goose", "warp"),
        next_steps="Configure your MCP client using the generated studiobridge server block.",
    ),
]

TARGETS_MAP: Final[dict[str, AgentTarget]] = {}
for target in TARGETS_LIST:
    TARGETS_MAP[target.id] = target
    for alias in target.aliases:
        TARGETS_MAP[alias] = target


def get_target(name_or_alias: str) -> AgentTarget:
    """Resolve agent target by ID or alias (case-insensitive)."""
    norm = name_or_alias.strip().lower().replace("_", "-")
    # Check exact normalized match
    if norm in TARGETS_MAP:
        return TARGETS_MAP[norm]
    # Check underscore variant
    und = norm.replace("-", "_")
    if und in TARGETS_MAP:
        return TARGETS_MAP[und]
    # Check bare id
    for t in TARGETS_LIST:
        if t.id.lower() == norm or any(a.lower() == norm for a in t.aliases):
            return t

    valid_names = sorted({t.id for t in TARGETS_LIST})
    raise ValueError(f"Unknown agent '{name_or_alias}'. Supported agents: {', '.join(valid_names)}")


def list_targets() -> list[AgentTarget]:
    """Return all known agent targets."""
    return list(TARGETS_LIST)


def strip_jsonc_comments_and_trailing_commas(text: str) -> str:
    """Strip // line comments, /* block comments */ and trailing commas outside strings."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    string_escape = False

    # Pass 1: strip comments while preserving strings
    while i < n:
        c = text[i]

        if in_string:
            out.append(c)
            if string_escape:
                string_escape = False
            elif c == "\\":
                string_escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
            string_escape = False
            out.append(c)
            i += 1
            continue

        # Check for line comment //
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue

        # Check for block comment /*
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(c)
        i += 1

    clean_comments = "".join(out)

    # Pass 2: remove trailing commas before } or ]
    out2: list[str] = []
    i = 0
    n = len(clean_comments)
    in_string = False
    string_escape = False

    while i < n:
        c = clean_comments[i]

        if in_string:
            out2.append(c)
            if string_escape:
                string_escape = False
            elif c == "\\":
                string_escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
            string_escape = False
            out2.append(c)
            i += 1
            continue

        if c == ",":
            # Peek ahead to next non-whitespace character
            j = i + 1
            while j < n and clean_comments[j] in " \t\r\n":
                j += 1
            if j < n and clean_comments[j] in "}]":
                # Trailing comma: discard
                i += 1
                continue

        out2.append(c)
        i += 1

    return "".join(out2)


def detect_indentation(text: str) -> int:
    """Detect JSON indentation style (2 or 4 spaces; default 2)."""
    for line in text.splitlines():
        if line.startswith("    ") and not line.startswith("      "):
            return 4
        if line.startswith("  ") and not line.startswith("   "):
            return 2
    return 2


def validate_zero_secrets(content: str) -> None:
    """Enforce security rule [AGT-03]: zero credentials, tokens, or absolute user home paths."""
    # 1. Check for absolute user home directory path
    try:
        home_path = Path.home().resolve()
        home_str = str(home_path)
        home_posix = home_path.as_posix()
        if home_str in content or home_posix in content:
            raise ValueError(
                "Security rule [AGT-03] violated: configuration contains absolute user home path"
            )
    except Exception:
        pass

    # Generic Windows user directory patterns (e.g. C:\Users\Username or /Users/username)
    if re.search(r"[a-zA-Z]:(?:\\+|/+)+Users(?:\\+|/+)+[^\\/\s\"']+", content, re.IGNORECASE):
        raise ValueError(
            "Security rule [AGT-03] violated: configuration contains user home path "
            "(C:\\Users\\...)"
        )
    if re.search(r"/(?:Users|home)/[^\\/\s\"']+", content):
        raise ValueError(
            "Security rule [AGT-03] violated: configuration contains user home path "
            "(/Users/... or /home/...)"
        )

    # 2. Check for suspicious credentials, tokens, or private keys
    secret_pat = re.search(
        r"[\"']?(?:secret|token|password|api_key|apikey|private_key)[\"']?\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']",
        content,
        re.IGNORECASE,
    )
    if secret_pat:
        raise ValueError(
            "Security rule [AGT-03] violated: configuration appears to contain "
            f"credential/token ({secret_pat.group(0)})"
        )


def resolve_config_path(
    target: AgentTarget,
    scope: str = "user",
    project_dir: Path | None = None,
) -> Path:
    """Resolve target configuration file path for given scope."""
    p_dir = project_dir or Path.cwd()

    if scope == "project":
        if target.id == "claude-code":
            return p_dir / ".mcp.json"
        if target.id == "codex":
            return p_dir / ".codex" / "config.toml"
        if target.id == "cursor":
            return p_dir / ".cursor" / "mcp.json"
        if target.id == "opencode":
            return p_dir / "opencode.json"
        if target.id == "vscode":
            return p_dir / ".vscode" / "mcp.json"
        if target.id == "zed":
            return p_dir / ".zed" / "settings.json"
        # Fallback for other targets if requested in project scope
        return p_dir / "mcp.json"

    # User scope
    if target.id == "claude-code":
        return Path.home() / ".claude.json"
    if target.id == "claude-desktop":
        if sys.platform == "win32":
            return get_appdata_dir() / "Claude" / "claude_desktop_config.json"
        if sys.platform == "darwin":
            return (
                Path.home()
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    if target.id == "codex":
        return Path.home() / ".codex" / "config.toml"
    if target.id == "cursor":
        return Path.home() / ".cursor" / "mcp.json"
    if target.id == "windsurf":
        return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    if target.id == "zed":
        if sys.platform == "win32":
            return get_appdata_dir() / "Zed" / "settings.json"
        return Path.home() / ".config" / "zed" / "settings.json"
    if target.id == "opencode":
        if sys.platform == "win32":
            return get_appdata_dir() / "opencode" / "opencode.json"
        return Path.home() / ".config" / "opencode" / "opencode.json"
    if target.id == "antigravity":
        # Check ~/.gemini/antigravity or ~/.gemini/config
        p1 = Path.home() / ".gemini" / "antigravity" / "mcp_config.json"
        p2 = Path.home() / ".gemini" / "config" / "mcp_config.json"
        if p1.exists() or p1.parent.exists():
            return p1
        if p2.exists():
            return p2
        return p1
    if target.id == "gemini":
        return Path.home() / ".gemini" / "settings.json"
    if target.id == "vscode":
        if sys.platform == "win32":
            return get_appdata_dir() / "Code" / "User" / "mcp.json"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
        return Path.home() / ".config" / "Code" / "User" / "mcp.json"

    # Generic fallback
    return Path.home() / ".mcp.json"


def render_server_entry(
    target: AgentTarget,
    launcher: str = "uvx",
    is_windows: bool | None = None,
    dist: str = DEFAULT_DIST,
) -> dict[str, Any]:
    """Generate server entry dictionary for target agent and launcher."""
    on_windows = sys.platform == "win32" if is_windows is None else is_windows

    if launcher == "npm":
        if on_windows:
            cmd = "cmd"
            args = ["/c", "npx", "-y", dist, "mcp"]
        else:
            cmd = "npx"
            args = ["-y", dist, "mcp"]
    else:
        # Default uvx launcher
        cmd = "uvx"
        args = [dist, "mcp"]

    if target.id == "opencode":
        # opencode format: command is one single array including executable; environment key
        if launcher == "npm":
            full_command = (
                ["cmd", "/c", "npx", "-y", dist, "mcp"]
                if on_windows
                else ["npx", "-y", dist, "mcp"]
            )
        else:
            full_command = ["uvx", dist, "mcp"]
        return {
            "type": "local",
            "command": full_command,
            "environment": {},
            "enabled": True,
        }

    if target.id == "vscode":
        # VS Code format: type is stdio
        return {
            "type": "stdio",
            "command": cmd,
            "args": args,
        }

    if target.id == "codex":
        # Codex TOML format: tool_timeout_sec >= 120
        return {
            "command": cmd,
            "args": args,
            "tool_timeout_sec": 120,
        }

    # Standard MCP format
    return {
        "command": cmd,
        "args": args,
    }


def render_snippet(
    target: AgentTarget,
    launcher: str = "uvx",
    is_windows: bool | None = None,
    dist: str = DEFAULT_DIST,
) -> str:
    """Render standalone copy-pasteable configuration snippet for agent."""
    on_windows = sys.platform == "win32" if is_windows is None else is_windows
    entry = render_server_entry(target, launcher=launcher, is_windows=on_windows, dist=dist)

    if target.config_format == "toml":
        doc = tomlkit.document()
        table = tomlkit.table()
        table["command"] = entry["command"]
        args_arr = tomlkit.array()
        for a in entry["args"]:
            args_arr.append(a)
        table["args"] = args_arr
        if "tool_timeout_sec" in entry:
            table["tool_timeout_sec"] = entry["tool_timeout_sec"]
        servers_table = tomlkit.table()
        servers_table[dist] = table
        doc["mcp_servers"] = servers_table
        rendered = tomlkit.dumps(doc)
    else:
        section = target.config_section
        wrapped = {section: {dist: entry}}
        rendered = json.dumps(wrapped, indent=2) + "\n"

    validate_zero_secrets(rendered)
    return rendered


def merge_config(
    existing_text: str | None,
    target: AgentTarget,
    launcher: str = "uvx",
    is_windows: bool | None = None,
    dist: str = DEFAULT_DIST,
    filename: str = "config",
) -> tuple[str, bool, str]:
    """Merge StudioBridge server entry into existing config text.

    Returns:
        (new_text, has_changes, unified_diff)
    """
    on_windows = sys.platform == "win32" if is_windows is None else is_windows
    entry = render_server_entry(target, launcher=launcher, is_windows=on_windows, dist=dist)
    orig_text = existing_text or ""

    if target.config_format == "toml":
        doc = tomlkit.document() if not orig_text.strip() else tomlkit.parse(orig_text)

        if "mcp_servers" not in doc:
            doc["mcp_servers"] = tomlkit.table()

        mcp_servers: Any = doc["mcp_servers"]

        # Check existing entry for idempotency
        if dist in mcp_servers:
            existing_entry = mcp_servers[dist]
            same_cmd = existing_entry.get("command") == entry["command"]
            same_args = list(existing_entry.get("args", [])) == list(entry["args"])
            same_timeout = existing_entry.get("tool_timeout_sec") == entry.get("tool_timeout_sec")
            if same_cmd and same_args and same_timeout:
                return orig_text, False, ""

        server_table = tomlkit.table()
        server_table["command"] = entry["command"]
        args_arr = tomlkit.array()
        for a in entry["args"]:
            args_arr.append(a)
        server_table["args"] = args_arr
        if "tool_timeout_sec" in entry:
            server_table["tool_timeout_sec"] = entry["tool_timeout_sec"]

        mcp_servers[dist] = server_table
        new_text = tomlkit.dumps(doc)

    else:
        # JSON / JSONC merge
        indent = 2
        data: dict[str, Any] = {}
        if orig_text.strip():
            indent = detect_indentation(orig_text)
            try:
                data = json.loads(orig_text)
            except json.JSONDecodeError:
                cleaned = strip_jsonc_comments_and_trailing_commas(orig_text)
                data = json.loads(cleaned)

        section = target.config_section
        if section not in data or not isinstance(data[section], dict):
            data[section] = {}

        # Check idempotency
        existing_val = data[section].get(dist)
        if existing_val == entry:
            return orig_text, False, ""

        data[section][dist] = entry
        new_text = json.dumps(data, indent=indent) + "\n"

    validate_zero_secrets(new_text)

    # Compute unified diff
    orig_lines = orig_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )

    return new_text, True, diff


class AgentInstaller:
    """Automated AI coding agent MCP configuration installer and detector."""

    def __init__(
        self,
        project_dir: Path | None = None,
        dist: str = DEFAULT_DIST,
        cli: str = DEFAULT_CLI,
    ) -> None:
        """Initialize installer with project directory context and brand tokens."""
        self.project_dir: Path = (project_dir or Path.cwd()).resolve()
        self.dist: str = dist
        self.cli: str = cli

    def get_template(self, target_id: str) -> str:
        """Read raw template content from disk."""
        target = get_target(target_id)
        tmpl_path = TEMPLATES_DIR / target.template_file
        if not tmpl_path.exists():
            raise FileNotFoundError(
                f"Template file '{target.template_file}' not found in {TEMPLATES_DIR}"
            )
        return tmpl_path.read_text(encoding="utf-8")

    def detect_agent(self, target: AgentTarget) -> DetectResult:
        """Detect whether an agent is present and if StudioBridge is configured."""
        # 1. Check project config
        project_cfg = resolve_config_path(target, scope="project", project_dir=self.project_dir)
        # 2. Check user config
        user_cfg = resolve_config_path(target, scope="user", project_dir=self.project_dir)

        detected = False
        detected_by = "none"
        chosen_path = user_cfg
        chosen_scope = "user"

        if target.default_scope == "project" and project_cfg.exists():
            detected = True
            detected_by = "config_file"
            chosen_path = project_cfg
            chosen_scope = "project"
        elif user_cfg.exists():
            detected = True
            detected_by = "config_file"
            chosen_path = user_cfg
            chosen_scope = "user"
        elif project_cfg.exists():
            detected = True
            detected_by = "config_file"
            chosen_path = project_cfg
            chosen_scope = "project"

        # Check directories or executables if config file not found
        if not detected:
            if target.id == "claude-code":
                if (Path.home() / ".claude").exists() or (Path.home() / ".claude.json").exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("claude"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "claude-desktop":
                if (get_appdata_dir() / "Claude").exists() or (
                    get_localappdata_dir() / "Programs" / "Claude"
                ).exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("claude-desktop") or shutil.which("Claude"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "codex":
                if (Path.home() / ".codex").exists() or (self.project_dir / ".codex").exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("codex"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "cursor":
                if (
                    (self.project_dir / ".cursor").exists()
                    or (Path.home() / ".cursor").exists()
                    or (get_localappdata_dir() / "Programs" / "cursor").exists()
                ):
                    detected = True
                    detected_by = "directory"
                elif shutil.which("cursor"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "windsurf":
                if (Path.home() / ".codeium" / "windsurf").exists() or (
                    get_localappdata_dir() / "Programs" / "Windsurf"
                ).exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("windsurf"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "zed":
                if (
                    (get_appdata_dir() / "Zed").exists()
                    or (Path.home() / ".config" / "zed").exists()
                    or (get_localappdata_dir() / "Programs" / "Zed").exists()
                ):
                    detected = True
                    detected_by = "directory"
                elif shutil.which("zed"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "opencode":
                if (Path.home() / ".config" / "opencode").exists() or (
                    get_appdata_dir() / "opencode"
                ).exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("opencode"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "antigravity":
                if (Path.home() / ".gemini" / "antigravity").exists() or (
                    Path.home() / ".gemini" / "config"
                ).exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("agy"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "gemini":
                if (Path.home() / ".gemini").exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("gemini"):
                    detected = True
                    detected_by = "executable"
            elif target.id == "vscode":
                if (self.project_dir / ".vscode").exists() or (get_appdata_dir() / "Code").exists():
                    detected = True
                    detected_by = "directory"
                elif shutil.which("code"):
                    detected = True
                    detected_by = "executable"

            chosen_scope = target.default_scope
            chosen_path = resolve_config_path(
                target, scope=chosen_scope, project_dir=self.project_dir
            )

        # Inspect if studiobridge server entry is already configured
        configured = False
        if chosen_path.exists():
            try:
                content = chosen_path.read_text(encoding="utf-8")
                if target.config_format == "toml":
                    doc = tomlkit.parse(content)
                    configured = self.dist in doc.get("mcp_servers", {})
                else:
                    cleaned = strip_jsonc_comments_and_trailing_commas(content)
                    data = json.loads(cleaned)
                    section_data = data.get(target.config_section, {})
                    configured = isinstance(section_data, dict) and self.dist in section_data
            except Exception:
                configured = False

        return DetectResult(
            target=target,
            detected=detected,
            detected_by=detected_by,
            config_path=chosen_path,
            scope=chosen_scope,
            configured=configured,
        )

    def detect_all(self) -> list[DetectResult]:
        """Detect all registered agent targets."""
        return [self.detect_agent(t) for t in TARGETS_LIST if t.tier == 1]

    def verify_server(self, timeout: float = 10.0) -> VerifyResult:
        """Run 'sbridge mcp --check' to verify server startup without hanging."""
        cmd = [sys.executable, "-m", "studiobridge.cli", "mcp", "--check", "--json"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode == 0:
                try:
                    data = json.loads(proc.stdout)
                    count = data.get("tools_count", 0)
                    return VerifyResult(passed=True, tools_count=count, output=proc.stdout)
                except json.JSONDecodeError:
                    return VerifyResult(passed=True, tools_count=0, output=proc.stdout)
            else:
                return VerifyResult(
                    passed=False,
                    tools_count=0,
                    output=proc.stdout,
                    error=proc.stderr or f"Server check returned non-zero code {proc.returncode}",
                )
        except subprocess.TimeoutExpired:
            return VerifyResult(
                passed=False,
                tools_count=0,
                output="",
                error="Timed out waiting for 'sbridge mcp --check'",
            )
        except Exception as exc:
            return VerifyResult(passed=False, tools_count=0, output="", error=str(exc))

    def install(
        self,
        agent_name: str,
        scope: str | None = None,
        dry_run: bool = False,
        launcher: str = "uvx",
        force: bool = False,
        verify: bool = True,
    ) -> InstallResult:
        """Install StudioBridge server entry into target agent configuration."""
        target = get_target(agent_name)
        chosen_scope = scope or target.default_scope
        warnings: list[str] = []

        if chosen_scope == "project":
            warnings.append(PROJECT_SCOPE_SECURITY_WARNING)

        config_path = resolve_config_path(target, scope=chosen_scope, project_dir=self.project_dir)

        existing_text: str | None = None
        if config_path.exists():
            try:
                existing_text = config_path.read_text(encoding="utf-8")
            except Exception as exc:
                return InstallResult(
                    success=False,
                    changed=False,
                    message=f"Failed to read existing config at {config_path}: {exc}",
                    target=target,
                    config_path=config_path,
                    scope=chosen_scope,
                    warnings=warnings,
                )

        try:
            new_text, has_changes, diff = merge_config(
                existing_text=existing_text,
                target=target,
                launcher=launcher,
                dist=self.dist,
                filename=config_path.name,
            )
        except Exception as exc:
            return InstallResult(
                success=False,
                changed=False,
                message=f"Merge error: {exc}",
                target=target,
                config_path=config_path,
                scope=chosen_scope,
                warnings=warnings,
            )

        if not has_changes and not force:
            return InstallResult(
                success=True,
                changed=False,
                message=f"Already configured in {config_path} (no changes needed)",
                target=target,
                config_path=config_path,
                scope=chosen_scope,
                warnings=warnings,
                next_steps=target.next_steps,
            )

        if dry_run:
            return InstallResult(
                success=True,
                changed=has_changes,
                message=f"Dry-run preview for {target.display_name} ({config_path})",
                target=target,
                config_path=config_path,
                scope=chosen_scope,
                diff=diff,
                dry_run=True,
                warnings=warnings,
                next_steps=target.next_steps,
            )

        # Create parent directory if missing
        config_path.parent.mkdir(parents=True, exist_ok=True)

        backup_path: Path | None = None
        if config_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = config_path.with_name(f"{config_path.name}.bak-{timestamp}")
            try:
                backup_path.write_text(existing_text or "", encoding="utf-8")
            except Exception as exc:
                return InstallResult(
                    success=False,
                    changed=False,
                    message=f"Failed to create backup at {backup_path}: {exc}",
                    target=target,
                    config_path=config_path,
                    scope=chosen_scope,
                    warnings=warnings,
                )

        # Atomic write via temporary file
        tmp_path = config_path.with_name(f"{config_path.name}.tmp.{uuid.uuid4().hex[:8]}")
        try:
            tmp_path.write_text(new_text, encoding="utf-8")
            os.replace(tmp_path, config_path)
        except Exception as exc:
            if tmp_path.exists():
                with contextlib.suppress(OSError):
                    tmp_path.unlink()
            return InstallResult(
                success=False,
                changed=False,
                message=f"Failed to write configuration file at {config_path}: {exc}",
                target=target,
                config_path=config_path,
                scope=chosen_scope,
                warnings=warnings,
            )

        # Verify server startup via sbridge mcp --check
        verify_res: VerifyResult | None = None
        if verify:
            verify_res = self.verify_server()

        return InstallResult(
            success=True,
            changed=True,
            message=f"Successfully installed StudioBridge in {target.display_name} ({config_path})",
            target=target,
            config_path=config_path,
            scope=chosen_scope,
            diff=diff,
            backup_path=backup_path,
            verify_result=verify_res,
            warnings=warnings,
            next_steps=target.next_steps,
        )
