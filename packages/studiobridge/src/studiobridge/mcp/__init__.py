"""Model Context Protocol (MCP) server implementation for AI agents."""

from __future__ import annotations

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

__all__ = [
    "DEFAULT_INSTRUCTIONS",
    "DEFAULT_TOOLSETS",
    "EARLIEST_PROTOCOL_VERSION",
    "JsonRpcErrorCode",
    "LATEST_PROTOCOL_VERSION",
    "McpHost",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "StudioMcpServer",
    "ToolDefinition",
    "ToolResult",
    "VALID_TOOLSETS",
    "negotiate_protocol_version",
    "parse_toolsets",
]
