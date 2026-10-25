"""Model Context Protocol (MCP) host adapter and JSON-RPC 2.0 protocol router.

Implements spec version negotiation (targeting 2026-07-28 with automatic fallbacks
down to 2025-03-26) and stdio JSON-RPC transport with framework-agnostic tool
dispatch per spec 10_l2_interfaces.md §2.1–§2.3 and [MCP-01..04].
"""

from __future__ import annotations

import enum
import inspect
import json
import logging
import sys
from collections.abc import Callable
from typing import Any, TextIO

import anyio

from studiobridge._version import __version__
from studiobridge.core.errors import ProtocolError, StudioBridgeError
from studiobridge.mcp.instructions import DEFAULT_INSTRUCTIONS

logger = logging.getLogger("studiobridge.mcp.host")

# Supported protocol version strings in descending priority order per [MCP-01]
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = (
    "2026-07-28",
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
)
LATEST_PROTOCOL_VERSION: str = "2026-07-28"
EARLIEST_PROTOCOL_VERSION: str = "2025-03-26"


class JsonRpcErrorCode(enum.IntEnum):
    """Standard JSON-RPC 2.0 and MCP protocol error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_NOT_INITIALIZED = -32002


def negotiate_protocol_version(client_version: str | None) -> str:
    """Negotiate the active MCP protocol version with a connecting client.

    Implements [MCP-01]:
    - Negotiates 2026-07-28 when requested or when client sends a newer version.
    - Automatically falls back to 2025-11-25, 2025-06-18, or 2025-03-26 for older clients.
    - Raises ProtocolError if the client version is missing or below 2025-03-26.
    """
    if not client_version or not isinstance(client_version, str):
        raise ProtocolError(
            f"Missing or invalid protocolVersion: {client_version!r}",
            code="E_PROTOCOL",
            remedy="Client must supply a valid date string (e.g. '2026-07-28')",
        )

    ver = client_version.strip()
    if ver in SUPPORTED_PROTOCOL_VERSIONS:
        return ver

    # If client is newer than our highest supported version, clamp to latest supported
    if ver >= LATEST_PROTOCOL_VERSION:
        return LATEST_PROTOCOL_VERSION

    # For intermediate dates, select highest supported version <= ver
    for supported in SUPPORTED_PROTOCOL_VERSIONS:
        if ver >= supported:
            return supported

    # If older than earliest supported protocol version
    supported_list = ", ".join(SUPPORTED_PROTOCOL_VERSIONS)
    raise ProtocolError(
        f"Unsupported protocol version: {client_version}. Supported versions: {supported_list}",
        code="E_PROTOCOL",
        remedy=f"Upgrade client MCP library to support one of: {supported_list}",
    )


class McpHost:
    """Model Context Protocol (MCP) host adapter.

    Wraps the official Python MCP SDK with automatic fallback to an in-house
    lightweight pure-Python stdio JSON-RPC server per [MCP-03].
    """

    def __init__(
        self,
        server: Any = None,
        adapter: str = "auto",
    ) -> None:
        """Initialize host adapter.

        Args:
            server: Parent StudioMcpServer instance providing toolset registry.
            adapter: Host adapter choice: "auto", "fallback" (pure-Python), or "sdk".
        """
        self.server = server
        self.adapter = adapter
        self.negotiated_version: str | None = None
        self.is_initialized: bool = False
        self.is_ready: bool = False
        self.tools: dict[str, Any] = {}

        if adapter in ("sdk", "official"):
            try:
                import mcp.server  # type: ignore # noqa: F401

                self._adapter_mode = "sdk"
            except ImportError as err:
                raise ImportError(
                    "Official Python MCP SDK ('mcp') is not installed in the current environment"
                ) from err
        else:
            self._adapter_mode = "fallback"

    @property
    def adapter_mode(self) -> str:
        """Return the active adapter implementation name ('fallback' or 'sdk')."""
        return self._adapter_mode

    def negotiate_version(self, client_version: str | None) -> str:
        """Negotiate protocol version string with client."""
        return negotiate_protocol_version(client_version)

    def register_tool(self, tool: Any) -> None:
        """Register a tool definition directly on the host (for standalone use)."""
        name = getattr(tool, "name", str(tool))
        self.tools[name] = tool

    def reset_connection(self) -> None:
        """Reset handshake and initialization status for a new connection transport."""
        self.negotiated_version = None
        self.is_initialized = False
        self.is_ready = False

    def handle_message(self, line: str) -> str | None:
        """Parse and process a single-line JSON-RPC message.

        Returns serialized response string, or None for notifications.
        """
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            err_frame = self._make_error_frame(
                req_id=None,
                code=JsonRpcErrorCode.PARSE_ERROR,
                message=f"Parse error: {exc}",
            )
            return json.dumps(err_frame, ensure_ascii=False)

        response = self.handle_request(payload)
        if response is None:
            return None
        return json.dumps(response, ensure_ascii=False)

    def handle_request(self, req: Any) -> dict[str, Any] | None:
        """Dispatch a deserialized JSON-RPC request and return response dictionary.

        Returns None if the incoming message was a notification (no 'id' field).
        """
        if not isinstance(req, dict):
            return self._make_error_frame(
                req_id=None,
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Invalid Request: payload must be a JSON object",
            )

        # A JSON-RPC notification is defined as a request object without an 'id' member
        is_notification = "id" not in req
        req_id = req.get("id")

        if req.get("jsonrpc") != "2.0":
            if is_notification:
                return None
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Invalid Request: 'jsonrpc' must be '2.0'",
            )

        method = req.get("method")
        if not isinstance(method, str):
            if is_notification:
                return None
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Invalid Request: 'method' must be a string",
            )

        params = req.get("params") or {}

        # 1. initialize
        if method == "initialize":
            if is_notification:
                return None
            return self._handle_initialize(req_id, params)

        # 2. notifications/initialized
        if method == "notifications/initialized":
            self.is_ready = True
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # 3. ping
        if method == "ping":
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # All other methods require initialize to have completed
        if not self.is_initialized:
            if is_notification:
                return None
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Server not initialized. Call 'initialize' first.",
            )

        # 4. tools/list
        if method == "tools/list":
            if is_notification:
                return None
            return self._handle_tools_list(req_id, params)

        # 5. tools/call
        if method == "tools/call":
            if is_notification:
                return None
            return self._handle_tools_call(req_id, params)

        # 6. resources/list
        if method == "resources/list":
            if is_notification:
                return None
            return self._handle_resources_list(req_id, params)

        # 7. resources/templates/list
        if method == "resources/templates/list":
            if is_notification:
                return None
            return self._handle_resources_templates_list(req_id, params)

        # 8. resources/read
        if method == "resources/read":
            if is_notification:
                return None
            return self._handle_resources_read(req_id, params)

        # 9. prompts/list
        if method == "prompts/list":
            if is_notification:
                return None
            return self._handle_prompts_list(req_id, params)

        # 10. prompts/get
        if method == "prompts/get":
            if is_notification:
                return None
            return self._handle_prompts_get(req_id, params)

        # 11. tasks/get
        if method == "tasks/get":
            if is_notification:
                return None
            return self._handle_tasks_get(req_id, params)

        # 12. tasks/cancel
        if method == "tasks/cancel":
            if is_notification:
                return None
            return self._handle_tasks_cancel(req_id, params)

        # 13. tasks/list
        if method == "tasks/list":
            if is_notification:
                return None
            return self._handle_tasks_list(req_id, params)

        # Unknown method
        if is_notification:
            return None
        return self._make_error_frame(
            req_id=req_id,
            code=JsonRpcErrorCode.METHOD_NOT_FOUND,
            message=f"Method not found: '{method}'",
        )

    def _handle_initialize(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'initialize' request and return handshake result or error frame."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        client_version = params.get("protocolVersion")
        try:
            negotiated = self.negotiate_version(client_version)
        except ProtocolError as err:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message=str(err),
                data={"code": err.code, "remedy": err.remedy},
            )

        self.negotiated_version = negotiated
        self.is_initialized = True

        # Capability matrix adapts according to negotiated protocol version per [MCP-01]
        capabilities: dict[str, Any] = {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
            "prompts": {"listChanged": False},
        }

        # Tasks extension capability included for 2026-07-28 spec per 10_l2_interfaces.md §2.1
        if self.negotiated_version == "2026-07-28":
            capabilities["tasks"] = {"listChanged": False}

        server_name = getattr(self.server, "name", "studiobridge")
        server_version = getattr(self.server, "version", __version__)
        instructions = getattr(self.server, "instructions", DEFAULT_INSTRUCTIONS)

        result: dict[str, Any] = {
            "protocolVersion": self.negotiated_version,
            "capabilities": capabilities,
            "serverInfo": {
                "name": server_name,
                "version": server_version,
            },
            "instructions": instructions,
        }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _handle_tools_list(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'tools/list' request and return active tool registrations."""
        if self.server and hasattr(self.server, "get_active_tools"):
            active_tools = self.server.get_active_tools()
        else:
            active_tools = list(self.tools.values())

        formatted_tools = [
            t.to_mcp_dict() if hasattr(t, "to_mcp_dict") else t for t in active_tools
        ]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": formatted_tools},
        }

    def _handle_tools_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'tools/call' request and dispatch to tool handler."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        name = params.get("name")
        if not name or not isinstance(name, str):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'name' is required and must be a string",
            )

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'arguments' must be an object",
            )

        if self.server and hasattr(self.server, "call_tool"):
            tool_res = self.server.call_tool(name, arguments)
        else:
            tool_def = self.tools.get(name)
            if not tool_def:
                tool_res = {
                    "content": [{"type": "text", "text": f"Tool '{name}' not found"}],
                    "isError": True,
                }
            else:
                handler = getattr(tool_def, "handler", None)
                tool_res = self._execute_tool_handler(handler, arguments)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": tool_res,
        }

    def _execute_tool_handler(
        self, handler: Callable[..., Any] | None, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Safely invoke tool handler and package response adhering to MCP conventions."""
        if handler is None:
            return {
                "content": [{"type": "text", "text": "Tool has no registered handler"}],
                "isError": True,
            }

        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())

            # If the handler accepts a single argument named 'args', 'arguments', or 'payload'
            if len(params) == 1 and params[0].name in ("args", "arguments", "payload"):
                if inspect.iscoroutinefunction(handler):
                    res = anyio.run(lambda: handler(arguments))
                else:
                    res = handler(arguments)
            else:
                if inspect.iscoroutinefunction(handler):
                    res = anyio.run(lambda: handler(**arguments))
                else:
                    res = handler(**arguments)
        except StudioBridgeError as err:
            return {
                "content": [{"type": "text", "text": f"Error [{err.code}]: {err}"}],
                "structuredContent": {
                    "code": err.code,
                    "message": str(err),
                    "details": getattr(err, "details", {}),
                    "remedy": getattr(err, "remedy", None),
                },
                "isError": True,
            }
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "structuredContent": {
                    "code": "E_INTERNAL",
                    "message": str(exc),
                },
                "isError": True,
            }

        if hasattr(res, "to_dict"):
            return res.to_dict()
        if isinstance(res, dict) and "content" in res:
            return res
        if isinstance(res, dict):
            return {
                "content": [{"type": "text", "text": json.dumps(res, indent=2, default=str)}],
                "structuredContent": res,
                "isError": False,
            }
        return {
            "content": [{"type": "text", "text": str(res)}],
            "structuredContent": res,
            "isError": False,
        }

    def _handle_resources_list(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'resources/list' request and return registered resources."""
        if self.server and hasattr(self.server, "get_resources"):
            resources = self.server.get_resources()
        else:
            from studiobridge.mcp.resources import get_default_resources

            resources = get_default_resources(server=self.server)

        formatted = [r.to_mcp_dict() if hasattr(r, "to_mcp_dict") else r for r in resources]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": formatted},
        }

    def _handle_resources_templates_list(
        self, req_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Process 'resources/templates/list' request and return registered resource templates."""
        if self.server and hasattr(self.server, "get_resource_templates"):
            templates = self.server.get_resource_templates()
        else:
            from studiobridge.mcp.resources import get_default_resource_templates

            templates = get_default_resource_templates()

        formatted = [t.to_mcp_dict() if hasattr(t, "to_mcp_dict") else t for t in templates]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resourceTemplates": formatted},
        }

    def _handle_resources_read(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'resources/read' request and resolve requested resource URI."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        uri = params.get("uri")
        if not uri or not isinstance(uri, str):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'uri' is required and must be a string",
            )

        try:
            if self.server and hasattr(self.server, "read_resource"):
                content = self.server.read_resource(uri)
            else:
                from studiobridge.mcp.resources import read_resource

                content = read_resource(uri, server=self.server)

            formatted = content.to_mcp_dict() if hasattr(content, "to_mcp_dict") else content
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"contents": [formatted]},
            }
        except ValueError as exc:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message=str(exc),
                data={"code": "E_BADREF", "uri": uri},
            )
        except Exception as exc:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
                message=f"Failed to read resource '{uri}': {exc}",
                data={"code": "E_RESOURCE", "uri": uri},
            )

    def _handle_prompts_list(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'prompts/list' request and return registered prompt templates."""
        if self.server and hasattr(self.server, "get_prompts"):
            prompts = self.server.get_prompts()
        else:
            from studiobridge.mcp.prompts import get_default_prompts

            prompts = get_default_prompts(server=self.server)

        formatted = [p.to_mcp_dict() if hasattr(p, "to_mcp_dict") else p for p in prompts]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"prompts": formatted},
        }

    def _handle_prompts_get(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'prompts/get' request and render prompt template messages."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        name = params.get("name")
        if not name or not isinstance(name, str):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'name' is required and must be a string",
            )

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'arguments' must be an object",
            )

        try:
            if self.server and hasattr(self.server, "get_prompt"):
                res = self.server.get_prompt(name, arguments)
            else:
                from studiobridge.mcp.prompts import get_prompt

                res = get_prompt(name, arguments)

            formatted = res.to_mcp_dict() if hasattr(res, "to_mcp_dict") else res
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": formatted,
            }
        except ValueError as exc:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message=str(exc),
                data={"code": "E_ARGS", "name": name},
            )
        except Exception as exc:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
                message=f"Failed to get prompt '{name}': {exc}",
                data={"code": "E_PROMPT", "name": name},
            )

    def _handle_tasks_get(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'tasks/get' request per MCP Tasks extension (2026-07-28)."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        task_id = params.get("taskId") or params.get("id") or params.get("job_id")
        if not task_id or not isinstance(task_id, str):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'taskId' is required and must be a string",
            )

        from studiobridge.mcp.tools.render import _lookup_job

        data = _lookup_job(task_id)
        if data is None:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message=f"Task '{task_id}' not found.",
                data={"code": "E_BADREF", "taskId": task_id},
            )

        state_val = data.get("state", "running")
        status_map = {
            "done": "completed",
            "failed": "failed",
            "cancelled": "cancelled",
        }
        status_val = status_map.get(state_val, "running")

        task_payload: dict[str, Any] = {
            "id": task_id,
            "status": status_val,
            "state": state_val,
            "output": data.get("output_files", []),
            "metrics": data.get("metrics", {}),
            "error": data.get("error"),
            "created_at": data.get("created_at"),
            "completed_at": data.get("completed_at"),
        }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"task": task_payload},
        }

    def _handle_tasks_cancel(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'tasks/cancel' request per MCP Tasks extension (2026-07-28)."""
        if not isinstance(params, dict):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: params must be an object",
            )

        task_id = params.get("taskId") or params.get("id") or params.get("job_id")
        if not task_id or not isinstance(task_id, str):
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: 'taskId' is required and must be a string",
            )

        from studiobridge.mcp.tools.render import RenderTools

        try:
            tools = RenderTools(server=self.server)
            tools.render_cancel(task_id)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"task": {"id": task_id, "status": "cancelled"}},
            }
        except Exception as exc:
            return self._make_error_frame(
                req_id=req_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
                message=f"Failed to cancel task '{task_id}': {exc}",
                data={"code": "E_TASK_CANCEL", "taskId": task_id},
            )

    def _handle_tasks_list(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Process 'tasks/list' request per MCP Tasks extension (2026-07-28)."""
        from studiobridge.core.paths import get_jobs_dir
        from studiobridge.mcp.tools.render import _lookup_job

        tasks: list[dict[str, Any]] = []
        jobs_dir = get_jobs_dir()
        if jobs_dir.exists():
            for child in sorted(jobs_dir.iterdir(), reverse=True):
                if child.is_dir():
                    data = _lookup_job(child.name)
                    if data:
                        state_val = data.get("state", "running")
                        status_map = {
                            "done": "completed",
                            "failed": "failed",
                            "cancelled": "cancelled",
                        }
                        tasks.append(
                            {
                                "id": child.name,
                                "status": status_map.get(state_val, "running"),
                                "state": state_val,
                                "created_at": data.get("created_at"),
                            }
                        )

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tasks": tasks},
        }

    def _make_error_frame(
        self,
        req_id: Any,
        code: int | JsonRpcErrorCode,
        message: str,
        data: Any = None,
    ) -> dict[str, Any]:
        """Construct a spec-compliant JSON-RPC 2.0 error frame."""
        err_obj: dict[str, Any] = {
            "code": int(code),
            "message": message,
        }
        if data is not None:
            err_obj["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": err_obj,
        }

    def run_stdio(self, reader: TextIO | None = None, writer: TextIO | None = None) -> None:
        """Run synchronous stdio transport loop until EOF."""
        in_stream = reader or sys.stdin
        out_stream = writer or sys.stdout

        for line in in_stream:
            line_clean = line.strip()
            if not line_clean:
                continue
            response_str = self.handle_message(line_clean)
            if response_str is not None:
                out_stream.write(response_str + "\n")
                out_stream.flush()
