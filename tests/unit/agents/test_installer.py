"""Unit and golden-file regression tests for AI coding agent installer and templates.

Verifies:
1. Target definitions and aliases across all Tier-1 supported agents.
2. Template validity, brand token placeholders, and zero-secrets compliance.
3. Safe merging against real-world dirty agent config files (JSONC comments,
   trailing commas, existing other MCP servers, custom settings).
4. TOML comment and structure preservation via tomlkit.
5. Idempotency (re-running yields zero diff).
6. Backup creation (.bak-YYYYmmddHHMMSS) and atomic writes.
7. [AGT-04] Project-scope security warning.
8. [AGT-03] Zero secrets, tokens, or absolute user home paths.
9. Post-install verification via 'sbridge mcp --check'.
10. CLI commands 'sbridge agent list', 'install', and 'snippet'.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomlkit

from studiobridge.agents import (
    PROJECT_SCOPE_SECURITY_WARNING,
    AgentInstaller,
    AgentTarget,
    get_target,
    list_targets,
    merge_config,
    render_server_entry,
    render_snippet,
    strip_jsonc_comments_and_trailing_commas,
    validate_zero_secrets,
)
from studiobridge.cli import main as cli_main


class TestAgentTargets:
    """Validate agent targets and registry lookups."""

    TIER_1_IDS = [
        "claude-code",
        "claude-desktop",
        "codex",
        "cursor",
        "windsurf",
        "zed",
        "opencode",
        "antigravity",
        "gemini",
        "vscode",
    ]

    def test_all_tier_1_targets_present(self) -> None:
        targets = {t.id: t for t in list_targets()}
        for tid in self.TIER_1_IDS:
            assert tid in targets
            assert targets[tid].tier == 1
            assert isinstance(targets[tid], AgentTarget)

    def test_target_aliases_case_insensitive(self) -> None:
        assert get_target("claude-code").id == "claude-code"
        assert get_target("Claude_Code").id == "claude-code"
        assert get_target("CLAUDE").id == "claude-code"
        assert get_target("Cursor").id == "cursor"
        assert get_target("codex-cli").id == "codex"
        assert get_target("agy").id == "antigravity"
        assert get_target("copilot").id == "vscode"

    def test_unknown_target_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent 'unknown-agent'"):
            get_target("unknown-agent")


class TestTemplateFiles:
    """Validate template files on disk."""

    def test_all_tier_1_template_files_exist(self) -> None:
        installer = AgentInstaller()
        for tid in TestAgentTargets.TIER_1_IDS:
            tmpl = installer.get_template(tid)
            assert "{DIST}" in tmpl
            validate_zero_secrets(tmpl)

    def test_template_syntax_validity(self) -> None:
        installer = AgentInstaller()
        for target in list_targets():
            raw = installer.get_template(target.id)
            rendered = raw.replace("{DIST}", "studiobridge")
            if target.config_format == "toml":
                doc = tomlkit.parse(rendered)
                assert "mcp_servers" in doc
            else:
                data = json.loads(rendered)
                assert isinstance(data, dict)


class TestZeroSecretsRule:
    """Enforce security rule [AGT-03]: zero secrets or absolute home paths."""

    def test_valid_content_passes(self) -> None:
        clean = json.dumps(
            {"mcpServers": {"studiobridge": {"command": "uvx", "args": ["studiobridge", "mcp"]}}}
        )
        validate_zero_secrets(clean)

    def test_rejects_user_home_path_windows(self) -> None:
        dirty = json.dumps({"command": r"C:\Users\JohnDoe\AppData\Local\Programs\uvx.exe"})
        with pytest.raises(ValueError, match="user home path"):
            validate_zero_secrets(dirty)

    def test_rejects_user_home_path_unix(self) -> None:
        dirty = json.dumps({"command": "/home/johndoe/.local/bin/uvx"})
        with pytest.raises(ValueError, match="user home path"):
            validate_zero_secrets(dirty)

    def test_rejects_secret_or_token(self) -> None:
        dirty = json.dumps({"token": "ab12cd34ef56gh78ij90"})
        with pytest.raises(ValueError, match="credential/token"):
            validate_zero_secrets(dirty)

    def test_snippets_are_clean(self) -> None:
        for target in list_targets():
            for launcher in ("uvx", "npm"):
                snippet = render_snippet(target, launcher=launcher)
                validate_zero_secrets(snippet)


class TestDirtyConfigMerging:
    """Verify safe merging into real-world dirty agent configuration files."""

    def test_strip_jsonc_direct(self) -> None:
        raw = '// comment\n{\n  /* block */\n  "key": "value",\n}'
        cleaned = strip_jsonc_comments_and_trailing_commas(raw)
        data = json.loads(cleaned)
        assert data == {"key": "value"}

    def test_merge_into_jsonc_with_comments_and_trailing_commas(self) -> None:
        dirty_jsonc = """// Master Claude Desktop configuration
{
  /* Primary remote filesystem MCP server */
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\\\Projects",],
    },
  }, // end of servers
  "theme": "dark",
}"""
        target = get_target("claude-desktop")
        new_text, changed, diff = merge_config(
            existing_text=dirty_jsonc,
            target=target,
            launcher="uvx",
        )

        assert changed is True
        assert "studiobridge" in diff
        # Check parsed JSON structure
        data = json.loads(new_text)
        assert data["theme"] == "dark"
        assert "filesystem" in data["mcpServers"]
        assert "studiobridge" in data["mcpServers"]
        assert data["mcpServers"]["studiobridge"]["command"] == "uvx"
        assert data["mcpServers"]["studiobridge"]["args"] == ["studiobridge", "mcp"]

    def test_merge_into_toml_preserves_comments_and_structure(self) -> None:
        dirty_toml = """# Codex CLI Configuration File
title = "My Project"

[mcp_servers.database]
# Connects to local SQLite
command = "sqlite3"
args = ["test.db"]
tool_timeout_sec = 60
"""
        target = get_target("codex")
        new_text, changed, diff = merge_config(
            existing_text=dirty_toml,
            target=target,
            launcher="uvx",
        )

        assert changed is True
        assert "[mcp_servers.studiobridge]" in new_text
        assert "# Codex CLI Configuration File" in new_text
        assert "# Connects to local SQLite" in new_text
        assert "database" in new_text

        doc = tomlkit.parse(new_text)
        assert doc["mcp_servers"]["database"]["command"] == "sqlite3"  # pyright: ignore[reportIndexIssue]
        assert doc["mcp_servers"]["studiobridge"]["command"] == "uvx"  # pyright: ignore[reportIndexIssue]
        assert doc["mcp_servers"]["studiobridge"]["tool_timeout_sec"] == 120  # pyright: ignore[reportIndexIssue]

    def test_merge_into_zed_context_servers(self) -> None:
        dirty_zed = """{
  "theme": "Solarized",
  "context_servers": {
    "weather": {
      "command": "uvx",
      "args": ["weather-mcp"]
    }
  }
}"""
        target = get_target("zed")
        new_text, changed, diff = merge_config(
            existing_text=dirty_zed,
            target=target,
            launcher="uvx",
        )

        assert changed is True
        data = json.loads(new_text)
        assert data["theme"] == "Solarized"
        assert "weather" in data["context_servers"]
        assert "studiobridge" in data["context_servers"]
        assert data["context_servers"]["studiobridge"]["command"] == "uvx"

    def test_merge_into_opencode_format(self) -> None:
        dirty_opencode = """{
  "mcp": {
    "git": {
      "type": "local",
      "command": ["git-mcp", "serve"],
      "environment": {},
      "enabled": true
    }
  }
}"""
        target = get_target("opencode")
        new_text, changed, diff = merge_config(
            existing_text=dirty_opencode,
            target=target,
            launcher="uvx",
        )

        assert changed is True
        data = json.loads(new_text)
        assert "git" in data["mcp"]
        assert "studiobridge" in data["mcp"]
        sb_entry = data["mcp"]["studiobridge"]
        assert sb_entry["type"] == "local"
        assert sb_entry["command"] == ["uvx", "studiobridge", "mcp"]
        assert sb_entry["enabled"] is True

    def test_merge_into_vscode_servers_format(self) -> None:
        dirty_vscode = """{
  "editor.tabSize": 4,
  "servers": {
    "node-mcp": {
      "type": "stdio",
      "command": "node",
      "args": ["mcp.js"]
    }
  }
}"""
        target = get_target("vscode")
        new_text, changed, diff = merge_config(
            existing_text=dirty_vscode,
            target=target,
            launcher="uvx",
        )

        assert changed is True
        data = json.loads(new_text)
        assert data["editor.tabSize"] == 4
        assert "node-mcp" in data["servers"]
        assert "studiobridge" in data["servers"]
        assert data["servers"]["studiobridge"]["type"] == "stdio"
        assert data["servers"]["studiobridge"]["command"] == "uvx"


class TestIdempotency:
    """Verify that re-running merge or install yields zero diff."""

    def test_json_idempotency(self) -> None:
        target = get_target("cursor")
        first_text, changed1, _ = merge_config(None, target, launcher="uvx")
        assert changed1 is True

        second_text, changed2, diff2 = merge_config(first_text, target, launcher="uvx")
        assert changed2 is False
        assert diff2 == ""
        assert second_text == first_text

    def test_toml_idempotency(self) -> None:
        target = get_target("codex")
        first_text, changed1, _ = merge_config(None, target, launcher="uvx")
        assert changed1 is True

        second_text, changed2, diff2 = merge_config(first_text, target, launcher="uvx")
        assert changed2 is False
        assert diff2 == ""
        assert second_text == first_text


class TestInstallerOperations:
    """Test full install workflow: dry-run, backup creation, project warnings."""

    def test_dry_run_does_not_modify_disk(self, tmp_path: Path) -> None:
        installer = AgentInstaller(project_dir=tmp_path)
        cfg_file = tmp_path / ".cursor" / "mcp.json"

        result = installer.install("cursor", scope="project", dry_run=True)
        assert result.success is True
        assert result.dry_run is True
        assert result.changed is True
        assert "studiobridge" in result.diff
        assert not cfg_file.exists()
        assert PROJECT_SCOPE_SECURITY_WARNING in result.warnings

    def test_install_creates_file_and_backup_on_modification(self, tmp_path: Path) -> None:
        installer = AgentInstaller(project_dir=tmp_path)
        cfg_dir = tmp_path / ".cursor"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "mcp.json"

        initial_content = json.dumps({"mcpServers": {"other": {"command": "node"}}})
        cfg_file.write_text(initial_content, encoding="utf-8")

        # Run installation
        result = installer.install("cursor", scope="project", dry_run=False, verify=False)
        assert result.success is True
        assert result.changed is True
        assert result.backup_path is not None
        assert result.backup_path.exists()
        assert ".bak-" in result.backup_path.name
        assert result.backup_path.read_text(encoding="utf-8") == initial_content

        # Verify new file content
        new_data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert "other" in new_data["mcpServers"]
        assert "studiobridge" in new_data["mcpServers"]

        # Run again: should be idempotent (no changes, no new backup)
        re_result = installer.install("cursor", scope="project", dry_run=False, verify=False)
        assert re_result.success is True
        assert re_result.changed is False
        assert re_result.backup_path is None

    def test_npm_launcher_windows_vs_unix(self) -> None:
        target = get_target("cursor")
        win_entry = render_server_entry(target, launcher="npm", is_windows=True)
        assert win_entry["command"] == "cmd"
        assert win_entry["args"] == ["/c", "npx", "-y", "studiobridge", "mcp"]

        unix_entry = render_server_entry(target, launcher="npm", is_windows=False)
        assert unix_entry["command"] == "npx"
        assert unix_entry["args"] == ["-y", "studiobridge", "mcp"]

    def test_server_verification(self) -> None:
        installer = AgentInstaller()
        verify_res = installer.verify_server()
        assert verify_res.passed is True
        assert verify_res.tools_count > 0


class TestAgentCliCommands:
    """Test CLI commands execution."""

    def test_cli_agent_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_main(["agent", "list"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Claude Code" in captured.out
        assert "Cursor" in captured.out

    def test_cli_agent_list_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_main(["agent", "list", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert any(item["id"] == "cursor" for item in data)

    def test_cli_agent_snippet_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_main(["agent", "snippet", "codex", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert data["agent"] == "codex"
        assert "[mcp_servers.studiobridge]" in data["snippet"]

    def test_cli_agent_install_dry_run_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_main(["agent", "install", "cursor", "--scope", "project", "--dry-run", "--json"])
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert data["results"]["dry_run"] is True
        assert any("SECURITY WARNING [AGT-04]" in w for w in data["results"]["warnings"])

    def test_cli_agent_invalid_target(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli_main(["agent", "install", "nonexistent-agent"])
        assert code == 2
        captured = capsys.readouterr()
        assert "Unknown agent 'nonexistent-agent'" in captured.err


class TestTier1GoldenMerge:
    """Golden-file regression test suite across all 10 Tier-1 targets."""

    @pytest.mark.parametrize("target_id", TestAgentTargets.TIER_1_IDS)
    def test_golden_merge_tier_1_agent(self, target_id: str) -> None:
        target = get_target(target_id)

        # 1. Merge into blank
        text1, changed1, diff1 = merge_config(None, target, launcher="uvx")
        assert changed1 is True
        assert diff1 != ""
        validate_zero_secrets(text1)

        # 2. Verify idempotency on second pass
        text2, changed2, diff2 = merge_config(text1, target, launcher="uvx")
        assert changed2 is False
        assert diff2 == ""
        assert text2 == text1

        # 3. Merge into dirty file with existing custom settings and other MCP server
        if target.config_format == "toml":
            dirty = """# Existing comments
app_name = "test"

[mcp_servers.preexisting]
command = "node"
args = ["test.js"]
"""
        elif target.config_section == "servers":
            dirty = """{
  // VS Code settings
  "editor.fontSize": 12,
  "servers": {
    "preexisting": {
      "type": "stdio",
      "command": "node",
      "args": ["test.js"],
    },
  },
}"""
        elif target.config_section == "context_servers":
            dirty = """{
  /* Zed configuration */
  "theme": "Nord",
  "context_servers": {
    "preexisting": {
      "command": "node",
      "args": ["test.js"],
    },
  },
}"""
        elif target.config_section == "mcp":
            dirty = """{
  // opencode config
  "mcp": {
    "preexisting": {
      "type": "local",
      "command": ["node", "test.js"],
      "environment": {},
      "enabled": true,
    },
  },
}"""
        else:
            dirty = """{
  // General MCP configuration
  "mcpServers": {
    "preexisting": {
      "command": "node",
      "args": ["test.js"],
    },
  },
}"""

        merged, changed_dirty, diff_dirty = merge_config(dirty, target, launcher="uvx")
        assert changed_dirty is True
        assert "studiobridge" in diff_dirty
        validate_zero_secrets(merged)

        # Verify preexisting server is preserved
        assert "preexisting" in merged

        # 4. Verify idempotency on dirty merged config
        re_merged, re_changed, re_diff = merge_config(merged, target, launcher="uvx")
        assert re_changed is False
        assert re_diff == ""
        assert re_merged == merged


class TestAgentDetection:
    """Test agent environment detection logic."""

    def test_detect_windsurf_mock_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "userhome"
        fake_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        ws_dir = fake_home / ".codeium" / "windsurf"
        ws_dir.mkdir(parents=True, exist_ok=True)

        installer = AgentInstaller(project_dir=tmp_path)
        res = installer.detect_agent(get_target("windsurf"))
        assert res.detected is True
        assert res.detected_by == "directory"
        assert res.configured is False

    def test_detect_zed_mock_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_home = tmp_path / "userhome"
        fake_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        zed_cfg_dir = tmp_path / "appdata" / "Zed"
        zed_cfg_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))

        zed_settings = zed_cfg_dir / "settings.json"
        zed_settings.write_text(
            json.dumps(
                {
                    "context_servers": {
                        "studiobridge": {"command": "uvx", "args": ["studiobridge", "mcp"]}
                    }
                }
            ),
            encoding="utf-8",
        )

        installer = AgentInstaller(project_dir=tmp_path)
        res = installer.detect_agent(get_target("zed"))
        assert res.detected is True
        assert res.detected_by == "config_file"
        assert res.configured is True
