"""Agent skill installers and integrations.

Provides automated MCP configuration installer, detection, templates, and golden tests
per spec 10_l2_interfaces.md §5 and requirements [AGT-01] through [AGT-04].
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

__all__ = [
    "PROJECT_SCOPE_SECURITY_WARNING",
    "AgentInstaller",
    "AgentTarget",
    "DetectResult",
    "InstallResult",
    "VerifyResult",
    "get_target",
    "list_targets",
    "merge_config",
    "render_server_entry",
    "render_snippet",
    "strip_jsonc_comments_and_trailing_commas",
    "validate_zero_secrets",
]
