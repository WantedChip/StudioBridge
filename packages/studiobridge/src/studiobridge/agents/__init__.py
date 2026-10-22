"""Agent skill installers and integrations.

Provides automated MCP configuration installer, detection, templates, golden tests,
and agent skill package management per spec 10_l2_interfaces.md §5, §6 and [AGT-01..04, SKL-01].
"""

from __future__ import annotations

from studiobridge.agents.installer import (
    PROJECT_SCOPE_SECURITY_WARNING,
    AgentInstaller,
    AgentTarget,
    DetectResult,
    InstallResult,
    VerifyResult,
    get_target,
    list_targets,
    merge_config,
    render_server_entry,
    render_snippet,
    strip_jsonc_comments_and_trailing_commas,
    validate_zero_secrets,
)
from studiobridge.agents.skill import (
    SKILL_NAME,
    SKILL_TARGETS,
    InstalledSkillInfo,
    SkillInstaller,
    SkillInstallResult,
    SkillMetadata,
    SkillTarget,
    get_skill_target,
    list_skill_targets,
)

__all__ = [
    "PROJECT_SCOPE_SECURITY_WARNING",
    "AgentInstaller",
    "AgentTarget",
    "DetectResult",
    "InstallResult",
    "InstalledSkillInfo",
    "SKILL_NAME",
    "SKILL_TARGETS",
    "SkillInstallResult",
    "SkillInstaller",
    "SkillMetadata",
    "SkillTarget",
    "VerifyResult",
    "get_skill_target",
    "get_target",
    "list_skill_targets",
    "list_targets",
    "merge_config",
    "render_server_entry",
    "render_snippet",
    "strip_jsonc_comments_and_trailing_commas",
    "validate_zero_secrets",
]
