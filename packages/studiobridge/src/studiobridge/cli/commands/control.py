"""Implementation of control CLI commands: transport, mixer, channels, patterns."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from studiobridge.core.errors import DisconnectedError
from studiobridge.mcp.tools.control import ControlTools

_DEFAULT_CLIENT: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client for CLI control commands."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def _get_control_tools(client: Any = None) -> ControlTools:
    """Return ControlTools provider instance."""
    resolved = client or _DEFAULT_CLIENT
    return ControlTools(client=resolved)


def handle_transport_control(args: argparse.Namespace) -> int:
    """Handle 'sbridge transport play|stop|record|tempo|pos' commands."""
    action = getattr(args, "transport_action", None)
    if not action:
        # Check subparser dest or command line argument
        action = getattr(args, "action", "get")

    is_json = getattr(args, "json", False)
    tools = _get_control_tools()

    tempo = getattr(args, "bpm", None)
    position = getattr(args, "ticks", None)
    allow_protected = getattr(args, "allow_protected", False)
    confirm_token = getattr(args, "confirm_token", None)

    try:
        res = tools.transport_control(
            action=action,
            tempo=tempo,
            position=position,
            allow_protected=allow_protected,
            confirm_token=confirm_token,
            verify=True,
        )
    except DisconnectedError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 4
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        for c in res.content:
            print(c.get("text", ""))

    return 0


def handle_mixer_set(args: argparse.Namespace) -> int:
    """Handle 'sbridge mixer set <track> [--vol/--pan/--mute/--solo/--name]' command."""
    is_json = getattr(args, "json", False)
    track_raw = getattr(args, "track", 0)
    try:
        track_idx = int(track_raw)
    except (ValueError, TypeError):
        track_idx = 0

    volume = getattr(args, "volume", None)
    pan = getattr(args, "pan", None)
    mute = getattr(args, "mute", None)
    solo = getattr(args, "solo", None)
    name = getattr(args, "name", None)
    allow_protected = getattr(args, "allow_protected", False)
    confirm_token = getattr(args, "confirm_token", None)

    tools = _get_control_tools()

    try:
        res = tools.mixer_set(
            track=track_idx,
            volume=volume,
            pan=pan,
            mute=mute,
            solo=solo,
            name=name,
            allow_protected=allow_protected,
            confirm_token=confirm_token,
            verify=True,
        )
    except DisconnectedError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 4
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        for c in res.content:
            print(c.get("text", ""))

    return 0


def handle_channels_set(args: argparse.Namespace) -> int:
    """Handle 'sbridge channels set <channel> [flags]' command."""
    is_json = getattr(args, "json", False)
    chan_raw = getattr(args, "channel", 0)
    try:
        chan_val: int | str = int(chan_raw)
    except (ValueError, TypeError):
        chan_val = str(chan_raw)

    volume = getattr(args, "volume", None)
    pan = getattr(args, "pan", None)
    mute = getattr(args, "mute", None)
    solo = getattr(args, "solo", None)
    name = getattr(args, "name", None)
    steps_str = getattr(args, "steps", None)
    confirm_token = getattr(args, "confirm_token", None)

    steps: list[int] | None = None
    if steps_str:
        tokens = [s.strip() for s in steps_str.split(",") if s.strip()]
        steps = [1 if t in ("1", "true", "True") else 0 for t in tokens]

    tools = _get_control_tools()

    try:
        res = tools.channel_set(
            channel=chan_val,
            volume=volume,
            pan=pan,
            mute=mute,
            solo=solo,
            name=name,
            steps=steps,
            confirm_token=confirm_token,
            verify=True,
        )
    except DisconnectedError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 4
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        for c in res.content:
            print(c.get("text", ""))

    return 0


def handle_patterns_control(args: argparse.Namespace) -> int:
    """Handle 'sbridge patterns select <n>' and 'sbridge patterns rename <n> <name>'."""
    is_json = getattr(args, "json", False)
    action = getattr(args, "patterns_action", "select")
    pattern = getattr(args, "pattern", 1)
    name = getattr(args, "name", None)
    color = getattr(args, "color", None)
    confirm_token = getattr(args, "confirm_token", None)

    tools = _get_control_tools()

    try:
        res = tools.pattern_edit(
            pattern=pattern,
            action=action,
            name=name,
            color=color,
            confirm_token=confirm_token,
            verify=True,
        )
    except DisconnectedError as err:
        if is_json:
            print(json.dumps({"status": "error", "code": err.code, "message": str(err)}, indent=2))
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 4
    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        for c in res.content:
            print(c.get("text", ""))

    return 0


__all__ = [
    "handle_channels_set",
    "handle_mixer_set",
    "handle_patterns_control",
    "handle_transport_control",
    "set_default_client",
]
