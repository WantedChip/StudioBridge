"""Unit tests for StudioBridge Agent Skill installer and CLI commands.

Verifies:
1. Canonical skill bundle discovery, frontmatter parsing, and metadata.
2. Skill installation across all targets (.agents, claude, cursor, codex, gemini, opencode).
3. Project and user scope resolution.
4. AGENTS.md rules snippet injection and idempotency (no duplicate headers).
5. Dry-run mode previews without touching disk.
6. CLI commands: 'sbridge skill info', 'sbridge skill list', 'sbridge skill install'.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.agents.skill import (
    SKILL_NAME,
    SkillInstaller,
    get_skill_target,
    list_skill_targets,
)
from studiobridge.cli.commands.skill import (
    handle_skill_info,
    handle_skill_install,
    handle_skill_list,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project root."""
    proj = tmp_path / "test_project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


class TestSkillMetadataAndTargets:
    """Tests for metadata discovery and supported skill targets."""

    def test_list_and_get_skill_targets(self) -> None:
        """Supported targets list includes .agents, claude, cursor, codex, gemini, opencode."""
        targets = list_skill_targets()
        ids = {t.id for t in targets}
        expected = {".agents", "claude", "cursor", "codex", "gemini", "opencode"}
        assert expected.issubset(ids)

        # Aliases
        assert get_skill_target("claude-code").id == "claude"
        assert get_skill_target("antigravity").id == "gemini"
        assert get_skill_target("agy").id == "gemini"
        assert get_skill_target("agents").id == ".agents"

        with pytest.raises(ValueError, match="Unknown agent skill target"):
            get_skill_target("nonexistent_agent_xyz")

    def test_get_skill_info(self) -> None:
        """Installer discovers source bundle and extracts valid metadata."""
        installer = SkillInstaller()
        info = installer.get_skill_info()

        assert info.name == SKILL_NAME
        assert "FL Studio" in info.description
        assert "SKILL.md" in info.files
        assert "AGENTS.md" in info.files
        assert any(r.startswith("references/") for r in info.references)
        assert len(info.references) >= 4
        assert "StudioBridge Agent Rules" in info.rules_snippet


class TestSkillInstallerExecution:
    """Tests for skill file installation and idempotency."""

    def test_install_default_agents(self, temp_project: Path) -> None:
        """Installs skill bundle to .agents/skills/studiobridge and updates AGENTS.md."""
        installer = SkillInstaller()
        res = installer.install(
            target=".agents",
            scope="project",
            root_dir=temp_project,
        )

        assert res.target == ".agents"
        assert res.scope == "project"
        assert res.dest_dir == temp_project / ".agents" / "skills" / SKILL_NAME
        assert (res.dest_dir / "SKILL.md").is_file()
        assert (res.dest_dir / "references" / "modes.md").is_file()
        assert (res.dest_dir / "references" / "verified_writes.md").is_file()
        assert (res.dest_dir / "references" / "api_search.md").is_file()
        assert (res.dest_dir / "references" / "render_workflows.md").is_file()

        # AGENTS.md created
        agents_md = temp_project / "AGENTS.md"
        assert agents_md.is_file()
        content = agents_md.read_text(encoding="utf-8")
        assert "StudioBridge Agent Rules" in content
        assert "Zero native/compiled dependencies" in content

    def test_install_dry_run_does_not_modify_disk(self, temp_project: Path) -> None:
        """Dry-run returns expected changes without creating any files on disk."""
        installer = SkillInstaller()
        res = installer.install(
            target="cursor",
            scope="project",
            dry_run=True,
            root_dir=temp_project,
        )

        assert res.dry_run is True
        assert len(res.files_written) > 0
        assert not res.dest_dir.exists()
        assert not (temp_project / "AGENTS.md").exists()

    def test_install_idempotency(self, temp_project: Path) -> None:
        """Running install twice writes files once; second run reports 0 written."""
        installer = SkillInstaller()

        # Run 1
        res1 = installer.install(
            target="claude",
            scope="project",
            root_dir=temp_project,
        )
        assert len(res1.files_written) > 0
        assert res1.agents_md_updated is True

        # Run 2
        res2 = installer.install(
            target="claude",
            scope="project",
            root_dir=temp_project,
        )
        assert len(res2.files_written) == 0
        assert len(res2.files_skipped) > 0
        assert res2.agents_md_updated is False

        # Verify AGENTS.md has exactly one rules header
        content = (temp_project / "AGENTS.md").read_text(encoding="utf-8")
        assert content.count("# StudioBridge Agent Rules") == 1

    def test_install_append_to_existing_agents_md(self, temp_project: Path) -> None:
        """If project AGENTS.md exists with other rules, StudioBridge rules are cleanly appended."""
        agents_md = temp_project / "AGENTS.md"
        agents_md.write_text(
            "# Existing Project Rules\n\n- Do not break things.\n",
            encoding="utf-8",
        )

        installer = SkillInstaller()
        res = installer.install(
            target="codex",
            scope="project",
            root_dir=temp_project,
        )
        assert res.agents_md_updated is True

        content = agents_md.read_text(encoding="utf-8")
        assert "# Existing Project Rules" in content
        assert "# StudioBridge Agent Rules" in content

    def test_install_no_rules_flag(self, temp_project: Path) -> None:
        """Passing install_rules=False installs skill but leaves AGENTS.md untouched."""
        installer = SkillInstaller()
        res = installer.install(
            target="gemini",
            scope="project",
            install_rules=False,
            root_dir=temp_project,
        )
        assert res.agents_md_updated is False
        assert not (temp_project / "AGENTS.md").exists()

    def test_install_custom_destination(self, tmp_path: Path) -> None:
        """Custom destination directory writes skill directly into specified folder."""
        custom_dir = tmp_path / "custom_skills_folder" / "studiobridge"
        installer = SkillInstaller()
        res = installer.install(
            dest=custom_dir,
            install_rules=False,
        )
        assert res.dest_dir == custom_dir
        assert (custom_dir / "SKILL.md").is_file()

    def test_list_installed(self, temp_project: Path) -> None:
        """list_installed finds installed skills in project directory."""
        installer = SkillInstaller()
        assert len(installer.list_installed(scope="project", root_dir=temp_project)) == 0

        installer.install(target=".agents", scope="project", root_dir=temp_project)
        installer.install(target="cursor", scope="project", root_dir=temp_project)

        installed = installer.list_installed(scope="project", root_dir=temp_project)
        targets = {item.target for item in installed}
        assert targets == {".agents", "cursor"}
        for item in installed:
            assert item.valid is True
            assert item.file_count >= 5


class TestSkillCLICommands:
    """Tests for CLI handlers: sbridge skill info, list, install."""

    def test_cli_skill_info_text_and_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge skill info prints valid text and machine-readable JSON."""
        installer = SkillInstaller()

        # Text
        args_text = type("Args", (), {"json": False})()
        code = handle_skill_info(installer, args_text)  # type: ignore[arg-type]
        assert code == 0
        captured = capsys.readouterr().out
        assert "Skill:       studiobridge" in captured

        # JSON
        args_json = type("Args", (), {"json": True})()
        code_json = handle_skill_info(installer, args_json)  # type: ignore[arg-type]
        assert code_json == 0
        data = json.loads(capsys.readouterr().out)
        assert data["name"] == "studiobridge"
        assert len(data["files"]) >= 5

    def test_cli_skill_install_and_list_json(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sbridge skill install and list work cleanly with --json."""
        installer = SkillInstaller()

        # 1. Install via CLI handler
        args_inst = type(
            "Args",
            (),
            {
                "agent": ".agents",
                "scope": "project",
                "dest": str(temp_project / ".agents" / "skills" / "studiobridge"),
                "dry_run": False,
                "rules": True,
                "force": False,
                "json": True,
            },
        )()
        code_inst = handle_skill_install(installer, args_inst)  # type: ignore[arg-type]
        assert code_inst == 0
        inst_out = json.loads(capsys.readouterr().out)
        assert inst_out["status"] == "ok"
        assert len(inst_out["installations"]) == 1

        # 2. List via CLI handler
        args_list = type("Args", (), {"scope": "all", "json": True})()
        code_list = handle_skill_list(installer, args_list)  # type: ignore[arg-type]
        assert code_list == 0
        list_out = json.loads(capsys.readouterr().out)
        assert isinstance(list_out, list)
