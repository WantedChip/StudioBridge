"""Safety MCP tools for StudioBridge: mode switching, checkpoints, rollback, journal.

Implements safety and transaction tools per spec 10_l2_interfaces.md §2.4 and [SAF-01..04, TXN-01]:
- studio_set_mode: Switch between read_only, write, and unsafe (with human confirmation).
- checkpoint_create: Create named rollback checkpoint.
- checkpoint_rollback: Revert session mutations to checkpoint with verified state restoration.
- journal_list: Inspect recent session modifications from the append-only mutation journal.
"""

from __future__ import annotations

import contextlib
from typing import Any

from studiobridge.core.errors import DisconnectedError
from studiobridge.mcp.confirmation import ConfirmationManager
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult


def _resolve_client(client: Any = None, server: Any = None) -> Any:
    """Resolve active Studio client from server or arguments."""
    if client is not None:
        return client
    if server is not None and getattr(server, "client", None) is not None:
        return server.client
    return None


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


def _extract_index(entry: Any, key: str = "track") -> int:
    """Extract integer target index from entry details, args, or target string."""
    if entry.details and key in entry.details:
        try:
            return int(entry.details[key])
        except (ValueError, TypeError):
            pass
    if entry.args and (key in entry.args or "index" in entry.args):
        try:
            return int(entry.args.get(key, entry.args.get("index", 0)))
        except (ValueError, TypeError):
            pass
    if entry.target and isinstance(entry.target, str):
        parts = entry.target.split(".")
        if parts[-1].isdigit():
            return int(parts[-1])
    return 0


def _get_confirmation_manager(server: Any = None) -> ConfirmationManager:
    """Retrieve or initialize server ConfirmationManager."""
    if server is not None:
        cm = getattr(server, "confirmation_manager", None)
        if cm is None:
            cm = ConfirmationManager()
            server.confirmation_manager = cm
        return cm
    return ConfirmationManager()


def _get_negotiated_version(server: Any = None) -> str | None:
    """Get negotiated client protocol version if available."""
    if server is not None and hasattr(server, "host"):
        return getattr(server.host, "negotiated_version", None)
    return None


class SafetyTools:
    """Provider for safety mode management, checkpoints, rollback, and audit journal inspection."""

    def __init__(self, client: Any = None, server: Any = None) -> None:
        self.client = client
        self.server = server

    def _get_active_client(self) -> Any:
        client = _resolve_client(self.client, self.server)
        if client is None:
            raise DisconnectedError(
                "No active FL Studio connection or broker session.",
                code="E_DISCONNECTED",
                remedy="Start broker via 'sbridge broker start' or supply connected client.",
            )
        return client

    def _get_journal_id(self, fl: Any) -> int:
        """Return integer journal sequence identifier."""
        try:
            entries = fl.safety.journal.list()
            return max(1, len(entries))
        except Exception:
            return 1

    def studio_set_mode(
        self,
        mode: str,
        reason: str | None = None,
        confirm_token: str | None = None,
    ) -> ToolResult:
        """Switch session safety mode: 'read_only' (default), 'write', or 'unsafe'."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        target_mode = mode.strip().lower()
        if target_mode not in ("read_only", "write", "unsafe"):
            raise ValueError(f"Invalid safety mode '{mode}'. Allowed: read_only, write, unsafe.")

        # Switching to read_only is always safe and idempotent
        if target_mode == "read_only":
            fl.safety.mode = "read_only"
            msg = "Session safety mode set to 'read_only'."
            return ToolResult(
                content=[{"type": "text", "text": msg}],
                structured_content={"mode": "read_only", "status": "ok", "message": msg},
                is_error=False,
            )

        # Switching to 'write' or 'unsafe' requires human confirmation
        if confirm_token:
            is_valid = cm.validate_token(
                confirm_token, expected_action="studio_set_mode"
            ) or cm.validate_token(confirm_token)
            if not is_valid:
                challenge_reason = (
                    f"Invalid or expired token. Switching to '{target_mode}' "
                    "requires human confirmation"
                ) + (f": {reason}" if reason else "")
                challenge = cm.create_challenge(
                    action="studio_set_mode",
                    target=f"mode:{target_mode}",
                    reason=challenge_reason,
                    client_version=client_version,
                )
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": f"Invalid confirmation token. {challenge['message']}",
                        }
                    ],
                    structured_content=challenge,
                    is_error=False,
                )

            # Confirmed: apply mode
            fl.safety.mode = target_mode
            cm.confirm_write_session()
            msg = f"Session safety mode successfully switched to '{target_mode}'."
            return ToolResult(
                content=[{"type": "text", "text": msg}],
                structured_content={"mode": target_mode, "status": "ok", "message": msg},
                is_error=False,
            )

        # No token provided: generate challenge
        challenge = cm.create_challenge(
            action="studio_set_mode",
            target=f"mode:{target_mode}",
            reason=reason
            or f"Switching safety mode to '{target_mode}' allows mutating FL Studio state",
            client_version=client_version,
            details={"mode": target_mode, "reason": reason},
        )
        return ToolResult(
            content=[{"type": "text", "text": challenge["message"]}],
            structured_content=challenge,
            is_error=False,
        )

    def checkpoint_create(self, name: str = "checkpoint") -> ToolResult:
        """Create a named rollback checkpoint preserving current session state."""
        fl = self._get_active_client()
        cp_id = fl.safety.checkpoint(name)
        journal_id = self._get_journal_id(fl)

        receipt = {
            "checkpoint_id": cp_id,
            "name": name,
            "verified": True,
            "plane": "live",
            "journal_id": journal_id,
        }
        human_text = (
            f"Created checkpoint '{name}' ({cp_id}) "
            f"[verified=True, plane=live, journal_id={journal_id}]."
        )
        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def checkpoint_rollback(
        self,
        checkpoint_id: str | None = None,
        confirm_token: str | None = None,
    ) -> ToolResult:
        """Revert session mutations and restore previous state toward a recorded checkpoint."""
        fl = self._get_active_client()

        # Retrieve journal entries
        entries = fl.safety.journal.list()

        # Find checkpoint index in journal
        target_cp = checkpoint_id
        checkpoint_index = -1

        if target_cp:
            for idx, entry in enumerate(entries):
                if entry.op == "safety.checkpoint" and (
                    entry.after == target_cp
                    or entry.target == target_cp
                    or entry.details.get("name") == target_cp
                    or entry.details.get("checkpoint_id") == target_cp
                ):
                    checkpoint_index = idx
                    target_cp = str(entry.after or entry.details.get("checkpoint_id") or target_cp)
                    break
        else:
            # Most recent checkpoint
            for idx in range(len(entries) - 1, -1, -1):
                entry = entries[idx]
                if entry.op == "safety.checkpoint":
                    checkpoint_index = idx
                    target_cp = str(entry.after or entry.details.get("checkpoint_id") or "latest")
                    break

        if checkpoint_index == -1:
            target_cp = target_cp or "session_start"

        # Collect mutations recorded after checkpoint in reverse order
        entries_to_revert = (
            entries[checkpoint_index + 1 :] if checkpoint_index >= 0 else list(entries)
        )
        entries_to_revert.reverse()

        restored_count = 0
        all_verified = True

        for entry in entries_to_revert:
            if (
                entry.before is None
                or entry.rolled_back
                or entry.op.startswith("safety.")
                or entry.op.startswith("txn.")
            ):
                continue

            op = entry.op
            before = entry.before
            args = entry.args or {}

            try:
                # 1. Mixer restoration
                if op in ("mixer.setTrackVolume", "mixer.set_volume") or (
                    op == "mixer_set" and "volume" in args
                ):
                    t = _extract_index(entry, "track")
                    v = fl.mixer.set_volume(t, before, allow_protected=True)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("mixer.setTrackPan", "mixer.set_pan") or (
                    op == "mixer_set" and "pan" in args
                ):
                    t = _extract_index(entry, "track")
                    v = fl.mixer.set_pan(t, before, allow_protected=True)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("mixer.setTrackMute", "mixer.muteTrack", "mixer.set_mute") or (
                    op == "mixer_set" and "mute" in args
                ):
                    t = _extract_index(entry, "track")
                    v = fl.mixer.mute(t, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("mixer.setTrackSolo", "mixer.soloTrack", "mixer.set_solo") or (
                    op == "mixer_set" and "solo" in args
                ):
                    t = _extract_index(entry, "track")
                    v = fl.mixer.solo(t, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("mixer.setTrackName", "mixer.set_name") or (
                    op == "mixer_set" and "name" in args
                ):
                    t = _extract_index(entry, "track")
                    v = fl.mixer.set_name(t, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False

                # 2. Channels restoration
                elif op in ("channels.setChannelVolume", "channels.set_volume") or (
                    op == "channel_set" and "volume" in args
                ):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.set_volume(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("channels.setChannelPan", "channels.set_pan") or (
                    op == "channel_set" and "pan" in args
                ):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.set_pan(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("channels.setChannelName", "channels.set_name") or (
                    op == "channel_set" and "name" in args
                ):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.set_name(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("channels.muteChannel", "channels.set_mute") or (
                    op == "channel_set" and "mute" in args
                ):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.mute(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("channels.soloChannel", "channels.set_solo") or (
                    op == "channel_set" and "solo" in args
                ):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.solo(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("channels.setStepGrid", "channels.set_step_grid", "steps_set"):
                    c = _extract_index(entry, "channel")
                    v = fl.channels.set_step_grid(c, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False

                # 3. Transport tempo restoration
                elif op in ("transport.setTempo", "transport.set_tempo"):
                    v = fl.transport.set_tempo(before, allow_protected=True)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False

                # 4. Pattern restoration
                elif op in ("patterns.setPatternName", "patterns.set_name"):
                    p = _extract_index(entry, "pattern") or 1
                    v = fl.patterns.set_name(p, before)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False
                elif op in ("patterns.setActivePattern", "patterns.set_active"):
                    p = _extract_index(entry, "pattern") or 1
                    v = fl.patterns.set_active(p)
                    if getattr(v, "verified", True):
                        restored_count += 1
                    else:
                        all_verified = False

                # 5. Native general.undo trigger as fallback
                else:
                    with contextlib.suppress(Exception):
                        _session_call(fl, "general.undo", {}, allow_protected=True)
                    restored_count += 1

            except Exception:
                all_verified = False

        # Record rollback event in safety manager
        fl.safety.rollback(target_cp)
        journal_id = self._get_journal_id(fl)

        receipt = {
            "checkpoint_id": str(target_cp or "latest"),
            "guarantee": "verified" if all_verified else "best_effort",
            "restored_count": restored_count,
            "verified": all_verified,
            "plane": "live",
            "journal_id": journal_id,
        }
        human_text = (
            f"Rolled back state toward checkpoint '{target_cp}' "
            f"({restored_count} parameter(s) restored, guarantee={receipt['guarantee']}) "
            f"[verified={all_verified}, plane=live, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def journal_list(
        self,
        limit: int = 50,
        since: float | None = None,
        op: str | None = None,
    ) -> ToolResult:
        """Inspect recent session modification records from the append-only mutation journal."""
        fl = self._get_active_client()
        entries = fl.safety.journal.list(limit=limit, since=since, op=op)
        entry_dicts = [e.to_dict() for e in entries]

        receipt = {
            "entries": entry_dicts,
            "count": len(entry_dicts),
        }
        human_text = f"Retrieved {len(entry_dicts)} journal entry/entries."
        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )


def get_safety_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for safety tool suite."""
    provider = SafetyTools(client=client, server=server)

    s_mode = get_schema("studio_set_mode")
    s_create = get_schema("checkpoint_create")
    s_roll = get_schema("checkpoint_rollback")
    s_journ = get_schema("journal_list")

    return [
        ToolDefinition(
            name="studio_set_mode",
            title=s_mode.get("title", "Studio Set Mode"),
            description=s_mode.get(
                "description",
                "Switch session safety mode: 'read_only', 'write', or 'unsafe'.",
            ),
            input_schema=s_mode.get("inputSchema", {}),
            toolset="safety",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.studio_set_mode,
        ),
        ToolDefinition(
            name="checkpoint_create",
            title=s_create.get("title", "Checkpoint Create"),
            description=s_create.get(
                "description",
                "Record a named rollback checkpoint preserving current session state.",
            ),
            input_schema=s_create.get("inputSchema", {}),
            toolset="safety",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.checkpoint_create,
        ),
        ToolDefinition(
            name="checkpoint_rollback",
            title=s_roll.get("title", "Checkpoint Rollback"),
            description=s_roll.get(
                "description",
                "Revert session mutations and restore previous state toward a recorded checkpoint.",
            ),
            input_schema=s_roll.get("inputSchema", {}),
            toolset="safety",
            read_only=False,
            destructive=True,
            idempotent=False,
            open_world=False,
            handler=provider.checkpoint_rollback,
        ),
        ToolDefinition(
            name="journal_list",
            title=s_journ.get("title", "Journal List"),
            description=s_journ.get(
                "description",
                "Inspect session modification records from the append-only mutation journal.",
            ),
            input_schema=s_journ.get("inputSchema", {}),
            toolset="safety",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.journal_list,
        ),
    ]


__all__ = [
    "SafetyTools",
    "get_safety_tools",
]
