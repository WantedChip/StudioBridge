"""Command-line interface commands for headless FL Studio render orchestration.

Implements CLI commands:
- sbridge render <project.flp> [--format wav|mp3|flac] [--timeout seconds] [--watch] [--out dir]
- sbridge render status <job_id>
- sbridge render cancel <job_id>
- sbridge render analyze <audio_file>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from studiobridge.core.errors import StudioBridgeError
from studiobridge.mcp.tools.render import RenderTools

# CLI exit code constants
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_RENDER = 8

_DEFAULT_CLIENT: Any = None
_DEFAULT_RUNNER: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client for CLI render commands."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def set_default_runner(runner: Any = None) -> None:
    """Set default RenderRunner for CLI render commands (used in unit tests)."""
    global _DEFAULT_RUNNER
    _DEFAULT_RUNNER = runner


def _get_render_tools() -> RenderTools:
    """Return RenderTools provider instance."""
    return RenderTools(client=_DEFAULT_CLIENT, runner=_DEFAULT_RUNNER)


def handle_render_start(args: argparse.Namespace) -> int:
    """Handle 'sbridge render <project.flp> [options]' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_render_tools()

    source = getattr(args, "project", None) or getattr(args, "source", None)
    if not source:
        print("Error: Source project file (.flp) is required.", file=sys.stderr)
        return EXIT_USAGE

    fmt_raw = getattr(args, "format", "wav")
    formats = [f.strip() for f in fmt_raw.split(",") if f.strip()]
    out_dir = getattr(args, "out", None) or getattr(args, "out_dir", None)
    instance_policy = getattr(args, "policy", "require_closed")
    timeout_s = getattr(args, "timeout", 900.0)
    idle_timeout_s = getattr(args, "idle_timeout", 120.0)
    watch = getattr(args, "watch", False)

    try:
        start_res = tools.render_start(
            source=source,
            formats=formats,
            out_dir=out_dir,
            instance_policy=instance_policy,
            timeout_s=float(timeout_s),
            idle_timeout_s=float(idle_timeout_s),
            wait=False,
        )

        job_id = start_res.structured_content["job_id"]

        if not watch:
            if is_json:
                print(json.dumps(start_res.structured_content, indent=2))
            else:
                for item in start_res.content:
                    print(item.get("text", ""))
                print(f"Watch progress with: sbridge render status {job_id}")
            return EXIT_OK

        # Watch mode: poll until job completes or fails
        if not is_json:
            print(f"Rendering job '{job_id}' (watching)...")

        poll_interval = 0.5
        max_time = float(timeout_s)
        start_time = time.time()

        while True:
            status_res = tools.render_status(job_id)
            state = status_res.structured_content.get("state")

            if state in ("done", "failed", "cancelled"):
                if is_json:
                    print(json.dumps(status_res.structured_content, indent=2))
                else:
                    for item in status_res.content:
                        print(item.get("text", ""))

                if state == "done":
                    return EXIT_OK
                else:
                    return EXIT_RENDER

            if (time.time() - start_time) > max_time:
                if is_json:
                    print(
                        json.dumps(
                            {"status": "error", "code": "E_RND_TIMEOUT", "job_id": job_id}, indent=2
                        )
                    )
                else:
                    print(f"Error: Render timed out after {max_time:.1f}s", file=sys.stderr)
                return EXIT_RENDER

            time.sleep(poll_interval)

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_RENDER


def handle_render_status(args: argparse.Namespace) -> int:
    """Handle 'sbridge render status <job_id>' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_render_tools()

    job_id = getattr(args, "job_id", None)
    if not job_id:
        print("Error: job_id is required.", file=sys.stderr)
        return EXIT_USAGE

    try:
        res = tools.render_status(job_id=job_id)
        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))

        state = res.structured_content.get("state")
        return EXIT_OK if state != "failed" else EXIT_RENDER

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_render_cancel(args: argparse.Namespace) -> int:
    """Handle 'sbridge render cancel <job_id>' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_render_tools()

    job_id = getattr(args, "job_id", None)
    if not job_id:
        print("Error: job_id is required.", file=sys.stderr)
        return EXIT_USAGE

    try:
        res = tools.render_cancel(job_id=job_id)
        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))
        return EXIT_OK

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_render_analyze(args: argparse.Namespace) -> int:
    """Handle 'sbridge render analyze <file>' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_render_tools()

    path = getattr(args, "path", None)
    if not path:
        print("Error: Audio file path is required.", file=sys.stderr)
        return EXIT_USAGE

    min_dur = getattr(args, "min_duration", 0.5)
    max_silence = getattr(args, "max_silence", 0.98)
    allow_clipping = getattr(args, "allow_clipping", True)

    try:
        res = tools.render_analyze(
            path=path,
            min_duration_s=float(min_dur),
            max_silence_ratio=float(max_silence),
            allow_clipping=bool(allow_clipping),
        )
        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))

        is_valid = res.structured_content.get("is_valid", False)
        return EXIT_OK if is_valid else EXIT_ERROR

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_render(args: argparse.Namespace) -> int:
    """Main sub-dispatcher for 'sbridge render' command."""
    first = getattr(args, "project", None)
    if first in ("status", "cancel", "analyze"):
        target = getattr(args, "job_or_file", None)
        if first == "status":
            args.job_id = target
            return handle_render_status(args)
        elif first == "cancel":
            args.job_id = target
            return handle_render_cancel(args)
        elif first == "analyze":
            args.path = target
            return handle_render_analyze(args)

    action = getattr(args, "render_action", None)
    if action == "status":
        return handle_render_status(args)
    elif action == "cancel":
        return handle_render_cancel(args)
    elif action == "analyze":
        return handle_render_analyze(args)
    else:
        # Default action is rendering the project file
        return handle_render_start(args)


__all__ = [
    "handle_render",
    "handle_render_analyze",
    "handle_render_cancel",
    "handle_render_start",
    "handle_render_status",
    "set_default_client",
    "set_default_runner",
]
