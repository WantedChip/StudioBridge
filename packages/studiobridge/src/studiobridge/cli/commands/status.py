"""Implementation of 'sbridge status' command."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import anyio

from studiobridge._version import __version__
from studiobridge.broker.client import BrokerClient, is_process_alive
from studiobridge.core.paths import get_broker_json_path, get_broker_token_path


def handle_status(args: argparse.Namespace) -> int:
    """Print live bridge status, capabilities, and lease holder."""
    is_json = getattr(args, "json", False)

    meta_path = get_broker_json_path()
    token_path = get_broker_token_path()

    if not meta_path.exists():
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "broker_running": False,
                        "version": __version__,
                        "message": "Broker daemon is not running.",
                    },
                    indent=2,
                )
            )
        else:
            print("StudioBridge Status: STOPPED (Broker daemon is not running)")
        return 3

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pid = int(meta.get("pid", 0))
        port = int(meta.get("port", 0))

        if not is_process_alive(pid):
            if is_json:
                print(
                    json.dumps(
                        {
                            "status": "stale",
                            "broker_running": False,
                            "stale_pid": pid,
                            "message": f"Stale metadata detected; process {pid} is dead.",
                        },
                        indent=2,
                    )
                )
            else:
                print(f"StudioBridge Status: STALE (PID {pid} is dead. Restart broker.)")
            return 3

        async def _query_status() -> dict[str, Any]:
            client = BrokerClient(
                port=port,
                metadata_path=meta_path,
                token_path=token_path,
            )
            async with client:
                st = await client.status()
                return st if isinstance(st, dict) else {"status": st}

        result = anyio.run(_query_status)
        combined = {
            "status": "running",
            "broker_running": True,
            "version": __version__,
            "pid": pid,
            "port": port,
            "broker": result,
        }

        if is_json:
            print(json.dumps(combined, indent=2))
        else:
            print("StudioBridge Status: RUNNING")
            print("=" * 60)
            print(f"Version:      v{__version__}")
            print(f"Daemon PID:   {pid}")
            print(f"TCP Endpoint: 127.0.0.1:{port}")
            uptime = result.get("uptime_s", "unknown")
            print(f"Uptime:       {uptime}s")
            lease = result.get("lease", {})
            lease_held = lease.get("held", False)
            owner_str = f"Acquired by {lease.get('owner')}" if lease_held else "Available"
            print(f"Writer Lease: {owner_str}")
            print("=" * 60)

        return 0

    except Exception as exc:
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "unreachable",
                        "broker_running": False,
                        "error": str(exc),
                    },
                    indent=2,
                )
            )
        else:
            print(f"StudioBridge Status: UNREACHABLE ({exc})", file=sys.stderr)
        return 3
