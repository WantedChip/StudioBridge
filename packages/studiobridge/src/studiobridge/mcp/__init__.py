"""Model Context Protocol (MCP) server implementation for AI agents."""

from __future__ import annotations

from studiobridge.mcp.confirmation import ConfirmationManager
from studiobridge.mcp.host import (
    DEFAULT_INSTRUCTIONS,
    EARLIEST_PROTOCOL_VERSION,
    LATEST_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    JsonRpcErrorCode,
    McpHost,
    negotiate_protocol_version,
)
from studiobridge.mcp.server import (
    DEFAULT_TOOLSETS,
    VALID_TOOLSETS,
    StudioMcpServer,
    ToolDefinition,
    ToolResult,
    parse_toolsets,
)
from studiobridge.mcp.tools import (
    ControlTools,
    CoreTools,
    InspectTools,
    SafetyTools,
    get_control_tools,
    get_core_tools,
    get_inspect_tools,
    get_raw_tools,
    get_safety_tools,
)

__all__ = [
    "ConfirmationManager",
    "ControlTools",
    "CoreTools",
    "DEFAULT_INSTRUCTIONS",
    "DEFAULT_TOOLSETS",
    "EARLIEST_PROTOCOL_VERSION",
    "InspectTools",
    "JsonRpcErrorCode",
    "LATEST_PROTOCOL_VERSION",
    "McpHost",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "SafetyTools",
    "StudioMcpServer",
    "ToolDefinition",
    "ToolResult",
    "VALID_TOOLSETS",
    "get_control_tools",
    "get_core_tools",
    "get_inspect_tools",
    "get_raw_tools",
    "get_safety_tools",
    "negotiate_protocol_version",
    "parse_toolsets",
]
