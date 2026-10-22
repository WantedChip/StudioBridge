"""Agent skill installer and distribution engine.

Implements canonical StudioBridge Agent Skill (`SKILL.md`) installation across
project and user-level agent directories per spec 10_l2_interfaces.md §6 and [SKL-01].
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Default skill bundle name
SKILL_NAME: Final[str] = "studiobridge"

# Markers used to identify StudioBridge rules in AGENTS.md
RULES_HEADER_MARKER: Final[str] = "# StudioBridge Agent Rules"
RULES_KEYWORD_MARKER: Final[str] = "StudioBridge Agent Rules"


@dataclass(frozen=True)
class SkillTarget:
    """Target agent/IDE definition for skill installation."""

    id: str
    display_name: str
    project_skills_rel: Path
    user_skills_dir: Path
    aliases: tuple[str, ...] = ()

    def matches(self, name: str) -> bool:
        """Check if target matches id or any alias."""
        clean = name.strip().lower()
        if clean == self.id.lower() or clean == self.display_name.lower():
            return True
        return clean in [a.lower() for a in self.aliases]


# Standard agent skill targets per spec 10_l2_interfaces.md §6
SKILL_TARGETS: Final[tuple[SkillTarget, ...]] = (
    SkillTarget(
        id=".agents",
        display_name="Agent Skills (Standard)",
        project_skills_rel=Path(".agents/skills"),
        user_skills_dir=Path.home() / ".agents" / "skills",
        aliases=("agents", "standard", "default"),
    ),
    SkillTarget(
        id="claude",
        display_name="Claude Code",
        project_skills_rel=Path(".claude/skills"),
        user_skills_dir=Path.home() / ".claude" / "skills",
        aliases=("claude-code", "claude_code", "claude-desktop"),
    ),
    SkillTarget(
        id="cursor",
        display_name="Cursor",
        project_skills_rel=Path(".cursor/skills"),
        user_skills_dir=Path.home() / ".cursor" / "skills",
        aliases=("cursor-ide",),
    ),
    SkillTarget(
        id="codex",
        display_name="Codex",
        project_skills_rel=Path(".codex/skills"),
        user_skills_dir=Path.home() / ".codex" / "skills",
        aliases=("codex-cli",),
    ),
    SkillTarget(
        id="gemini",
        display_name="Gemini CLI / Antigravity",
        project_skills_rel=Path(".gemini/skills"),
        user_skills_dir=Path.home() / ".gemini" / "skills",
        aliases=("antigravity", "agy", "google-antigravity", "gemini-cli"),
    ),
    SkillTarget(
        id="opencode",
        display_name="opencode",
        project_skills_rel=Path(".opencode/skills"),
        user_skills_dir=Path.home() / ".config" / "opencode" / "skills",
        aliases=("open-code",),
    ),
)


def list_skill_targets() -> Sequence[SkillTarget]:
    """Return all supported skill targets."""
    return SKILL_TARGETS


def get_skill_target(name: str) -> SkillTarget:
    """Retrieve SkillTarget by id or alias."""
    clean = name.strip().lower()
    for t in SKILL_TARGETS:
        if t.matches(clean):
            return t
    valid = ", ".join(t.id for t in SKILL_TARGETS)
    raise ValueError(f"Unknown agent skill target '{name}'. Valid targets: {valid}, or 'all'")


@dataclass(frozen=True)
class SkillMetadata:
    """Metadata describing the StudioBridge agent skill."""

    name: str
    description: str
    version: str
    source_dir: Path
    files: tuple[str, ...]
    references: tuple[str, ...]
    rules_snippet: str


@dataclass(frozen=True)
class SkillInstallResult:
    """Outcome of a skill installation operation."""

    target: str
    scope: str
    dest_dir: Path
    files_written: tuple[Path, ...]
    files_skipped: tuple[Path, ...]
    agents_md_path: Path | None
    agents_md_updated: bool
    dry_run: bool
    message: str = ""

    @property
    def has_changes(self) -> bool:
        """True if any file was written or AGENTS.md was updated."""
        return bool(self.files_written) or self.agents_md_updated


@dataclass(frozen=True)
class InstalledSkillInfo:
    """Information regarding an installed skill on disk."""

    target: str
    scope: str
    path: Path
    valid: bool
    file_count: int
    has_rules: bool


class SkillInstaller:
    """Manages discovery, inspection, and installation of the StudioBridge skill bundle."""

    def __init__(self, source_dir: Path | str | None = None) -> None:
        """Initialize installer, resolving canonical skill source directory."""
        if source_dir is not None:
            self._source_dir = Path(source_dir).resolve()
        else:
            self._source_dir = self._resolve_source_dir()

    @property
    def source_dir(self) -> Path:
        """Resolved source directory containing canonical skill assets."""
        return self._source_dir

    @staticmethod
    def _resolve_source_dir() -> Path:
        """Locate canonical skill directory across repo and package bundle."""
        # 1. Check relative to this module in package bundle
        pkg_bundle = Path(__file__).parent / "bundle" / SKILL_NAME
        if (pkg_bundle / "SKILL.md").is_file():
            return pkg_bundle.resolve()

        # 2. Check repo root / skills / studiobridge
        # Walk up from this file to find repo root (containing pyproject.toml)
        curr = Path(__file__).resolve().parent
        for _ in range(6):
            candidate = curr / "skills" / SKILL_NAME
            if (candidate / "SKILL.md").is_file():
                return candidate.resolve()
            if (curr / "pyproject.toml").is_file():
                candidate = curr / "skills" / SKILL_NAME
                if candidate.exists():
                    return candidate.resolve()
            curr = curr.parent

        # 3. Check current working directory
        cwd_candidate = Path.cwd() / "skills" / SKILL_NAME
        if (cwd_candidate / "SKILL.md").is_file():
            return cwd_candidate.resolve()

        # Return fallback bundle path even if missing (will be handled gracefully)
        return pkg_bundle.resolve()

    def get_skill_info(self) -> SkillMetadata:
        """Inspect and parse metadata from the source skill bundle."""
        skill_file = self._source_dir / "SKILL.md"
        name = SKILL_NAME
        description = "Control, inspect, and automate Image-Line FL Studio via StudioBridge"
        version = "0.3.5"

        if skill_file.is_file():
            content = skill_file.read_text(encoding="utf-8")
            # Parse YAML frontmatter if present
            fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
                if name_match:
                    name = name_match.group(1).strip()
                desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
                if desc_match:
                    description = desc_match.group(1).strip()

        # Collect files
        all_files: list[str] = []
        references: list[str] = []
        if self._source_dir.is_dir():
            for p in sorted(self._source_dir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(self._source_dir).as_posix()
                    all_files.append(rel)
                    if rel.startswith("references/"):
                        references.append(rel)

        # Load AGENTS.md rules snippet
        rules_snippet = self.get_rules_snippet()

        return SkillMetadata(
            name=name,
            description=description,
            version=version,
            source_dir=self._source_dir,
            files=tuple(all_files),
            references=tuple(references),
            rules_snippet=rules_snippet,
        )

    def get_rules_snippet(self) -> str:
        """Return the 10 hard rules snippet for coding agents."""
        agents_file = self._source_dir / "AGENTS.md"
        if agents_file.is_file():
            return agents_file.read_text(encoding="utf-8").strip()

        # Built-in fallback
        return (
            "# StudioBridge Agent Rules\n\n"
            "When developing or interacting with StudioBridge and FL Studio projects, "
            "all coding agents MUST adhere to these 10 hard rules:\n\n"
            "1. **Zero native/compiled dependencies on Windows**: Runtime dependencies must "
            "provide universal pure-Python wheels or both win_amd64 and win_arm64 binary wheels.\n"
            "2. **Device-script sandbox rules**: Any code executing inside FL Studio's controller "
            "script context (device/assets/*) MUST be Python 3.9-compatible and import ONLY "
            "standard builtin modules and sibling script files.\n"
            "3. **Clean-room provenance**: Never copy, decompile, or port code from GPL projects. "
            "Format facts and protocol specifications come from clean-room documentation and "
            "hardware corpus experiments.\n"
            "4. **Third-party driver safety**: Never bundle, distribute, or require proprietary "
            "kernel-mode virtual MIDI drivers. Primary Windows routing uses Windows MIDI Services "
            "(WMS) loopback.\n"
            "5. **Verified, reversible writes**: Writes to FL state must be verified with "
            "read-back comparison, recorded in the mutation journal, and default to read-only "
            "session mode. Always create a checkpoint before mutations.\n"
            "6. **Token-based branding**: Centralize brand strings using the token table "
            "(studiobridge, sbridge, SBridge).\n"
            "7. **Tests first**: Reference requirement IDs in test comments. Cover edge cases, "
            "timeouts, and error paths.\n"
            "8. **Capability honesty**: If real FL Studio behavior is unknown or unverified, "
            "gate behind a capability flag; do not guess or hallucinate API behavior.\n"
            "9. **Strict typing and validation**: Keep public APIs fully typed. Enforce linting "
            "with ruff, type-checking with pyright, and module layering with import-linter.\n"
            "10. **Concise reporting**: Output short summaries of operations including "
            "verification receipts, journal IDs, safety modes, and remedies for any failure."
        )

    def resolve_destination(
        self,
        target_name: str = ".agents",
        scope: str = "project",
        dest: Path | str | None = None,
        root_dir: Path | None = None,
    ) -> tuple[SkillTarget | None, Path]:
        """Resolve the target directory where the skill folder should be installed."""
        if dest is not None:
            resolved_dest = Path(dest).resolve()
            if resolved_dest.name != SKILL_NAME:
                resolved_dest = resolved_dest / SKILL_NAME
            return None, resolved_dest

        target = get_skill_target(target_name)
        root = Path(root_dir) if root_dir is not None else Path.cwd()

        if scope.lower() == "user":
            dest_dir = target.user_skills_dir / SKILL_NAME
        else:
            dest_dir = root / target.project_skills_rel / SKILL_NAME

        return target, dest_dir.resolve()

    def install(
        self,
        target: str = ".agents",
        scope: str = "project",
        dest: Path | str | None = None,
        dry_run: bool = False,
        install_rules: bool = True,
        force: bool = False,
        root_dir: Path | None = None,
    ) -> SkillInstallResult:
        """Install the StudioBridge agent skill bundle to the target destination."""
        project_root = Path(root_dir) if root_dir is not None else Path.cwd()
        target_obj, dest_dir = self.resolve_destination(
            target_name=target,
            scope=scope,
            dest=dest,
            root_dir=project_root,
        )

        target_id = target_obj.id if target_obj is not None else "custom"

        if not self._source_dir.is_dir():
            raise FileNotFoundError(
                f"StudioBridge skill source directory not found at: {self._source_dir}"
            )

        files_written: list[Path] = []
        files_skipped: list[Path] = []

        # Find all files in source directory
        source_files = [p for p in self._source_dir.rglob("*") if p.is_file()]
        if not source_files:
            raise FileNotFoundError(f"No skill files found in source directory: {self._source_dir}")

        for src_file in source_files:
            rel = src_file.relative_to(self._source_dir)
            target_file = dest_dir / rel

            src_content = src_file.read_bytes()
            needs_write = True

            if target_file.is_file() and not force:
                existing_content = target_file.read_bytes()
                if existing_content == src_content:
                    needs_write = False

            if needs_write:
                files_written.append(target_file)
                if not dry_run:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(src_content)
            else:
                files_skipped.append(target_file)

        # Handle AGENTS.md rules snippet installation
        agents_md_path: Path | None = None
        agents_md_updated = False

        if install_rules:
            # Determine target AGENTS.md location
            if scope.lower() == "project" or dest is None:
                agents_md_path = project_root / "AGENTS.md"
            else:
                agents_md_path = dest_dir.parent.parent / "AGENTS.md"

            snippet = self.get_rules_snippet()

            if agents_md_path.is_file():
                current_text = agents_md_path.read_text(encoding="utf-8")
                has_rules = (
                    RULES_HEADER_MARKER in current_text or RULES_KEYWORD_MARKER in current_text
                )
                if not has_rules:
                    agents_md_updated = True
                    new_text = current_text.rstrip() + "\n\n" + snippet + "\n"
                    if not dry_run:
                        agents_md_path.write_text(new_text, encoding="utf-8")
                elif force:
                    agents_md_updated = True
                    if not dry_run:
                        # Replace existing rules block or rewrite
                        agents_md_path.write_text(snippet + "\n", encoding="utf-8")
            else:
                agents_md_updated = True
                if not dry_run:
                    agents_md_path.parent.mkdir(parents=True, exist_ok=True)
                    agents_md_path.write_text(snippet + "\n", encoding="utf-8")

        action_desc = "Would install" if dry_run else "Installed"
        msg = (
            f"{action_desc} skill '{SKILL_NAME}' to {dest_dir} "
            f"({len(files_written)} written, {len(files_skipped)} unchanged)."
        )
        if agents_md_updated:
            msg += f" Updated rules in {agents_md_path}."

        return SkillInstallResult(
            target=target_id,
            scope=scope,
            dest_dir=dest_dir,
            files_written=tuple(files_written),
            files_skipped=tuple(files_skipped),
            agents_md_path=agents_md_path,
            agents_md_updated=agents_md_updated,
            dry_run=dry_run,
            message=msg,
        )

    def list_installed(
        self,
        scope: str = "all",
        root_dir: Path | None = None,
    ) -> list[InstalledSkillInfo]:
        """Scan project and user directories for existing skill installations."""
        root = Path(root_dir) if root_dir is not None else Path.cwd()
        results: list[InstalledSkillInfo] = []

        scopes_to_check = ["project", "user"] if scope == "all" else [scope.lower()]

        for target in SKILL_TARGETS:
            for s in scopes_to_check:
                if s == "project":
                    skill_dir = root / target.project_skills_rel / SKILL_NAME
                else:
                    skill_dir = target.user_skills_dir / SKILL_NAME

                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    valid = skill_md.is_file()
                    files = [f for f in skill_dir.rglob("*") if f.is_file()]
                    has_rules = (skill_dir / "AGENTS.md").is_file() or (
                        root / "AGENTS.md"
                    ).is_file()

                    results.append(
                        InstalledSkillInfo(
                            target=target.id,
                            scope=s,
                            path=skill_dir,
                            valid=valid,
                            file_count=len(files),
                            has_rules=has_rules,
                        )
                    )

        return results


__all__ = [
    "InstalledSkillInfo",
    "RULES_HEADER_MARKER",
    "RULES_KEYWORD_MARKER",
    "SKILL_NAME",
    "SKILL_TARGETS",
    "SkillInstallResult",
    "SkillInstaller",
    "SkillMetadata",
    "SkillTarget",
    "get_skill_target",
    "list_skill_targets",
]
