"""CLI command handlers for 'sbridge skill'.

Implements 'sbridge skill install', 'sbridge skill list', and 'sbridge skill info'
per requirements [SKL-01].
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from studiobridge.agents.skill import (
    SKILL_NAME,
    SKILL_TARGETS,
    SkillInstaller,
    get_skill_target,
)

logger = logging.getLogger("studiobridge.cli.skill")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def handle_skill_install(installer: SkillInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge skill install'."""
    agent_name: str = getattr(args, "agent", ".agents")
    scope: str = getattr(args, "scope", "project")
    dest_arg: str | None = getattr(args, "dest", None)
    dry_run: bool = getattr(args, "dry_run", False)
    install_rules: bool = getattr(args, "rules", True)
    force: bool = getattr(args, "force", False)
    use_json: bool = getattr(args, "json", False)

    dest_path = Path(dest_arg) if dest_arg is not None else None

    # Handle 'all' target
    if agent_name.lower() == "all" and dest_path is None:
        targets_to_run = [t.id for t in SKILL_TARGETS]
    else:
        try:
            if dest_path is None:
                target_obj = get_skill_target(agent_name)
                targets_to_run = [target_obj.id]
            else:
                targets_to_run = ["custom"]
        except ValueError as exc:
            if use_json:
                print(json.dumps({"status": "error", "code": "E_USAGE", "message": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return EXIT_USAGE

    results: list[dict[str, Any]] = []
    overall_ok = True

    for t_id in targets_to_run:
        try:
            res = installer.install(
                target=t_id,
                scope=scope,
                dest=dest_path,
                dry_run=dry_run,
                install_rules=install_rules,
                force=force,
            )
            results.append(
                {
                    "target": res.target,
                    "scope": res.scope,
                    "dest_dir": str(res.dest_dir),
                    "files_written": [str(p) for p in res.files_written],
                    "files_skipped": [str(p) for p in res.files_skipped],
                    "agents_md_path": str(res.agents_md_path) if res.agents_md_path else None,
                    "agents_md_updated": res.agents_md_updated,
                    "dry_run": res.dry_run,
                    "message": res.message,
                    "status": "ok",
                }
            )
        except Exception as exc:
            overall_ok = False
            results.append(
                {
                    "target": t_id,
                    "scope": scope,
                    "dest_dir": str(dest_path) if dest_path else "",
                    "status": "error",
                    "error": str(exc),
                }
            )

    if use_json:
        payload = {
            "status": "ok" if overall_ok else "error",
            "installations": results,
        }
        print(json.dumps(payload, indent=2))
        return EXIT_OK if overall_ok else EXIT_ERROR

    # Human-readable CLI text output
    prefix = "[dry-run] " if dry_run else ""
    for r in results:
        if r.get("status") == "ok":
            print(f"{prefix}Skill '{SKILL_NAME}' -> {r['dest_dir']}")
            w_cnt = len(r["files_written"])
            u_cnt = len(r["files_skipped"])
            print(f"  Files written: {w_cnt}, unchanged: {u_cnt}")
            if r.get("agents_md_updated"):
                print(f"  Rules updated: {r['agents_md_path']}")
        else:
            print(f"Error installing for target '{r['target']}': {r.get('error')}", file=sys.stderr)

    return EXIT_OK if overall_ok else EXIT_ERROR


def handle_skill_list(installer: SkillInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge skill list'."""
    scope: str = getattr(args, "scope", "all")
    use_json: bool = getattr(args, "json", False)

    installed = installer.list_installed(scope=scope)

    if use_json:
        payload = [
            {
                "target": item.target,
                "scope": item.scope,
                "path": str(item.path),
                "valid": item.valid,
                "file_count": item.file_count,
                "has_rules": item.has_rules,
            }
            for item in installed
        ]
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    if not installed:
        print(f"No installed '{SKILL_NAME}' skills found.")
        return EXIT_OK

    header = f"{'Target':<14} {'Scope':<9} {'Valid':<8} {'Files':<7} {'Rules':<7} {'Path'}"
    print(header)
    print("-" * 90)
    for item in installed:
        valid_str = "Yes" if item.valid else "No"
        rules_str = "Yes" if item.has_rules else "No"
        print(
            f"{item.target:<14} {item.scope:<9} {valid_str:<8} "
            f"{item.file_count:<7} {rules_str:<7} {item.path}"
        )

    return EXIT_OK


def handle_skill_info(installer: SkillInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge skill info'."""
    use_json: bool = getattr(args, "json", False)

    try:
        info = installer.get_skill_info()
    except Exception as exc:
        if use_json:
            print(json.dumps({"status": "error", "message": str(exc)}))
        else:
            print(f"Error loading skill info: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if use_json:
        payload = {
            "name": info.name,
            "version": info.version,
            "description": info.description,
            "source_dir": str(info.source_dir),
            "files": list(info.files),
            "references": list(info.references),
            "rules_snippet": info.rules_snippet,
        }
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    print(f"Skill:       {info.name} (v{info.version})")
    print(f"Description: {info.description}")
    print(f"Source:      {info.source_dir}")
    print(f"Files ({len(info.files)}):")
    for f in info.files:
        print(f"  - {f}")
    if info.references:
        print(f"References ({len(info.references)}):")
        for r in info.references:
            print(f"  - {r}")
    print("\nAgent Rules Snippet (10 Hard Rules):")
    print("-" * 50)
    print(info.rules_snippet)

    return EXIT_OK


def handle_skill(args: argparse.Namespace) -> int:
    """Dispatch 'sbridge skill' subcommands."""
    action = getattr(args, "skill_action", None)
    installer = SkillInstaller()

    if action == "install":
        return handle_skill_install(installer, args)
    elif action == "list":
        return handle_skill_list(installer, args)
    elif action == "info":
        return handle_skill_info(installer, args)
    else:
        # Default action when none specified is 'info'
        return handle_skill_info(installer, args)


__all__ = [
    "handle_skill",
    "handle_skill_info",
    "handle_skill_install",
    "handle_skill_list",
]
