"""FLP seed template instantiation and fragment authoring CLI handlers.

Implements CLI commands:
- sbridge flp new [--template <name>] <output.flp>
- sbridge flp template list [--json]
- sbridge flp template add <flp> --select channel:<id> [--name <name>] [--author <author>]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from studiobridge.core.errors import TemplateFragmentUnavailableError
from studiobridge.core.paths import validate_safe_path
from studiobridge.flp.atomic import atomic_save
from studiobridge.flp.model.project import Project
from studiobridge.flp.templates.instantiator import (
    TemplateLibrary,
    instantiate,
)


def handle_flp_template(args: argparse.Namespace) -> int:
    """Dispatch template subcommands (new, list, add)."""
    action = getattr(args, "flp_template_action", None)
    if action == "new":
        return _handle_new(args)
    if action == "list":
        return _handle_list(args)
    if action == "add":
        return _handle_add(args)

    print(f"Unknown template action: {action}", file=sys.stderr)
    return 2


def _handle_new(args: argparse.Namespace) -> int:
    """Handle `sbridge flp new [--template <name>] <output.flp>` [FLP-40]."""
    out_arg = getattr(args, "output", None) or getattr(args, "file", None)
    if not out_arg:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": "Missing required output file path"}))
        else:
            print("Error: Missing required output file path", file=sys.stderr)
        return 1

    dest_path = validate_safe_path(out_arg)
    template_name = getattr(args, "template", "minimal") or "minimal"
    force = getattr(args, "force", False)

    params: dict[str, Any] = {}
    if getattr(args, "title", None):
        params["title"] = args.title
    if getattr(args, "author", None):
        params["author"] = args.author
    if getattr(args, "comments", None):
        params["comments"] = args.comments
    if getattr(args, "tempo", None) is not None:
        params["tempo"] = args.tempo

    try:
        project = instantiate(template_name, params)
    except TemplateFragmentUnavailableError as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": exc.code,
                        "message": str(exc),
                        "remedy": exc.remedy,
                    }
                )
            )
        else:
            print(f"Error ({exc.code}): {exc}", file=sys.stderr)
            if exc.remedy:
                print(f"Remedy: {exc.remedy}", file=sys.stderr)
        return 7
    except Exception as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Failed to instantiate template '{template_name}': {exc}",
                    }
                )
            )
        else:
            print(
                f"Error: Failed to instantiate template '{template_name}': {exc}",
                file=sys.stderr,
            )
        return 7

    try:
        saved_path = atomic_save(project, dest_path, in_place=force)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Failed to save project: {exc}"}))
        else:
            print(f"Error: Failed to save project: {exc}", file=sys.stderr)
        return 7

    if getattr(args, "json", False):
        output = {
            "status": "ok",
            "file": str(saved_path),
            "template": template_name,
            "title": project.title,
            "tempo": project.tempo,
            "channels": len(project.channels),
            "patterns": len(project.patterns),
            "version": project.version,
        }
        print(json.dumps(output, indent=2))
        return 0

    print(
        f"Created project '{saved_path.name}' from template '{template_name}' "
        f"({len(project.channels)} channels, {project.tempo:.1f} BPM, FL {project.version})"
    )
    print(f"Destination: {saved_path}")
    return 0


def _handle_list(args: argparse.Namespace) -> int:
    """Handle `sbridge flp template list [--json]` [FLP-40]."""
    templates = TemplateLibrary.list_templates()
    fragments = [f.to_dict() for f in TemplateLibrary.list_fragments()]

    if getattr(args, "json", False):
        output = {
            "status": "ok",
            "templates": templates,
            "fragments": fragments,
        }
        print(json.dumps(output, indent=2))
        return 0

    print("Baseline Seed Templates:")
    print("-" * 70)
    for t in templates:
        name = t.get("name", "unknown")
        ch_count = t.get("channel_count", 0)
        tempo = t.get("tempo", 120.0)
        ver = t.get("version", "26.1.0")
        title = t.get("title", "")
        print(f"  * {name:<18} ({ch_count} ch, {tempo:.1f} BPM, FL {ver}) - {title}")

    print("\nStock Fragment Library:")
    print("-" * 70)
    for f in fragments:
        name = f.get("name", "unknown")
        kind = f.get("kind", "unknown")
        profile = f.get("profile", "*")
        ev_count = f.get("event_count", 0)
        prov = f.get("provenance", {})
        author = prov.get("author", "StudioBridge")
        fl_ver = prov.get("fl_version", "26.1.0")
        print(
            f"  * {name:<24} [{kind}] (profile: {profile}, {ev_count} events, "
            f"FL {fl_ver} by {author})"
        )

    return 0


def _handle_add(args: argparse.Namespace) -> int:
    """Handle `sbridge flp template add <flp> --select channel:<id>` [FLP-40]."""
    file_path = validate_safe_path(args.file)
    if not file_path.is_file():
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"File not found: {file_path}"}))
        else:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    selector = getattr(args, "select", None)
    if not selector:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": "Missing required --select selector"}))
        else:
            print(
                "Error: Missing required --select selector (e.g. --select channel:3)",
                file=sys.stderr,
            )
        return 1

    # Parse selector format: channel:<id>
    selector_str = selector.strip().lower()
    if selector_str.startswith("channel:"):
        raw_id = selector_str.removeprefix("channel:")
    elif selector_str.isdigit():
        raw_id = selector_str
    else:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": (
                            f"Unsupported selector format '{selector}'; expected 'channel:<id>'"
                        ),
                    }
                )
            )
        else:
            print(
                f"Error: Unsupported selector format '{selector}'; expected 'channel:<id>'",
                file=sys.stderr,
            )
        return 1

    try:
        channel_index = int(raw_id)
    except ValueError:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": f"Invalid channel index '{raw_id}' in selector",
                    }
                )
            )
        else:
            print(f"Error: Invalid channel index '{raw_id}' in selector", file=sys.stderr)
        return 1

    try:
        project = Project.load(file_path)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Failed to parse project: {exc}"}))
        else:
            print(f"Error: Failed to parse project: {exc}", file=sys.stderr)
        return 7

    if not (0 <= channel_index < len(project.channels)):
        msg = (
            f"Channel index {channel_index} out of range; project has {len(project.channels)} "
            f"channels (0..{len(project.channels) - 1})"
        )
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": msg}))
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return 1

    try:
        frag = TemplateLibrary.extract_fragment(
            project,
            channel_index,
            name=getattr(args, "name", None),
            kind=getattr(args, "kind", None),
            author=getattr(args, "author", None),
        )
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "message": f"Failed to extract fragment: {exc}"}))
        else:
            print(f"Error: Failed to extract fragment: {exc}", file=sys.stderr)
        return 7

    if getattr(args, "json", False):
        output = {
            "status": "ok",
            "message": f"Successfully extracted fragment '{frag.name}'",
            "channel_index": channel_index,
            "fragment": frag.to_dict(),
        }
        print(json.dumps(output, indent=2))
        return 0

    print(
        f"Successfully extracted fragment '{frag.name}' from channel {channel_index} "
        f"({frag.kind}, {len(frag.events)} events)"
    )
    print(
        f"Provenance: FL {frag.provenance.fl_version}, by {frag.provenance.author} "
        f"on {frag.provenance.date}"
    )
    print(f"Source file: {frag.provenance.source_file}")
    return 0
