"""Implementation of 'sbridge serve' command.

Starts the local HTTP REST and Streamable HTTP MCP server on the loopback interface.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any

from studiobridge.core.logging import setup_logging
from studiobridge.core.paths import get_broker_token_path
from studiobridge.http.server import HttpServer

logger = logging.getLogger("studiobridge.cli.serve")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

_DEFAULT_CLIENT: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client instance for testing or embedded use."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def handle_serve(args: argparse.Namespace) -> int:
    """Handle 'sbridge serve' command."""
    is_json = getattr(args, "json", False)
    port = getattr(args, "port", 8080)
    host = getattr(args, "host", "127.0.0.1")
    token = getattr(args, "token", None)
    token_path_arg = getattr(args, "token_path", None)
    toolsets = getattr(args, "toolsets", None)

    token_path = Path(token_path_arg) if token_path_arg else get_broker_token_path()

    setup_logging(log_level="INFO", stream=sys.stderr)

    try:
        server = HttpServer(
            host=host,
            port=port,
            token=token,
            token_path=token_path,
            client=_DEFAULT_CLIENT,
            toolsets=toolsets,
        )
    except ValueError as exc:
        if is_json:
            print(json.dumps({"status": "error", "code": "E_USAGE", "message": str(exc)}))
        else:
            print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "code": "E_INTERNAL", "message": str(exc)}))
        else:
            print(f"Error initializing HTTP server: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        server.start(background=True)
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "code": "E_BIND", "message": str(exc)}))
        else:
            print(f"Error binding HTTP server: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if is_json:
        print(
            json.dumps(
                {
                    "status": "running",
                    "host": server.host,
                    "port": server.bound_port,
                    "url": server.url,
                    "token_path": str(server.token_path),
                    "endpoints": {
                        "rest": f"{server.url}/v1",
                        "mcp": f"{server.url}/mcp",
                        "openapi": f"{server.url}/openapi.json",
                    },
                },
                indent=2,
            )
        )
    else:
        print(f"StudioBridge HTTP server listening on {server.url}")
        print(f"  REST API:       {server.url}/v1")
        print(f"  MCP endpoint:   {server.url}/mcp")
        print(f"  OpenAPI schema: {server.url}/openapi.json")
        print(f"  Bearer token:   {server.token_path}")
        print("Press Ctrl+C to stop.")

    # Event used to wait for termination signal
    stop_event = threading.Event()

    def _sig_handler(signum: int, frame: Any) -> None:
        stop_event.set()

    # Register signal handlers on main thread if supported
    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except (ValueError, AttributeError):
        pass

    try:
        # Wait until stop_event is set or KeyboardInterrupt
        while not stop_event.is_set():
            stop_event.wait(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        if not is_json:
            print("\nStudioBridge HTTP server stopped.")

    return EXIT_OK
