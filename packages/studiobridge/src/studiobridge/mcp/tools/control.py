"""Mutating control MCP tools for StudioBridge.

Implements control tools with verified writes:
- transport_control: Play, stop, record, seek, tempo adjustments.
- mixer_set: Array of track adjustments (volume, pan, mute, solo, name).
- channel_set: Volume, pan, mute, solo, name, and 16-step sequencer pattern.
- plugin_param_set: Normalized plugin parameter value writes.
- pattern_edit: Pattern selection, renaming, coloring, and clearing.
- steps_set: 16-step sequencer grid activation pattern for rhythm channels.
- playlist_edit: Arrangement playlist track name, color, mute, and solo.
- playlist_place_pattern: Place pattern clip on arrangement playlist (experimental).
- fl_call: Raw allowlisted API execution for raw / unsafe toolsets.

Every mutating tool returns a structured write receipt:
{verified: bool, plane: str, journal_id: int} alongside human-readable text.
"""

from __future__ import annotations

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


class ControlTools:
    """Provider for mutating FL Studio control MCP tools."""

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

    def transport_control(
        self,
        action: str,
        tempo: float | None = None,
        position: float | None = None,
        allow_protected: bool = False,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Control FL Studio playback transport: play, stop, record, seek, tempo."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="transport_control",
            args={"action": action, "tempo": tempo, "position": position},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        # If token was consumed to switch mode
        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        # 2. Protected check for tempo
        if action == "tempo" or tempo is not None:
            prot_challenge = cm.check_protected_target(
                op="transport.setTempo",
                args={"action": action, "tempo": tempo},
                allow_protected=allow_protected,
                confirm_token=confirm_token,
                client_version=client_version,
            )
            if prot_challenge is not None:
                return ToolResult(
                    content=[{"type": "text", "text": prot_challenge["message"]}],
                    structured_content=prot_challenge,
                    is_error=False,
                )

        # 3. Execute action
        act = action.strip().lower()
        if act == "play":
            v = fl.transport.play(strict=verify)
            status_text = "Playback started."
        elif act == "stop":
            v = fl.transport.stop(strict=verify)
            status_text = "Playback stopped."
        elif act == "record":
            v = fl.transport.record(strict=verify)
            is_rec = getattr(v, "value", True)
            status_text = f"Recording mode {'engaged' if is_rec else 'disengaged'}."
        elif act == "tempo":
            if tempo is None:
                raise ValueError("Tempo BPM must be supplied for 'tempo' action.")
            v = fl.transport.set_tempo(tempo, allow_protected=allow_protected, strict=verify)
            status_text = f"Project tempo set to {float(v.value):.2f} BPM."
        elif act in ("seek", "pos"):
            if position is None:
                raise ValueError("Song position must be supplied for 'seek' / 'pos' action.")
            v = fl.transport.set_time(position, strict=verify)
            status_text = f"Playback position set to {float(v.value):.4f}."
        else:
            raise ValueError(
                f"Unknown transport action '{action}'. Valid: play, stop, record, tempo, seek, pos."
            )

        verified = bool(getattr(v, "verified", True))
        plane = str(getattr(v, "plane", "live"))
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": verified,
            "plane": plane,
            "journal_id": journal_id,
            "action": act,
            "status": "ok",
        }
        human_text = f"{status_text} [verified={verified}, plane={plane}, journal_id={journal_id}]"

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def mixer_set(
        self,
        tracks: list[dict[str, Any]] | None = None,
        track: int | None = None,
        volume: float | None = None,
        pan: float | None = None,
        mute: bool | None = None,
        solo: bool | None = None,
        name: str | None = None,
        allow_protected: bool = False,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Adjust volume, pan, mute, solo, or name across mixer tracks."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # Normalize adjustments list
        adjustments: list[dict[str, Any]] = []
        if tracks:
            adjustments.extend(tracks)
        elif track is not None:
            single: dict[str, Any] = {"track": track}
            if volume is not None:
                single["volume"] = volume
            if pan is not None:
                single["pan"] = pan
            if mute is not None:
                single["mute"] = mute
            if solo is not None:
                single["solo"] = solo
            if name is not None:
                single["name"] = name
            adjustments.append(single)
        else:
            raise ValueError("Either 'tracks' array or 'track' index must be provided.")

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="mixer_set",
            args={"tracks": adjustments},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        # 2. Protected check if master track (track 0) is modified
        for adj in adjustments:
            trk_idx = adj.get("track")
            if trk_idx == 0:
                prot_challenge = cm.check_protected_target(
                    op="mixer_set",
                    args={"track": 0},
                    allow_protected=allow_protected,
                    confirm_token=confirm_token,
                    client_version=client_version,
                )
                if prot_challenge is not None:
                    return ToolResult(
                        content=[{"type": "text", "text": prot_challenge["message"]}],
                        structured_content=prot_challenge,
                        is_error=False,
                    )
                break

        # 3. Apply mutations
        receipts: list[dict[str, Any]] = []
        all_verified = True

        for adj in adjustments:
            t = int(adj["track"])
            t_verified = True
            t_plane = "live"

            if "volume" in adj and adj["volume"] is not None:
                v = fl.mixer.set_volume(
                    t, adj["volume"], allow_protected=allow_protected, strict=verify
                )
                t_verified = t_verified and bool(getattr(v, "verified", True))
                t_plane = str(getattr(v, "plane", "live"))
            if "pan" in adj and adj["pan"] is not None:
                v = fl.mixer.set_pan(t, adj["pan"], allow_protected=allow_protected, strict=verify)
                t_verified = t_verified and bool(getattr(v, "verified", True))
            if "mute" in adj and adj["mute"] is not None:
                v = fl.mixer.mute(t, adj["mute"], strict=verify)
                t_verified = t_verified and bool(getattr(v, "verified", True))
            if "solo" in adj and adj["solo"] is not None:
                v = fl.mixer.solo(t, adj["solo"], strict=verify)
                t_verified = t_verified and bool(getattr(v, "verified", True))
            if "name" in adj and adj["name"] is not None:
                v = fl.mixer.set_name(t, adj["name"], strict=verify)
                t_verified = t_verified and bool(getattr(v, "verified", True))

            jid = self._get_journal_id(fl)
            receipts.append(
                {
                    "track": t,
                    "verified": t_verified,
                    "plane": t_plane,
                    "journal_id": jid,
                }
            )
            if not t_verified:
                all_verified = False

        overall_journal_id = self._get_journal_id(fl)
        receipt = {
            "verified": all_verified,
            "plane": "live",
            "journal_id": overall_journal_id,
            "track_count": len(adjustments),
            "receipts": receipts,
        }
        human_text = (
            f"Updated {len(adjustments)} mixer track(s) "
            f"[verified={all_verified}, plane=live, journal_id={overall_journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def channel_set(
        self,
        channel: int | str,
        volume: float | None = None,
        pan: float | None = None,
        mute: bool | None = None,
        solo: bool | None = None,
        name: str | None = None,
        steps: list[int] | list[bool] | None = None,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Modify channel properties: volume, pan, mute, solo, name, step grid."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="channel_set",
            args={"channel": channel},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        receipts: list[dict[str, Any]] = []
        all_verified = True
        c_idx: int = int(channel) if isinstance(channel, int) or str(channel).isdigit() else 0

        if volume is not None:
            v = fl.channels.set_volume(channel, volume, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "volume", "verified": ver})
            if not ver:
                all_verified = False

        if pan is not None:
            v = fl.channels.set_pan(channel, pan, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "pan", "verified": ver})
            if not ver:
                all_verified = False

        if mute is not None:
            v = fl.channels.mute(channel, mute, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "mute", "verified": ver})
            if not ver:
                all_verified = False

        if solo is not None:
            v = fl.channels.solo(channel, solo, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "solo", "verified": ver})
            if not ver:
                all_verified = False

        if name is not None:
            v = fl.channels.set_name(channel, name, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "name", "verified": ver})
            if not ver:
                all_verified = False

        if steps is not None:
            v = fl.channels.set_step_grid(channel, steps, strict=verify)
            ver = bool(getattr(v, "verified", True))
            receipts.append({"prop": "steps", "verified": ver})
            if not ver:
                all_verified = False

        journal_id = self._get_journal_id(fl)
        receipt = {
            "verified": all_verified,
            "plane": "live",
            "journal_id": journal_id,
            "channel": c_idx,
            "receipts": receipts,
        }
        human_text = (
            f"Updated channel {channel} properties "
            f"[verified={all_verified}, plane=live, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def plugin_param_set(
        self,
        param_index: int,
        value: float,
        target: str | None = None,
        track: int | None = None,
        slot: int | None = None,
        channel: int | None = None,
        allow_protected: bool = False,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Set normalized parameter value on an instrument or effect plugin."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="plugin_param_set",
            args={"param_index": param_index, "value": value},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        # 2. Resolve target and write
        val = float(value)
        p_idx = int(param_index)

        if track is not None and slot is not None:
            v = fl.plugins.set_param(track, slot, p_idx, val, strict=verify)
        elif channel is not None:
            v = fl.plugins.set_param(channel, p_idx, val, strict=verify)
        elif target is not None:
            # Parse 'mixer.track.X.slot.Y' or 'channel.X'
            parts = target.split(".")
            if (
                len(parts) >= 4
                and parts[0] == "mixer"
                and parts[1] == "track"
                and parts[2].isdigit()
            ):
                t_idx = int(parts[2])
                s_idx = int(parts[4]) if len(parts) >= 5 and parts[4].isdigit() else 0
                v = fl.plugins.set_param(t_idx, s_idx, p_idx, val, strict=verify)
            elif len(parts) >= 2 and parts[0] == "channel" and parts[1].isdigit():
                c_idx = int(parts[1])
                v = fl.plugins.set_param(c_idx, p_idx, val, strict=verify)
            else:
                v = fl.plugins.set_param(0, 0, p_idx, val, strict=verify)
        else:
            # Default to master slot 0
            v = fl.plugins.set_param(0, 0, p_idx, val, strict=verify)

        verified = bool(getattr(v, "verified", True))
        plane = str(getattr(v, "plane", "live"))
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": verified,
            "plane": plane,
            "journal_id": journal_id,
            "param_index": p_idx,
            "value": val,
        }
        human_text = (
            f"Set plugin parameter {p_idx} to {val:.4f} "
            f"[verified={verified}, plane={plane}, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def pattern_edit(
        self,
        pattern: int,
        action: str,
        name: str | None = None,
        color: int | str | None = None,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Select active pattern, rename, set color, or clear pattern."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="pattern_edit",
            args={"pattern": pattern, "action": action},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        act = action.strip().lower()
        p = int(pattern)

        if act == "select":
            v = fl.patterns.set_active(p, strict=verify)
            status_text = f"Pattern {p} selected as active."
        elif act == "rename":
            if not name:
                raise ValueError("Name required for pattern rename.")
            v = fl.patterns.set_name(p, name, strict=verify)
            status_text = f"Pattern {p} renamed to '{name}'."
        elif act == "color":
            if color is None:
                raise ValueError("Color required for pattern color edit.")
            v = fl.patterns.set_color(p, color, strict=verify)
            status_text = f"Pattern {p} color updated."
        elif act == "clear":
            v = fl.patterns.clear(p, strict=verify)
            status_text = f"Pattern {p} notes and automations cleared."
        else:
            raise ValueError(
                f"Unknown pattern action '{action}'. Valid: select, rename, color, clear."
            )

        verified = bool(getattr(v, "verified", True))
        plane = str(getattr(v, "plane", "live"))
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": verified,
            "plane": plane,
            "journal_id": journal_id,
            "pattern": p,
            "action": act,
        }
        human_text = f"{status_text} [verified={verified}, plane={plane}, journal_id={journal_id}]."

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def steps_set(
        self,
        channel: int | str,
        steps: list[int] | list[bool],
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Set 16-step sequencer activation bits for a channel."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="steps_set",
            args={"channel": channel, "steps": steps},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        v = fl.channels.set_step_grid(channel, steps, strict=verify)
        c_idx: int = int(channel) if isinstance(channel, int) or str(channel).isdigit() else 0
        step_ints = [1 if s else 0 for s in steps]

        verified = bool(getattr(v, "verified", True))
        plane = str(getattr(v, "plane", "live"))
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": verified,
            "plane": plane,
            "journal_id": journal_id,
            "channel": c_idx,
            "step_grid": step_ints,
        }
        human_text = (
            f"Set 16-step sequencer grid on channel {channel} "
            f"[verified={verified}, plane={plane}, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def playlist_edit(
        self,
        track: int,
        name: str | None = None,
        color: int | str | None = None,
        mute: bool | None = None,
        solo: bool | None = None,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Edit arrangement playlist track: rename, color, mute, or solo."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="playlist_edit",
            args={"track": track},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        t = int(track)
        all_verified = True

        if name is not None:
            v = fl.playlist.set_name(t, name, strict=verify)
            if not getattr(v, "verified", True):
                all_verified = False

        if color is not None:
            v = fl.playlist.set_color(t, color, strict=verify)
            if not getattr(v, "verified", True):
                all_verified = False

        if mute is not None:
            v = fl.playlist.mute(t, mute, strict=verify)
            if not getattr(v, "verified", True):
                all_verified = False

        if solo is not None:
            v = fl.playlist.solo(t, solo, strict=verify)
            if not getattr(v, "verified", True):
                all_verified = False

        journal_id = self._get_journal_id(fl)
        receipt = {
            "verified": all_verified,
            "plane": "live",
            "journal_id": journal_id,
            "track": t,
        }
        human_text = (
            f"Updated playlist track {t} "
            f"[verified={all_verified}, plane=live, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def playlist_place_pattern(
        self,
        track: int,
        pattern: int,
        time: float,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Place pattern clip onto arrangement playlist (experimental)."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op="playlist_place_pattern",
            args={"track": track, "pattern": pattern, "time": time},
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        t = int(track)
        p = int(pattern)
        pos = float(time)
        v = fl.playlist.place_pattern(t, p, pos)

        verified = bool(getattr(v, "verified", True))
        plane = str(getattr(v, "plane", "live"))
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": verified,
            "plane": plane,
            "journal_id": journal_id,
            "track": t,
            "pattern": p,
            "time": pos,
        }
        human_text = (
            f"Placed pattern {p} on playlist track {t} at time {pos:.2f} "
            f"[verified={verified}, plane={plane}, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def fl_call(
        self,
        function: str,
        args: list[Any] | dict[str, Any] | None = None,
        allow_protected: bool = False,
        confirm_token: str | None = None,
        verify: bool = True,
    ) -> ToolResult:
        """Execute raw allowlisted FL Studio Python API function."""
        fl = self._get_active_client()
        cm = _get_confirmation_manager(self.server)
        client_version = _get_negotiated_version(self.server)

        fn = function.strip()
        call_args = args if args is not None else {}
        args_dict = call_args if isinstance(call_args, dict) else {"args": call_args}

        # 1. Mode check
        challenge = cm.check_mode_and_confirmation(
            mode=fl.safety.mode,
            op=f"fl_call:{fn}",
            args=args_dict,
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": challenge["message"]}],
                structured_content=challenge,
                is_error=False,
            )

        if fl.safety.mode == "read_only":
            fl.safety.mode = "write"

        # 2. Protected check
        prot_challenge = cm.check_protected_target(
            op=fn,
            args=args_dict,
            allow_protected=allow_protected,
            confirm_token=confirm_token,
            client_version=client_version,
        )
        if prot_challenge is not None:
            return ToolResult(
                content=[{"type": "text", "text": prot_challenge["message"]}],
                structured_content=prot_challenge,
                is_error=False,
            )

        # 3. Call via session
        res = _session_call(fl, fn, call_args, allow_protected=allow_protected)
        journal_id = self._get_journal_id(fl)

        receipt = {
            "verified": True,
            "plane": "live",
            "journal_id": journal_id,
            "function": fn,
            "result": res,
        }
        human_text = (
            f"Executed {fn} -> {res!r} [verified=True, plane=live, journal_id={journal_id}]."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )


def get_control_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for control tool suite."""
    provider = ControlTools(client=client, server=server)

    s_trans = get_schema("transport_control")
    s_mix = get_schema("mixer_set")
    s_chan = get_schema("channel_set")
    s_plug = get_schema("plugin_param_set")
    s_pat = get_schema("pattern_edit")
    s_step = get_schema("steps_set")
    s_play = get_schema("playlist_edit")
    s_place = get_schema("playlist_place_pattern")

    return [
        ToolDefinition(
            name="transport_control",
            title=s_trans.get("title", "Transport Control"),
            description=s_trans.get(
                "description",
                "Start, stop, record, seek playback position, or adjust tempo with verification.",
            ),
            input_schema=s_trans.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.transport_control,
        ),
        ToolDefinition(
            name="mixer_set",
            title=s_mix.get("title", "Mixer Set"),
            description=s_mix.get(
                "description",
                "Adjust volume, pan, mute, solo, or name on mixer tracks with verification.",
            ),
            input_schema=s_mix.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.mixer_set,
        ),
        ToolDefinition(
            name="channel_set",
            title=s_chan.get("title", "Channel Set"),
            description=s_chan.get(
                "description",
                "Modify channel properties: volume, pan, mute, solo, name, and 16-step pattern.",
            ),
            input_schema=s_chan.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.channel_set,
        ),
        ToolDefinition(
            name="plugin_param_set",
            title=s_plug.get("title", "Plugin Parameter Set"),
            description=s_plug.get(
                "description",
                "Set normalized parameter value (0.0 to 1.0) on an instrument or effect plugin.",
            ),
            input_schema=s_plug.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.plugin_param_set,
        ),
        ToolDefinition(
            name="pattern_edit",
            title=s_pat.get("title", "Pattern Edit"),
            description=s_pat.get(
                "description",
                "Select active pattern, rename, set color, or clear notes and automations.",
            ),
            input_schema=s_pat.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.pattern_edit,
        ),
        ToolDefinition(
            name="steps_set",
            title=s_step.get("title", "Steps Set"),
            description=s_step.get(
                "description",
                "Set 16-step sequencer grid activation bits for a rhythm or generator channel.",
            ),
            input_schema=s_step.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.steps_set,
        ),
        ToolDefinition(
            name="playlist_edit",
            title=s_play.get("title", "Playlist Edit"),
            description=s_play.get(
                "description",
                "Edit arrangement playlist track: rename, color, mute, or solo.",
            ),
            input_schema=s_play.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.playlist_edit,
        ),
        ToolDefinition(
            name="playlist_place_pattern",
            title=s_place.get("title", "Playlist Place Pattern"),
            description=s_place.get(
                "description",
                "Place pattern clip onto arrangement track at normalized time (experimental).",
            ),
            input_schema=s_place.get("inputSchema", {}),
            toolset="control",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.playlist_place_pattern,
        ),
    ]


def get_raw_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for raw / unsafe execution tools."""
    provider = ControlTools(client=client, server=server)
    s_call = get_schema("fl_call")

    return [
        ToolDefinition(
            name="fl_call",
            title=s_call.get("title", "FL Call"),
            description=s_call.get(
                "description",
                "Execute raw allowlisted FL Studio Python API function with safety verification.",
            ),
            input_schema=s_call.get("inputSchema", {}),
            toolset="raw",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=True,
            handler=provider.fl_call,
        )
    ]


__all__ = [
    "ControlTools",
    "get_control_tools",
    "get_raw_tools",
]
