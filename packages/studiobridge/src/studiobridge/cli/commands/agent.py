"""CLI command handlers for 'sbridge agent'.

Implements 'sbridge agent list', 'sbridge agent install', and 'sbridge agent snippet'
per requirements [AGT-01] through [AGT-04].
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from studiobridge.agents.installer import (
    AgentInstaller,
    get_target,
    render_snippet,
    resolve_config_path,
)

logger = logging.getLogger("studiobridge.cli.agent")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def handle_agent_list(installer: AgentInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge agent list'."""
    results = installer.detect_all()
    use_json = getattr(args, "json", False)

    if use_json:
        payload = [
            {
                "id": r.target.id,
                "name": r.target.display_name,
                "tier": r.target.tier,
                "detected": r.detected,
                "detected_by": r.detected_by,
                "configured": r.configured,
                "scope": r.scope,
                "config_path": str(r.config_path),
            }
            for r in results
        ]
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    # Tabular output
    header = (
        f"{'Target':<16} {'Display Name':<18} {'Detected':<10} "
        f"{'Configured':<12} {'Scope':<9} {'Config Path'}"
    )
    print(header)
    print("-" * 100)
    for r in results:
        det_str = "Yes" if r.detected else "No"
        cfg_str = "Yes" if r.configured else "No"
        print(
            f"{r.target.id:<16} {r.target.display_name:<18} {det_str:<10} "
            f"{cfg_str:<12} {r.scope:<9} {r.config_path}"
        )
    return EXIT_OK


def handle_agent_install(installer: AgentInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge agent install <agent>'."""
    agent_name: str = getattr(args, "agent", "")
    scope_arg: str | None = getattr(args, "scope", None)
    is_dry_run: bool = getattr(args, "dry_run", False)
    use_npm: bool = getattr(args, "npm", False)
    use_uvx: bool = getattr(args, "uvx", False)
    force: bool = getattr(args, "force", False)
    use_json: bool = getattr(args, "json", False)

    launcher = "npm" if use_npm and not use_uvx else "uvx"

    targets_to_install = []
    if agent_name.lower() == "all":
        detected = installer.detect_all()
        targets_to_install = [d.target.id for d in detected if d.detected]
        if not targets_to_install:
            # Fall back to all Tier-1 targets
            targets_to_install = [d.target.id for d in detected]
    else:
        try:
            target = get_target(agent_name)
            targets_to_install = [target.id]
        except ValueError as exc:
            if use_json:
                print(json.dumps({"status": "error", "code": "E_USAGE", "message": str(exc)}))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return EXIT_USAGE

    results: list[dict[str, Any]] = []
    overall_ok = True

    for t_id in targets_to_install:
        res = installer.install(
            agent_name=t_id,
            scope=scope_arg,
            dry_run=is_dry_run,
            launcher=launcher,
            force=force,
            verify=not is_dry_run,
        )

        if not res.success:
            overall_ok = False

        res_dict = {
            "agent": res.target.id,
            "display_name": res.target.display_name,
            "success": res.success,
            "changed": res.changed,
            "dry_run": res.dry_run,
            "config_path": str(res.config_path),
            "scope": res.scope,
            "message": res.message,
            "diff": res.diff,
            "backup_path": str(res.backup_path) if res.backup_path else None,
            "warnings": res.warnings,
            "next_steps": res.next_steps,
            "verified": res.verify_result.passed if res.verify_result else None,
        }
        results.append(res_dict)

        if not use_json:
            for w in res.warnings:
                print(f"[WARN] {w}", file=sys.stderr)

            if res.dry_run:
                print(f"\n--- Dry-run diff for {res.target.display_name} ({res.config_path}) ---")
                if res.diff:
                    print(res.diff)
                else:
                    print("(No changes required; configuration already matches)")
            else:
                if res.success:
                    if res.changed:
                        print(f"[OK] Installed StudioBridge for {res.target.display_name}")
                        print(f"     Config path: {res.config_path}")
                        if res.backup_path:
                            print(f"     Backup created: {res.backup_path}")
                        if res.verify_result:
                            if res.verify_result.passed:
                                count = res.verify_result.tools_count
                                print(
                                    f"     [OK] Server verification passed "
                                    f"({count} tools registered)"
                                )
                            else:
                                err = res.verify_result.error
                                print(
                                    f"     [WARN] Server verification failed: {err}",
                                    file=sys.stderr,
                                )
                    else:
                        print(
                            f"[OK] Already configured for {res.target.display_name} "
                            f"({res.config_path})"
                        )

                    if res.next_steps:
                        print(f"     Next step: {res.next_steps}")
                else:
                    print(f"[ERROR] {res.message}", file=sys.stderr)

    if use_json:
        out_payload: dict[str, Any] = {
            "status": "ok" if overall_ok else "error",
            "results": results if len(results) > 1 else results[0],
        }
        print(json.dumps(out_payload, indent=2))

    return EXIT_OK if overall_ok else EXIT_ERROR


def handle_agent_snippet(installer: AgentInstaller, args: argparse.Namespace) -> int:
    """Handle 'sbridge agent snippet <agent>'."""
    agent_name: str = getattr(args, "agent", "")
    use_npm: bool = getattr(args, "npm", False)
    use_uvx: bool = getattr(args, "uvx", False)
    use_json: bool = getattr(args, "json", False)

    launcher = "npm" if use_npm and not use_uvx else "uvx"

    try:
        target = get_target(agent_name)
    except ValueError as exc:
        if use_json:
            print(json.dumps({"status": "error", "code": "E_USAGE", "message": str(exc)}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        snippet = render_snippet(target, launcher=launcher)
    except Exception as exc:
        if use_json:
            print(json.dumps({"status": "error", "code": "E_SECURITY", "message": str(exc)}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if use_json:
        hint_path = resolve_config_path(target, target.default_scope)
        payload = {
            "status": "ok",
            "agent": target.id,
            "display_name": target.display_name,
            "format": target.config_format,
            "launcher": launcher,
            "config_path_hint": str(hint_path),
            "snippet": snippet,
            "next_steps": target.next_steps,
        }
        print(json.dumps(payload, indent=2))
    else:
        # Direct raw snippet to stdout for seamless copy-pasting
        sys.stdout.write(snippet)

    return EXIT_OK


def handle_agent(args: argparse.Namespace) -> int:
    """Main CLI dispatcher for 'sbridge agent' commands."""
    action = getattr(args, "agent_action", "list")
    installer = AgentInstaller()

    if action == "list":
        return handle_agent_list(installer, args)
    if action == "install":
        return handle_agent_install(installer, args)
    if action == "snippet":
        return handle_agent_snippet(installer, args)

    print(f"Error: Unknown agent action '{action}'", file=sys.stderr)
    return EXIT_USAGE
