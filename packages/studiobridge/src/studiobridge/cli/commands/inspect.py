"""Implementation of inspection CLI commands: transport, mixer, channels, patterns."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from studiobridge.mcp.tools.inspect import InspectTools

_DEFAULT_CLIENT: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client for CLI inspection commands."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def _get_inspect_tools(client: Any = None) -> InspectTools:
    """Return InspectTools provider instance."""
    resolved = client or _DEFAULT_CLIENT
    return InspectTools(client=resolved)


def handle_transport(args: argparse.Namespace) -> int:
    """Handle 'sbridge transport get' command."""
    action = getattr(args, "transport_action", "get") or "get"
    is_json = getattr(args, "json", False)

    if action != "get":
        print(f"Unknown transport action '{action}'. Use 'sbridge transport get'.", file=sys.stderr)
        return 2

    tools = _get_inspect_tools()
    res = tools.transport_get()

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        d = res.structured_content
        print("FL Studio Transport Status:")
        print("=" * 60)
        print(f"Playback:       {'PLAYING' if d['is_playing'] else 'STOPPED'}")
        print(f"Tempo:          {d['tempo']:.2f} BPM")
        print(f"Song Position:  {d['song_pos']} ticks ({d['song_time_s']:.2f}s)")
        print(f"Loop Mode:      {d['loop_mode']}")
        sig = d["time_signature"]
        print(f"Time Signature: {sig[0]}/{sig[1]}")
        print("=" * 60)
    return 0


def handle_mixer(args: argparse.Namespace) -> int:
    """Handle 'sbridge mixer list' and 'sbridge mixer get <track>' commands."""
    action = getattr(args, "mixer_action", "list") or "list"
    is_json = getattr(args, "json", False)
    tools = _get_inspect_tools()

    if action == "list":
        limit = int(getattr(args, "limit", 40))
        cursor = int(getattr(args, "cursor", 0))
        fields_arg = getattr(args, "fields", None)
        fields = [f.strip() for f in fields_arg.split(",") if f.strip()] if fields_arg else None

        res = tools.mixer_list(limit=limit, cursor=cursor, fields=fields)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            tracks = res.structured_content.get("tracks", [])
            total = res.structured_content.get("total", 0)
            next_cursor = res.structured_content.get("next_cursor")
            print(f"Mixer Tracks ({len(tracks)} of {total} shown, cursor {cursor}):")
            print("=" * 80)
            print(f"{'Idx':<4} {'Name':<24} {'Vol (dB)':<10} {'Pan':<8} {'State':<12} {'Peak':<6}")
            print("-" * 80)
            for t in tracks:
                idx = t.get("index", "")
                name = t.get("name", "")
                v_db = (
                    f"{t.get('volume_db', 0.0):+.1f} dB"
                    if "volume_db" in t
                    else f"{t.get('volume', 0.0):.2f}"
                )
                pan = f"{t.get('pan', 0.0):+.2f}" if "pan" in t else ""
                state_flags = []
                if t.get("muted"):
                    state_flags.append("MUTED")
                if t.get("solo"):
                    state_flags.append("SOLO")
                if t.get("armed"):
                    state_flags.append("ARMED")
                state_str = " ".join(state_flags) if state_flags else "active"
                peak_str = f"{t.get('peak', 0.0):.2f}" if "peak" in t else ""
                print(f"{idx:<4} {name:<24} {v_db:<10} {pan:<8} {state_str:<12} {peak_str:<6}")
            print("=" * 80)
            if next_cursor is not None:
                print(f"Next page cursor: {next_cursor} (use '--cursor {next_cursor}')")
        return 0

    if action == "get":
        track_arg = getattr(args, "track", None)
        if track_arg is None:
            print(
                "Error: Track identifier is required "
                "(e.g. 'sbridge mixer get 0' or 'sbridge mixer get Master')",
                file=sys.stderr,
            )
            return 2

        res = tools.mixer_get(track=track_arg)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            d = res.structured_content
            print(f"Mixer Track {d['index']}: '{d['name']}'")
            print("=" * 60)
            print(f"Volume:         {d['volume']:.4f} ({d['volume_db']:+.2f} dB)")
            print(f"Pan:            {d['pan']:+.4f}")
            print(f"Muted:          {'Yes' if d['muted'] else 'No'}")
            print(f"Solo:           {'Yes' if d['solo'] else 'No'}")
            print(f"Armed:          {'Yes' if d['armed'] else 'No'}")
            print(f"Color:          {d['color']}")
            print(f"Peak Meter:     {d['peak']}")
            print("=" * 60)
        return 0

    print(
        f"Unknown mixer action '{action}'. "
        "Use 'sbridge mixer list' or 'sbridge mixer get <track>'.",
        file=sys.stderr,
    )
    return 2


def handle_channels(args: argparse.Namespace) -> int:
    """Handle 'sbridge channels list' and 'sbridge channels get <channel>' commands."""
    action = getattr(args, "channels_action", "list") or "list"
    is_json = getattr(args, "json", False)
    tools = _get_inspect_tools()

    if action == "list":
        limit = int(getattr(args, "limit", 20))
        cursor = int(getattr(args, "cursor", 0))
        fields_arg = getattr(args, "fields", None)
        fields = [f.strip() for f in fields_arg.split(",") if f.strip()] if fields_arg else None

        res = tools.channels_list(limit=limit, cursor=cursor, fields=fields)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            channels = res.structured_content.get("channels", [])
            total = res.structured_content.get("total", 0)
            next_cursor = res.structured_content.get("next_cursor")
            print(f"Channels ({len(channels)} of {total} shown, cursor {cursor}):")
            print("=" * 80)
            print(f"{'Idx':<4} {'Name':<24} {'Vol':<8} {'Pan':<8} {'State':<10} {'Step Bits'}")
            print("-" * 80)
            for ch in channels:
                idx = ch.get("index", "")
                name = ch.get("name", "")
                vol = f"{ch.get('volume', 0.0):.2f}" if "volume" in ch else ""
                pan = f"{ch.get('pan', 0.0):+.2f}" if "pan" in ch else ""
                state_flags = []
                if ch.get("muted"):
                    state_flags.append("MUTED")
                if ch.get("solo"):
                    state_flags.append("SOLO")
                state_str = " ".join(state_flags) if state_flags else "active"
                step_bits = f"{ch.get('step_bits', 0):016b}" if "step_bits" in ch else ""
                print(f"{idx:<4} {name:<24} {vol:<8} {pan:<8} {state_str:<10} {step_bits}")
            print("=" * 80)
            if next_cursor is not None:
                print(f"Next page cursor: {next_cursor} (use '--cursor {next_cursor}')")
        return 0

    if action == "get":
        channel_arg = getattr(args, "channel", None)
        if channel_arg is None:
            print(
                "Error: Channel identifier is required (e.g. 'sbridge channels get 0')",
                file=sys.stderr,
            )
            return 2

        res = tools.channel_get(channel=channel_arg)

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            d = res.structured_content
            print(f"Channel {d['index']}: '{d['name']}'")
            print("=" * 60)
            print(f"Volume:     {d['volume']:.4f}")
            print(f"Pan:        {d['pan']:+.4f}")
            print(f"Pitch:      {d['pitch']:+.2f}")
            print(f"Muted:      {'Yes' if d['muted'] else 'No'}")
            print(f"Solo:       {'Yes' if d['solo'] else 'No'}")
            print(f"Color:      {d['color']}")
            print(f"Step Bits:  {d['step_bits']:016b}")
            if "step_grid" in d:
                grid_symbols = ["■" if s else "·" for s in d["step_grid"][:16]]
                print(f"Step Grid:  {' '.join(grid_symbols)}")
            print("=" * 60)
        return 0

    print(
        f"Unknown channels action '{action}'. "
        "Use 'sbridge channels list' or 'sbridge channels get <ch>'.",
        file=sys.stderr,
    )
    return 2


def handle_patterns(args: argparse.Namespace) -> int:
    """Handle 'sbridge patterns list' command."""
    action = getattr(args, "patterns_action", "list") or "list"
    is_json = getattr(args, "json", False)

    if action != "list":
        print(f"Unknown patterns action '{action}'. Use 'sbridge patterns list'.", file=sys.stderr)
        return 2

    limit = int(getattr(args, "limit", 20))
    cursor = int(getattr(args, "cursor", 1))
    fields_arg = getattr(args, "fields", None)
    fields = [f.strip() for f in fields_arg.split(",") if f.strip()] if fields_arg else None

    tools = _get_inspect_tools()
    res = tools.patterns_list(limit=limit, cursor=cursor, fields=fields)

    if is_json:
        print(json.dumps(res.structured_content, indent=2))
    else:
        patterns = res.structured_content.get("patterns", [])
        total = res.structured_content.get("total", 0)
        active_pat = res.structured_content.get("active_pattern", 1)
        next_cursor = res.structured_content.get("next_cursor")
        print(f"Patterns ({len(patterns)} of {total} shown, active: Pattern {active_pat}):")
        print("=" * 70)
        print(f"{'Num':<6} {'Name':<24} {'Length (ticks)':<16} {'Active'}")
        print("-" * 70)
        for p in patterns:
            num = p.get("number", "")
            name = p.get("name", "")
            len_ticks = p.get("length_ticks", 0)
            is_act = "✓ (ACTIVE)" if p.get("is_active") else ""
            print(f"{num:<6} {name:<24} {len_ticks:<16} {is_act}")
        print("=" * 70)
        if next_cursor is not None:
            print(f"Next page cursor: {next_cursor} (use '--cursor {next_cursor}')")
    return 0
