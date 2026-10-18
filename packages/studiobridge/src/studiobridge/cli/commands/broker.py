"""Implementation of 'sbridge broker' command."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import anyio

from studiobridge.broker.client import BrokerClient, ensure_broker, is_process_alive
from studiobridge.core.paths import get_broker_json_path, get_broker_token_path


def handle_broker(args: argparse.Namespace) -> int:
    """Handle 'sbridge broker start|stop|status' subcommands."""
    subaction = getattr(args, "broker_action", "status") or "status"
    is_json = getattr(args, "json", False)

    meta_path = get_broker_json_path()
    token_path = get_broker_token_path()

    if subaction == "start":
        host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
        timeout = float(getattr(args, "timeout", 8.0))

        try:
            b_host, b_port = ensure_broker(host=host, timeout=timeout)
            meta = {}
            if meta_path.exists():
                with contextlib.suppress(Exception):
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))

            res = {
                "status": "running",
                "host": b_host,
                "port": b_port,
                "pid": meta.get("pid"),
                "message": f"Broker daemon running on {b_host}:{b_port}",
            }
            if is_json:
                print(json.dumps(res, indent=2))
            else:
                print(f"Broker daemon is active on {b_host}:{b_port} (PID {meta.get('pid')})")
            return 0
        except Exception as exc:
            if is_json:
                print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
            else:
                print(f"Error starting broker: {exc}", file=sys.stderr)
            return 1

    if subaction == "stop":
        if not meta_path.exists():
            if is_json:
                print(json.dumps({"status": "already_stopped"}, indent=2))
            else:
                print("Broker daemon is not running.")
            return 0

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pid = int(meta.get("pid", 0))
            port = int(meta.get("port", 0))

            if port > 0 and token_path.exists():

                async def _stop() -> None:
                    client = BrokerClient(
                        port=port,
                        metadata_path=meta_path,
                        token_path=token_path,
                    )
                    async with client:
                        await client.shutdown()

                with contextlib.suppress(Exception):
                    anyio.run(_stop)

            meta_path.unlink(missing_ok=True)
            if is_json:
                print(json.dumps({"status": "stopped", "pid": pid}, indent=2))
            else:
                print(f"Broker daemon stopped (PID {pid}).")
            return 0
        except Exception as exc:
            if is_json:
                print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
            else:
                print(f"Error stopping broker: {exc}", file=sys.stderr)
            return 1

    if subaction == "status":
        if not meta_path.exists():
            if is_json:
                print(json.dumps({"status": "stopped", "running": False}, indent=2))
            else:
                print("Broker daemon is stopped.")
            return 3

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pid = int(meta.get("pid", 0))
            port = int(meta.get("port", 0))
            alive = is_process_alive(pid)

            res = {
                "status": "running" if alive else "stale",
                "running": alive,
                "pid": pid,
                "port": port,
                "host": "127.0.0.1",
            }
            if is_json:
                print(json.dumps(res, indent=2))
            else:
                if alive:
                    print(f"Broker daemon is running on 127.0.0.1:{port} (PID {pid})")
                else:
                    print(f"Broker daemon metadata is stale (PID {pid} is dead).")
            return 0 if alive else 3
        except Exception as exc:
            if is_json:
                print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
            else:
                print(f"Error checking broker status: {exc}", file=sys.stderr)
            return 3

    return 2
