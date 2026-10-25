"""FLP project inspection, semantic diffing, and roundtrip CLI handlers.

Implements CLI commands per spec 10_l2_interfaces.md §3 and v0.5.2:
- sbridge flp inspect <file> [--json]
- sbridge flp diff <a.flp> <b.flp> [--json]
- sbridge flp roundtrip <file> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from studiobridge.core.errors import StudioBridgeError
from studiobridge.flp.atomic import atomic_save
from studiobridge.flp.codec.reader import FlpFile
from studiobridge.flp.diff import diff_projects
from studiobridge.flp.model.project import Project
from studiobridge.flp.validate.invariants import check_invariants


def handle_flp(args: argparse.Namespace) -> int:
    """Dispatch FLP subcommands (inspect, diff, roundtrip, edit, new, template)."""
    action = getattr(args, "flp_action", None)
    if action == "inspect":
        return _handle_inspect(args)
    if action == "diff":
        return _handle_diff(args)
    if action == "roundtrip":
        return _handle_roundtrip(args)
    if action == "edit":
        return _handle_edit(args)
    if action in ("new", "template"):
        from studiobridge.cli.commands.flp_template import handle_flp_template

        return handle_flp_template(args)

    print(f"Unknown flp action: {action}", file=sys.stderr)
    return 2


def _handle_inspect(args: argparse.Namespace) -> int:
    """Handle `sbridge flp inspect <file> [--json]`."""
    file_path = Path(args.file)
    if not file_path.is_file():
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"File not found: {file_path}"}))
        else:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    try:
        project = Project.load(file_path)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Failed to parse project: {exc}"}))
        else:
            print(f"Error: Failed to parse project: {exc}", file=sys.stderr)
        return 7

    if getattr(args, "json", False):
        output = {
            "status": "ok",
            "file": str(file_path),
            "project": project.to_dict(),
            "summary": project.info(),
        }
        print(json.dumps(output, indent=2))
        return 0

    info = project.info()
    print(f"Project: {file_path.name}")
    print(f"  Version: {info['version']}")
    if info["title"]:
        print(f"  Title: {info['title']}")
    if info["author"]:
        print(f"  Author: {info['author']}")
    print(f"  Tempo: {info['tempo']:.2f} BPM (Fine: {info['fine_tempo']:.2f} BPM)")
    print(f"  PPQ: {info['ppq']}")
    print(f"  Licensed: {info['licensed']}")
    print(f"  Channels ({info['channel_count']}):")
    for ch in project.channels:
        plugin_hint = f", plugin: {ch.plugin.name_hint or 'opaque'}" if ch.plugin else ""
        print(
            f"    [{ch.index}] {ch.name!r} ({ch.channel_type}, "
            f"mixer track: {ch.target_mixer_track}{plugin_hint})"
        )
    print(f"  Patterns ({info['pattern_count']}):")
    for pat in project.patterns:
        print(f"    [{pat.number}] {pat.name!r} ({pat.total_notes} notes)")
    print(f"  Playlist Items: {info['playlist_item_count']}")
    print(f"  Unmodeled Events: {info['unmodeled_event_count']}")

    return 0


def _handle_diff(args: argparse.Namespace) -> int:
    """Handle `sbridge flp diff <a.flp> <b.flp> [--json]`."""
    file_a = Path(args.file_a)
    file_b = Path(args.file_b)

    for p in (file_a, file_b):
        if not p.is_file():
            if getattr(args, "json", False):
                print(json.dumps({"status": "error", "message": f"File not found: {p}"}))
            else:
                print(f"Error: File not found: {p}", file=sys.stderr)
            return 1

    try:
        proj_a = Project.load(file_a)
        proj_b = Project.load(file_b)
    except Exception as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {"status": "error", "message": f"Failed to load project for diff: {exc}"}
                )
            )
        else:
            print(f"Error: Failed to load project for diff: {exc}", file=sys.stderr)
        return 7

    diff_report = diff_projects(proj_a, proj_b)

    if getattr(args, "json", False):
        output = {
            "status": "ok",
            "file_a": str(file_a),
            "file_b": str(file_b),
            "diff": diff_report.to_dict(),
        }
        print(json.dumps(output, indent=2))
        return 0

    print(f"Diffing {file_a.name} -> {file_b.name}:")
    print(diff_report.format_text())
    return 0


def _handle_roundtrip(args: argparse.Namespace) -> int:
    """Handle `sbridge flp roundtrip <file> [--json]`."""
    file_path = Path(args.file)
    if not file_path.is_file():
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"File not found: {file_path}"}))
        else:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    try:
        raw_bytes = file_path.read_bytes()
        flp_file = FlpFile.from_bytes(raw_bytes)
        re_bytes = flp_file.serialize()
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Roundtrip error: {exc}"}))
        else:
            print(f"Error during roundtrip processing: {exc}", file=sys.stderr)
        return 7

    if raw_bytes == re_bytes:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "byte_identical": True,
                        "file": str(file_path),
                        "size_bytes": len(raw_bytes),
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"[OK] Byte-identical roundtrip verified for {file_path.name} "
                f"({len(raw_bytes)} bytes)"
            )
        return 0

    # Mismatch detected
    mismatch_offset = -1
    for idx in range(min(len(raw_bytes), len(re_bytes))):
        if raw_bytes[idx] != re_bytes[idx]:
            mismatch_offset = idx
            break
    if mismatch_offset == -1:
        mismatch_offset = min(len(raw_bytes), len(re_bytes))

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "status": "error",
                    "byte_identical": False,
                    "file": str(file_path),
                    "original_size": len(raw_bytes),
                    "serialized_size": len(re_bytes),
                    "first_mismatch_offset": mismatch_offset,
                },
                indent=2,
            )
        )
    else:
        print(
            f"Error: Roundtrip mismatch for {file_path.name} at byte offset {mismatch_offset} "
            f"(original: {len(raw_bytes)} bytes, serialized: {len(re_bytes)} bytes)",
            file=sys.stderr,
        )
    return 7


def _handle_edit(args: argparse.Namespace) -> int:
    """Handle `sbridge flp edit <file> [options...]`."""
    file_path = Path(args.file)
    if not file_path.is_file():
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"File not found: {file_path}"}))
        else:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    try:
        project = Project.load(file_path)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Failed to load project: {exc}"}))
        else:
            print(f"Error: Failed to load project: {exc}", file=sys.stderr)
        return 7

    mutator = project.mutate()

    # Apply command line mutations
    try:
        if getattr(args, "tempo", None) is not None:
            mutator.set_tempo(float(args.tempo))
        if getattr(args, "title", None) is not None:
            mutator.set_title(str(args.title))
        if getattr(args, "author", None) is not None:
            mutator.set_author(str(args.author))
        if getattr(args, "comments", None) is not None:
            mutator.set_comments(str(args.comments))

        # Channel mutations
        for entry in getattr(args, "rename_channel", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.rename_channel(int(parts[0]), parts[1])
        for entry in getattr(args, "channel_volume", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.set_channel_volume(int(parts[0]), float(parts[1]))
        for entry in getattr(args, "channel_pan", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.set_channel_pan(int(parts[0]), float(parts[1]))

        # Pattern mutations
        for entry in getattr(args, "rename_pattern", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.rename_pattern(int(parts[0]), parts[1])
        for pat_num in getattr(args, "clear_pattern", None) or []:
            mutator.clear_pattern(int(pat_num))

        # Mixer mutations
        for entry in getattr(args, "rename_track", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.rename_track(int(parts[0]), parts[1])
        for entry in getattr(args, "track_volume", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.set_track_volume(int(parts[0]), float(parts[1]))
        for trk_idx in getattr(args, "track_mute", None) or []:
            mutator.set_track_mute(int(trk_idx), True)
        for trk_idx in getattr(args, "track_solo", None) or []:
            mutator.set_track_solo(int(trk_idx), True)

        # Playlist mutations
        for entry in getattr(args, "add_marker", None) or []:
            parts = entry.split(":", 1)
            if len(parts) == 2:
                mutator.add_marker(parts[0], int(parts[1]))

        # Check invariants
        check_invariants(project)

    except StudioBridgeError as err:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": err.code,
                        "message": str(err),
                        "details": err.details,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 7
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Mutation error: {exc}"}))
        else:
            print(f"Error: Mutation error: {exc}", file=sys.stderr)
        return 7

    # Dry-run handling
    if getattr(args, "dry_run", False):
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "dry_run": True,
                        "file": str(file_path),
                        "mutations_applied": len(mutator.records),
                        "mutations": [r.to_dict() for r in mutator.records],
                    },
                    indent=2,
                )
            )
        else:
            print(
                f"[DRY-RUN] Verified {len(mutator.records)} mutations for {file_path.name}; "
                f"invariants hold."
            )
        return 0

    # Determine destination
    in_place = getattr(args, "in_place", False)
    if getattr(args, "out", None):
        dest_path = Path(args.out)
    elif in_place:
        dest_path = file_path
    else:
        dest_path = file_path.with_name(f"{file_path.stem}.sb{file_path.suffix}")

    try:
        saved_path = atomic_save(
            project,
            dest_path,
            in_place=in_place,
            force_unknown_version=getattr(args, "force_unknown_version", False),
        )
    except StudioBridgeError as err:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": err.code,
                        "message": str(err),
                        "details": err.details,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
        return 7
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Save error: {exc}"}))
        else:
            print(f"Error during save: {exc}", file=sys.stderr)
        return 7

    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "status": "ok",
                    "file": str(file_path),
                    "destination": str(saved_path),
                    "mutations_applied": len(mutator.records),
                    "mutations": [r.to_dict() for r in mutator.records],
                },
                indent=2,
            )
        )
    else:
        print(
            f"[OK] Applied {len(mutator.records)} mutations; saved atomically to {saved_path.name}"
        )
    return 0
