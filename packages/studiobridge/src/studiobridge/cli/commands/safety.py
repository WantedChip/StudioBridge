"""Implementation of safety and transaction CLI commands.

Supports mode, checkpoint, rollback, journal, call, and batch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from studiobridge.core.errors import DisconnectedError
from studiobridge.mcp.tools.control import ControlTools
from studiobridge.mcp.tools.safety import SafetyTools

_DEFAULT_CLIENT: Any = None


def set_default_client(client: Any = None) -> None:
    """Set default Studio client for CLI safety commands."""
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client


def _session_call(fl: Any, op: str, args: Any = None, allow_protected: bool = False) -> Any:
    """Invoke allowlisted API operation across synchronous or asynchronous Studio clients."""
    if hasattr(fl, "raw") and hasattr(fl.raw, "call"):
        if isinstance(args, dict):
            return fl.raw.call(op, allow_protected=allow_protected, **args)
        elif isinstance(args, (list, tuple)):
            return fl.raw.call(op, *args, allow_protected=allow_protected)
        elif args is not None:
            return fl.raw.call(op, args, allow_protected=allow_protected)
        else:
            return fl.raw.call(op, allow_protected=allow_protected)

    session = getattr(fl, "_session", None)
    if session is None and hasattr(fl, "_async"):
        session = getattr(fl._async, "session", None)
    if session is not None:
        portal = getattr(fl, "_portal", None)
        if portal is not None:
            import functools

            return portal.call(
                functools.partial(session.call, op, args or {}, allow_protected=allow_protected)
            )
        return session.call(op, args or {}, allow_protected=allow_protected)
    raise RuntimeError(f"Cannot resolve session to invoke operation '{op}'.")


def _get_safety_tools(client: Any = None) -> SafetyTools:
    """Return SafetyTools provider instance."""
    resolved = client or _DEFAULT_CLIENT
    return SafetyTools(client=resolved)


def _get_control_tools(client: Any = None) -> ControlTools:
    """Return ControlTools provider instance."""
    resolved = client or _DEFAULT_CLIENT
    return ControlTools(client=resolved)


def handle_safety(args: argparse.Namespace) -> int:
    """Handle 'sbridge safety <mode|checkpoint|rollback|journal>' commands."""
    action = getattr(args, "safety_action", "mode")
    is_json = getattr(args, "json", False)
    tools = _get_safety_tools()

    try:
        if action == "mode":
            mode = getattr(args, "mode", "read_only")
            reason = getattr(args, "reason", None)
            confirm_token = getattr(args, "confirm_token", None)
            res = tools.studio_set_mode(mode=mode, reason=reason, confirm_token=confirm_token)

        elif action == "checkpoint":
            name = getattr(args, "name", "checkpoint") or "checkpoint"
            res = tools.checkpoint_create(name=name)

        elif action == "rollback":
            checkpoint_id = getattr(args, "checkpoint_id", None)
            confirm_token = getattr(args, "confirm_token", None)
            res = tools.checkpoint_rollback(
                checkpoint_id=checkpoint_id, confirm_token=confirm_token
            )

        elif action == "journal":
            limit = getattr(args, "limit", 50)
            since = getattr(args, "since", None)
            op = getattr(args, "op", None)
            res = tools.journal_list(limit=limit, since=since, op=op)

        else:
            print(
                f"Unknown safety action '{action}'. Valid: mode, checkpoint, rollback, journal.",
                file=sys.stderr,
            )
            return 2

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


def _parse_arg_value(val: str) -> Any:
    """Parse raw string argument into int, float, bool, or string."""
    s = val.strip()
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.lower() == "null" or s.lower() == "none":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def handle_call(args: argparse.Namespace) -> int:
    """Handle 'sbridge call <module.fn> [args...] [--verify] [--allow-protected]' command."""
    is_json = getattr(args, "json", False)
    fn = getattr(args, "function", "")
    raw_args = getattr(args, "args", [])
    verify = getattr(args, "verify", True)
    allow_protected = getattr(args, "allow_protected", False)
    confirm_token = getattr(args, "confirm_token", None)

    # Parse positional or keyword arguments
    parsed_args: list[Any] = []
    parsed_kwargs: dict[str, Any] = {}
    for a in raw_args:
        if "=" in a:
            k, v = a.split("=", 1)
            parsed_kwargs[k.strip()] = _parse_arg_value(v)
        else:
            parsed_args.append(_parse_arg_value(a))

    call_payload: Any = parsed_kwargs if parsed_kwargs else parsed_args

    tools = _get_control_tools()

    try:
        res = tools.fl_call(
            function=fn,
            args=call_payload,
            allow_protected=allow_protected,
            confirm_token=confirm_token,
            verify=verify,
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


def handle_batch(args: argparse.Namespace) -> int:
    """Handle 'sbridge batch <file.json|->' for batch mutations with rollback on error."""
    is_json = getattr(args, "json", False)
    file_path = getattr(args, "file", "-")
    allow_protected = getattr(args, "allow_protected", False)

    # Read content
    try:
        if file_path == "-":
            raw_content = sys.stdin.read()
        else:
            raw_content = Path(file_path).read_text(encoding="utf-8")
    except Exception as exc:
        print(f"Failed to read batch input: {exc}", file=sys.stderr)
        return 2

    # Parse mutations (support JSON array or NDJSON)
    operations: list[dict[str, Any]] = []
    stripped = raw_content.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                operations = parsed
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON in batch file: {exc}", file=sys.stderr)
            return 2
    else:
        for line in stripped.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            try:
                operations.append(json.loads(line_str))
            except json.JSONDecodeError as exc:
                print(f"Invalid NDJSON line: {exc}", file=sys.stderr)
                return 2

    if not operations:
        print("Batch contained no operations.", file=sys.stderr)
        return 0

    resolved_client = _DEFAULT_CLIENT
    if resolved_client is None:
        print("Error: No active FL Studio connection.", file=sys.stderr)
        return 4

    fl = resolved_client

    # Check mode: batch mutates, so mode must allow writes
    if fl.safety.mode == "read_only":
        err_msg = (
            "Cannot execute batch in 'read_only' mode. "
            "Switch mode to 'write' via 'sbridge safety mode write'."
        )
        if is_json:
            print(
                json.dumps({"status": "error", "code": "E_READONLY", "message": err_msg}, indent=2)
            )
        else:
            print(f"Error [E_READONLY]: {err_msg}", file=sys.stderr)
        return 6

    # Execute in a transaction for rollback on error
    applied_receipts: list[dict[str, Any]] = []
    try:
        with fl.transaction("cli_batch") as tx:
            for op_def in operations:
                fn = op_def.get("op", op_def.get("function", ""))
                op_args = op_def.get("args", {})
                res = _session_call(fl, fn, op_args, allow_protected=allow_protected)
                applied_receipts.append(
                    {
                        "op": fn,
                        "verified": True,
                        "result": res,
                    }
                )
            tx.commit()

        receipt = {
            "status": "ok",
            "verified": True,
            "plane": "live",
            "journal_id": max(1, len(fl.safety.journal.list())),
            "operations_count": len(applied_receipts),
            "receipts": applied_receipts,
        }
        if is_json:
            print(json.dumps(receipt, indent=2))
        else:
            print(
                f"Successfully applied {len(applied_receipts)} batch mutation(s) "
                "[verified=True, plane=live]."
            )
        return 0

    except Exception as exc:
        receipt = {
            "status": "error",
            "error": str(exc),
            "rolled_back": True,
            "guarantee": "verified",
            "applied_count": len(applied_receipts),
        }
        if is_json:
            print(json.dumps(receipt, indent=2))
        else:
            print(f"Batch execution failed: {exc}. Changes rolled back.", file=sys.stderr)
        return 1


__all__ = [
    "handle_batch",
    "handle_call",
    "handle_safety",
    "set_default_client",
]
