"""CLI command handler for 'sbridge mcp'.

Runs the StudioBridge Model Context Protocol server over stdio transport
per spec 10_l2_interfaces.md §2.1–§2.3 and §3.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from studiobridge.core.logging import setup_logging
from studiobridge.mcp.server import StudioMcpServer

logger = logging.getLogger("studiobridge.cli.mcp")

# Standard exit codes per spec 10_l2_interfaces.md §3
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def handle_mcp(args: argparse.Namespace) -> int:
    """Run the StudioBridge MCP server over stdio transport."""
    # Enforce logging to stderr to prevent corrupting the stdio JSON-RPC stream
    setup_logging(log_level="INFO", stream=sys.stderr)

    toolsets_arg = getattr(args, "toolsets", None)
    adapter_arg = getattr(args, "adapter", "auto")
    is_dry_run = getattr(args, "dry_run", False)
    is_check = getattr(args, "check", False)
    use_json = getattr(args, "json", False)

    try:
        server = StudioMcpServer(toolsets=toolsets_arg, adapter=adapter_arg)
    except ValueError as exc:
        if use_json:
            print(json.dumps({"status": "error", "code": "E_USAGE", "message": str(exc)}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if is_check:
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "sbridge-check", "version": "1.0"},
            },
        }
        init_res = server.host.handle_request(init_req)
        if not init_res or "error" in init_res:
            err_msg = (init_res or {}).get("error", {}).get("message", "Handshake failed")
            if use_json:
                print(json.dumps({"status": "error", "code": "E_INTERNAL", "message": err_msg}))
            else:
                print(f"Error: MCP initialize failed: {err_msg}", file=sys.stderr)
            return EXIT_ERROR

        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_res = server.host.handle_request(tools_req)
        if not tools_res or "error" in tools_res:
            err_msg = (tools_res or {}).get("error", {}).get("message", "Tools list failed")
            if use_json:
                print(json.dumps({"status": "error", "code": "E_INTERNAL", "message": err_msg}))
            else:
                print(f"Error: MCP tools/list failed: {err_msg}", file=sys.stderr)
            return EXIT_ERROR

        tools_list = (tools_res or {}).get("result", {}).get("tools", [])
        tools_count = len(tools_list)
        active = sorted(server.active_toolsets)

        if use_json:
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "check": "passed",
                        "tools_count": tools_count,
                        "active_toolsets": active,
                        "adapter": server.host.adapter_mode,
                        "protocol_version": (init_res or {})
                        .get("result", {})
                        .get("protocolVersion"),
                    },
                    indent=2,
                )
            )
        else:
            active_str = ", ".join(active)
            print(
                f"MCP check passed: {tools_count} tools registered across toolsets: "
                f"{active_str} (adapter: {server.host.adapter_mode})"
            )
        return EXIT_OK

    if is_dry_run:
        active = sorted(server.active_toolsets)
        if use_json:
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "active_toolsets": active,
                        "adapter": server.host.adapter_mode,
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"MCP server dry-run OK. Active toolsets ({len(active)}): {', '.join(active)}",
                file=sys.stderr,
            )
        return EXIT_OK

    try:
        server.run_stdio()
        return EXIT_OK
    except KeyboardInterrupt:
        return EXIT_OK
    except Exception as exc:
        logger.exception("MCP server encountered fatal error: %s", exc)
        if use_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_INTERNAL",
                        "message": str(exc),
                    }
                )
            )
        return EXIT_ERROR
