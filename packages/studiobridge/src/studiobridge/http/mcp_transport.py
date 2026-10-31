"""Streamable HTTP transport adapter for Model Context Protocol (MCP) clients.

Enables MCP clients to connect over local HTTP (POST /mcp) using JSON-RPC 2.0
with support for both application/json and text/event-stream responses.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from studiobridge.mcp.host import JsonRpcErrorCode
from studiobridge.mcp.server import StudioMcpServer

logger = logging.getLogger("studiobridge.http.mcp")


class StreamableMcpTransport:
    """Streamable HTTP transport adapter bridging HTTP requests to MCP host router."""

    def __init__(
        self,
        mcp_server: StudioMcpServer | None = None,
        toolsets: str | None = None,
    ) -> None:
        """Initialize Streamable HTTP MCP adapter.

        Args:
            mcp_server: Optional pre-configured StudioMcpServer instance.
            toolsets: Optional toolset configuration if creating internal server.
        """
        self.mcp_server: StudioMcpServer = (
            mcp_server if mcp_server is not None else StudioMcpServer(toolsets=toolsets)
        )

    def _auto_initialize_if_needed(self, payload: dict[str, Any]) -> None:
        """Auto-initialize MCP host if client sends stateless direct requests."""
        if self.mcp_server.host.is_initialized:
            return

        method = payload.get("method")
        # If client explicitly sends initialize, let host handle it normally
        if method == "initialize":
            return

        # Pre-initialize with latest protocol version for seamless stateless calls
        logger.debug("Auto-initializing MCP host for stateless Streamable HTTP request")
        init_frame = {
            "jsonrpc": "2.0",
            "id": "_http_auto_init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "streamable-http-client", "version": "1.0"},
            },
        }
        self.mcp_server.host.handle_request(init_frame)
        self.mcp_server.host.is_ready = True

    def handle_request(
        self,
        body_bytes: bytes,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Dispatch an incoming HTTP POST /mcp request.

        Args:
            body_bytes: Raw HTTP request body bytes.
            headers: Case-insensitive dictionary of HTTP request headers.

        Returns:
            Tuple of (status_code, response_headers, body_bytes).
        """
        if not body_bytes:
            err_frame = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": JsonRpcErrorCode.INVALID_REQUEST,
                    "message": "Empty request body.",
                },
            }
            return (
                400,
                {"Content-Type": "application/json"},
                json.dumps(err_frame).encode("utf-8"),
            )

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            err_frame = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": JsonRpcErrorCode.PARSE_ERROR,
                    "message": f"Parse error: {exc}",
                },
            }
            return (
                400,
                {"Content-Type": "application/json"},
                json.dumps(err_frame).encode("utf-8"),
            )

        # 1. Batch JSON-RPC request handling
        if isinstance(payload, list):
            responses: list[dict[str, Any]] = []
            for item in payload:
                if isinstance(item, dict):
                    self._auto_initialize_if_needed(item)
                    res = self.mcp_server.host.handle_request(item)
                    if res is not None:
                        responses.append(res)
            if not responses:
                # All were notifications
                return 204, {}, b""
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(responses, ensure_ascii=False).encode("utf-8"),
            )

        # 2. Single JSON-RPC request handling
        if isinstance(payload, dict):
            self._auto_initialize_if_needed(payload)
            response = self.mcp_server.host.handle_request(payload)

            if response is None:
                # Notification acknowledged
                return 204, {}, b""

            accept_hdr = headers.get("accept", "").lower()
            if "text/event-stream" in accept_hdr:
                sse_payload = (
                    f"event: message\ndata: {json.dumps(response, ensure_ascii=False)}\n\n"
                )
                return (
                    200,
                    {
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                    sse_payload.encode("utf-8"),
                )

            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(response, ensure_ascii=False).encode("utf-8"),
            )

        # Payload is not object or array
        invalid_frame = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": JsonRpcErrorCode.INVALID_REQUEST,
                "message": "Payload must be a JSON object or array.",
            },
        }
        return (
            400,
            {"Content-Type": "application/json"},
            json.dumps(invalid_frame).encode("utf-8"),
        )
