"""Command-line interface commands for piano-roll notes operations.

Implements CLI commands:
- sbridge notes apply <file.json|.mid> [--target channel:X,pattern:Y] [--mode append|replace]
- sbridge notes from-midi <file> [--ppq N]
- sbridge notes read <project.flp> [--pattern N] [--channel M]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from studiobridge.core.errors import StudioBridgeError
from studiobridge.mcp.tools.notes import NotesTools

# CLI exit code constants
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

_DEFAULT_CLIENT: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client for CLI notes commands."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def _get_notes_tools(client: Any = None) -> NotesTools:
    """Return NotesTools provider instance."""
    resolved = client or _DEFAULT_CLIENT
    return NotesTools(client=resolved)


def parse_target(target_str: str | None) -> tuple[int | None, int | None]:
    """Parse target channel and pattern from 'channel:X,pattern:Y' string."""
    if not target_str:
        return None, None
    ch: int | None = None
    pat: int | None = None
    for token in target_str.split(","):
        token = token.strip()
        if ":" in token:
            k, v = token.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k in ("ch", "channel") and v.isdigit():
                ch = int(v)
            elif k in ("pat", "pattern") and v.isdigit():
                pat = int(v)
    return ch, pat


def parse_range(range_str: str | None) -> list[int] | None:
    """Parse tick range from 'start:end' or 'start,end' string."""
    if not range_str:
        return None
    sep = ":" if ":" in range_str else ","
    parts = range_str.split(sep)
    if len(parts) >= 2:
        try:
            return [int(parts[0].strip()), int(parts[1].strip())]
        except ValueError:
            pass
    return None


def handle_notes_apply(args: argparse.Namespace) -> int:
    """Handle 'sbridge notes apply <file> [options]' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_notes_tools()

    file_path = getattr(args, "file", None)
    target_str = getattr(args, "target", None)
    t_ch, t_pat = parse_target(target_str)

    # Allow direct overrides if passed
    channel = getattr(args, "channel", None)
    if channel is None:
        channel = t_ch

    pattern = getattr(args, "pattern", None)
    if pattern is None:
        pattern = t_pat

    mode_raw = getattr(args, "mode", "append")
    mode = "replace_all" if mode_raw in ("replace", "replace_all") else mode_raw

    range_val = parse_range(getattr(args, "range", None))
    verify = getattr(args, "verify", "none")
    fallback = getattr(args, "fallback", "none")
    allow_focus_steal = getattr(args, "allow_focus_steal", None)
    force = getattr(args, "force", False)
    dry_run = getattr(args, "dry_run", False)
    ppq = getattr(args, "ppq", None)

    try:
        res = tools.notes_apply(
            file=file_path,
            channel=channel,
            pattern=pattern,
            mode=mode,
            range=range_val,
            verify=verify,
            fallback=fallback,
            allow_focus_steal=allow_focus_steal,
            force=force,
            dry_run=dry_run,
            ppq=ppq,
        )

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))

        if res.is_error:
            return EXIT_ERROR
        return EXIT_OK

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_notes_from_midi(args: argparse.Namespace) -> int:
    """Handle 'sbridge notes from-midi <file>' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_notes_tools()

    file_val = getattr(args, "file", None)
    if not file_val:
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_ARG",
                        "message": "Missing required MIDI file path.",
                    },
                    indent=2,
                )
            )
        else:
            print("Error [E_ARG]: Missing required MIDI file path.", file=sys.stderr)
        return EXIT_USAGE

    file_path: str = str(file_val)
    ppq = getattr(args, "ppq", 96)

    try:
        res = tools.notes_from_midi(path=file_path, ppq=ppq)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))

        if res.is_error:
            return EXIT_ERROR
        return EXIT_OK

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_notes_read(args: argparse.Namespace) -> int:
    """Handle 'sbridge notes read <file>' CLI command."""
    is_json = getattr(args, "json", False)
    tools = _get_notes_tools()

    file_val = getattr(args, "file", None)
    if not file_val:
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_ARG",
                        "message": "Missing required project file path.",
                    },
                    indent=2,
                )
            )
        else:
            print("Error [E_ARG]: Missing required project file path.", file=sys.stderr)
        return EXIT_USAGE

    file_path: str = str(file_val)
    pattern = getattr(args, "pattern", 1)
    channel = getattr(args, "channel", 0)

    try:
        res = tools.notes_read(flp_path=file_path, pattern=pattern, channel=channel)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            for item in res.content:
                print(item.get("text", ""))

        if res.is_error:
            return EXIT_ERROR
        return EXIT_OK

    except StudioBridgeError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return EXIT_ERROR


def handle_notes(args: argparse.Namespace) -> int:
    """Main sub-dispatcher for 'sbridge notes' command."""
    action = getattr(args, "notes_action", None)
    if action == "apply":
        return handle_notes_apply(args)
    elif action == "from-midi":
        return handle_notes_from_midi(args)
    elif action == "read":
        return handle_notes_read(args)
    else:
        print("Usage: sbridge notes [apply|from-midi|read] [options]", file=sys.stderr)
        return EXIT_USAGE


__all__ = [
    "handle_notes",
    "handle_notes_apply",
    "handle_notes_from_midi",
    "handle_notes_read",
    "set_default_client",
]
