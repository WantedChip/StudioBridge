"""Model Context Protocol (MCP) server foundation and toolset registry.

Provides the StudioMcpServer runtime, framework-agnostic ToolDefinition and
ToolResult structures, and toolset filtering per spec 10_l2_interfaces.md §2.1–§2.4
and [MCP-04, MCP-11].
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TextIO

from studiobridge._version import __version__
from studiobridge.mcp.host import DEFAULT_INSTRUCTIONS, McpHost

# All recognized toolset identifiers per spec 10_l2_interfaces.md §2.2
VALID_TOOLSETS: frozenset[str] = frozenset(
    {
        "core",
        "inspect",
        "control",
        "notes",
        "safety",
        "render",
        "flp",
        "unsafe",
        "raw",
    }
)

# Default active toolset selection (≈33 tools) per [MCP-11]
DEFAULT_TOOLSETS: frozenset[str] = frozenset(
    {
        "core",
        "inspect",
        "control",
        "notes",
        "safety",
        "render",
    }
)

MCP_SERVER_INSTRUCTIONS: str = DEFAULT_INSTRUCTIONS


@dataclass(frozen=True)
class ToolDefinition:
    """Framework-agnostic tool definition adhering to Model Context Protocol."""

    name: str
    description: str
    input_schema: dict[str, Any]
    toolset: str = "core"
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = False
    open_world: bool = False
    title: str | None = None
    handler: Callable[..., Any] | None = None

    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize tool definition into standard MCP tools/list structure."""
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": self.read_only,
                "destructiveHint": self.destructive,
                "idempotentHint": self.idempotent,
                "openWorldHint": self.open_world,
            },
        }
        if self.title:
            out["title"] = self.title
        return out


@dataclass(frozen=True)
class ToolResult:
    """Standardized tool execution result."""

    content: list[dict[str, Any]] = field(default_factory=list)
    structured_content: Any = None
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize tool result for JSON-RPC transmission."""
        res: dict[str, Any] = {
            "content": self.content,
            "isError": self.is_error,
        }
        if self.structured_content is not None:
            res["structuredContent"] = self.structured_content
        return res


def parse_toolsets(
    toolsets_arg: str | Sequence[str] | set[str] | frozenset[str] | None = None,
) -> frozenset[str]:
    """Parse, normalize, and validate toolsets from arguments or environment variable.

    Resolves against SBRIDGE_TOOLSETS if toolsets_arg is None.
    Applies the alias relationship between 'raw' and 'unsafe'.
    """
    if toolsets_arg is None:
        env_val = os.environ.get("SBRIDGE_TOOLSETS")
        if env_val:
            toolset_tokens = [t.strip().lower() for t in env_val.split(",") if t.strip()]
        else:
            return DEFAULT_TOOLSETS
    elif isinstance(toolsets_arg, str):
        toolset_tokens = [t.strip().lower() for t in toolsets_arg.split(",") if t.strip()]
    else:
        toolset_tokens = [str(t).strip().lower() for t in toolsets_arg if str(t).strip()]

    selected = set(toolset_tokens)

    # Validate against known toolsets
    unknown = selected - VALID_TOOLSETS
    if unknown:
        valid_sorted = ", ".join(sorted(VALID_TOOLSETS))
        unknown_sorted = ", ".join(sorted(unknown))
        raise ValueError(
            f"Invalid toolset(s): {unknown_sorted}. Valid toolsets are: {valid_sorted}"
        )

    # Meta mode and unsafe/raw aliasing per spec 10_l2_interfaces.md §2.2
    if "raw" in selected:
        selected.add("unsafe")
    if "unsafe" in selected:
        selected.add("raw")

    return frozenset(selected)


class StudioMcpServer:
    """Model Context Protocol server for StudioBridge.

    Enforces zero per-connection volatile state [MCP-04]:
    The server holds no active transactions, connection leases, or mutation logs
    in memory. All state and session lifecycles are backed by the broker and SDK.
    """

    def __init__(
        self,
        toolsets: str | Sequence[str] | set[str] | frozenset[str] | None = None,
        adapter: str = "auto",
        name: str = "studiobridge",
        version: str | None = None,
        instructions: str | None = None,
        client: Any = None,
    ) -> None:
        """Initialize MCP server with specified toolsets and adapter.

        Args:
            toolsets: Filter selection of active toolsets (e.g. 'core,inspect').
            adapter: Transport adapter ('auto', 'fallback', or 'sdk').
            name: Server name reported in handshake.
            version: Server version reported in handshake.
            instructions: System guidance string reported in handshake.
            client: Optional Studio SDK client instance.
        """
        self.active_toolsets: frozenset[str] = parse_toolsets(toolsets)
        self.name: str = name
        self.version: str = version or __version__
        self.instructions: str = instructions or MCP_SERVER_INSTRUCTIONS
        self.client = client
        self._tools: dict[str, ToolDefinition] = {}

        # Register built-in tool suites (core and inspect)
        self._register_default_tools()

        # Instantiate McpHost adapter
        self.host = McpHost(server=self, adapter=adapter)

    def _register_default_tools(self) -> None:
        """Register built-in tool definitions for standard toolsets."""
        from studiobridge.mcp.tools.core import get_core_tools
        from studiobridge.mcp.tools.inspect import get_inspect_tools

        for tool in get_core_tools(client=self.client, server=self):
            self.register_tool(tool)
        for tool in get_inspect_tools(client=self.client, server=self):
            self.register_tool(tool)

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool definition in the server catalog."""
        self._tools[tool.name] = tool

    def get_active_tools(self) -> list[ToolDefinition]:
        """Return registered tools enabled by the current active toolset filter."""
        return [t for t in self._tools.values() if t.toolset in self.active_toolsets]

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Retrieve active tool definition by name, or None if missing or disabled."""
        tool = self._tools.get(name)
        if tool is not None and tool.toolset in self.active_toolsets:
            return tool
        return None

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call against the server's registered tools."""
        tool = self._tools.get(name)
        if tool is None:
            return {
                "content": [{"type": "text", "text": f"Tool '{name}' not found."}],
                "isError": True,
            }

        if tool.toolset not in self.active_toolsets:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Tool '{name}' belongs to disabled toolset '{tool.toolset}'. "
                            f"Active toolsets: {', '.join(sorted(self.active_toolsets))}. "
                            "Enable via --toolsets or SBRIDGE_TOOLSETS."
                        ),
                    }
                ],
                "isError": True,
            }

        return self.host._execute_tool_handler(tool.handler, arguments)

    def run_stdio(self, reader: TextIO | None = None, writer: TextIO | None = None) -> None:
        """Start the stdio JSON-RPC transport loop."""
        self.host.run_stdio(reader=reader, writer=writer)
