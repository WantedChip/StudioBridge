"""FLP project inspection, semantic diffing, and roundtrip CLI handlers.

Implements CLI commands:
- sbridge flp inspect <file> [--json]
- sbridge flp diff <a.flp> <b.flp> [--json]
- sbridge flp roundtrip <file> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

from studiobridge.core.errors import StudioBridgeError
from studiobridge.core.paths import validate_safe_path
from studiobridge.flp.atomic import atomic_save
from studiobridge.flp.codec.reader import FlpFile
from studiobridge.flp.diff import diff_projects
from studiobridge.flp.model.project import Project
from studiobridge.flp.validate.invariants import check_invariants


def handle_flp(args: argparse.Namespace) -> int:
    """Dispatch FLP subcommands (inspect, diff, roundtrip, edit, validate, new, template)."""
    action = getattr(args, "flp_action", None)
    if action == "inspect":
        return _handle_inspect(args)
    if action == "diff":
        return _handle_diff(args)
    if action == "roundtrip":
        return _handle_roundtrip(args)
    if action == "edit":
        return _handle_edit(args)
    if action == "validate":
        return _handle_validate(args)
    if action in ("new", "template"):
        from studiobridge.cli.commands.flp_template import handle_flp_template

        return handle_flp_template(args)

    print(f"Unknown flp action: {action}", file=sys.stderr)
    return 2


def _handle_inspect(args: argparse.Namespace) -> int:
    """Handle `sbridge flp inspect <file> [--json]`."""
    file_path = validate_safe_path(args.file)
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
    file_a = validate_safe_path(args.file_a)
    file_b = validate_safe_path(args.file_b)

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
    file_path = validate_safe_path(args.file)
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
    file_path = validate_safe_path(args.file)
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
        dest_path = validate_safe_path(args.out)
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


def _handle_validate(args: argparse.Namespace) -> int:
    """Handle `sbridge flp validate <file> [--in-fl] [--timeout SECONDS] [--json]` [FLP-50]."""
    file_path = validate_safe_path(args.file)
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

    from studiobridge.flp.validate.invariants import validate_invariants
    from studiobridge.flp.validate.risk import calculate_project_risk

    violations = validate_invariants(project)
    risk_report = calculate_project_risk(project)

    in_fl = getattr(args, "in_fl", False)
    load_result = None
    live_result = None

    if in_fl:
        timeout_s = float(getattr(args, "timeout", 30.0) or 30.0)
        from studiobridge.flp.validate.fl_load import FlLoadHarness

        harness = FlLoadHarness()
        try:
            load_result = harness.run(file_path, timeout_s=timeout_s)
        except Exception as exc:
            if getattr(args, "json", False):
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "file": str(file_path),
                            "message": f"Headless FL-load failed: {exc}",
                        }
                    )
                )
            else:
                print(f"Error: Headless FL-load failed: {exc}", file=sys.stderr)
            return 7

        # Also check if live bridge session is active
        live_result = harness.verify_live_bridge(project)

    is_ok = len(violations) == 0 and (load_result is None or load_result.is_ok)
    status_str = "ok" if is_ok else "error"

    if getattr(args, "json", False):
        output = {
            "status": status_str,
            "file": str(file_path),
            "invariants": {
                "valid": len(violations) == 0,
                "violations": violations,
            },
            "risk": risk_report.to_dict(),
            "fl_load": load_result.to_dict() if load_result else None,
            "live_verification": live_result.to_dict() if live_result else None,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Validating: {file_path.name}")
        inv_status = (
            "PASS (0 violations)" if not violations else f"FAIL ({len(violations)} violations)"
        )
        print(f"  Structural Invariants: {inv_status}")
        for v in violations:
            print(f"    - {v}")

        risk_state = "safe to load" if risk_report.is_safe_to_load else "elevated risk"
        print(
            f"  Risk Assessment: {risk_report.level.upper()} "
            f"(Score: {risk_report.score}/100, {risk_state})"
        )
        for factor in risk_report.factors:
            print(f"    - [{factor.category}] {factor.message}")

        if in_fl and load_result:
            outcome_display = load_result.outcome.upper()
            print(
                f"  FL-Load Preflight: {outcome_display} "
                f"(duration: {load_result.duration_s:.1f}s, exit code: {load_result.exit_code})"
            )
            if load_result.dialog_title:
                print(f"    Dialog Title: '{load_result.dialog_title}'")
            if load_result.error_message:
                print(f"    Details: {load_result.error_message}")

        if live_result and live_result.available:
            live_status = "PASS" if live_result.matches else "FAIL"
            print(f"  Live Bridge Integrity: {live_status} ({live_result.message})")

    if violations:
        return 5  # Verification failed
    if in_fl and load_result and not load_result.is_ok:
        return 7  # Offline FLP error / load freeze or crash
    return 0
