"""Inspect MCP tools for StudioBridge mixer, transport, rack, and playlist.

Implements inspection tools:
- transport_get: Current playback state, tempo, position, and signature.
- mixer_list: List mixer tracks with volume, pan, peaks, and routing (paginated).
- mixer_get: Get a single mixer track by index or name.
- channels_list: List channels with channel properties and step bits (paginated).
- channel_get: Get a single channel by index or name.
- patterns_list: List patterns with pattern names, lengths, and active selection (paginated).
- playlist_get: Playlist summary, track counts, track properties (paginated).
- plugin_params_list: List plugin parameters for a given track and slot (paginated).
- plugin_param_get: Get a single plugin parameter by param_id.
- events_recent: Recent events with topic filtering and pagination.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from studiobridge.core.errors import DisconnectedError
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult
from studiobridge.sdk.units import Volume


def _resolve_client(client: Any = None, server: Any = None) -> Any:
    """Resolve an active Studio client from server reference or argument."""
    if client is not None:
        return client
    if server is not None and getattr(server, "client", None) is not None:
        return server.client
    return None


def apply_pagination_and_fields(
    items: list[dict[str, Any]],
    cursor: int,
    limit: int,
    fields: Sequence[str] | str | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """Slice items according to cursor/limit and project requested fields.

    Returns (sliced_and_projected_items, next_cursor).
    """
    sliced = items[cursor : cursor + limit]
    next_cursor = cursor + limit if cursor + limit < len(items) else None

    if not fields or fields == "all" or fields == ["all"]:
        return sliced, next_cursor

    if isinstance(fields, str):
        field_set = {f.strip() for f in fields.split(",") if f.strip()}
    else:
        field_set = set(fields)

    projected = [{k: v for k, v in item.items() if k in field_set} for item in sliced]
    return projected, next_cursor


class InspectTools:
    """Provider for StudioBridge read-only inspection MCP tools."""

    def __init__(self, client: Any = None, server: Any = None) -> None:
        self.client = client
        self.server = server

    def _get_active_client(self) -> Any:
        resolved = _resolve_client(self.client, self.server)
        if resolved is not None:
            return resolved
        from studiobridge.sdk.client import Studio

        try:
            return Studio.connect(timeout=2.0)
        except Exception as exc:
            raise DisconnectedError(
                f"No active StudioBridge connection: {exc}",
                remedy=(
                    "Ensure FL Studio and the StudioBridge broker daemon are running "
                    "('sbridge broker start')."
                ),
            ) from exc

    def transport_get(self, **kwargs: Any) -> ToolResult:
        """Get current FL Studio transport state: playback status, tempo, position, signature."""
        client = self._get_active_client()

        is_playing = bool(client.transport.is_playing())
        tempo = float(client.transport.get_tempo())
        song_pos = int(client.transport.get_time())
        loop_mode = str(client.transport.get_loop_mode())
        time_sig = list(client.transport.get_time_signature())

        # Calculate approximate time in seconds based on PPQ = 96 default
        seconds = song_pos / (tempo * 96.0 / 60.0) if tempo > 0 else 0.0

        structured = {
            "is_playing": is_playing,
            "tempo": tempo,
            "song_pos": song_pos,
            "song_time_s": round(seconds, 3),
            "loop_mode": loop_mode,
            "time_signature": [int(time_sig[0]), int(time_sig[1])],
        }
        summary_text = (
            f"Transport: {'PLAYING' if is_playing else 'STOPPED'}, {tempo:.2f} BPM, "
            f"Pos: {song_pos} ticks ({seconds:.2f}s), "
            f"Mode: {loop_mode}, Sig: {time_sig[0]}/{time_sig[1]}"
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def mixer_list(
        self,
        limit: int = 40,
        cursor: int = 0,
        fields: Sequence[str] | str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """List mixer tracks with volume, pan, peak meters, mute/solo, and routing."""
        client = self._get_active_client()
        all_tracks = client.mixer.get_tracks()

        raw_items: list[dict[str, Any]] = []
        for trk in all_tracks:
            raw_items.append(
                {
                    "index": trk.index,
                    "name": trk.name,
                    "volume": round(trk.volume, 4),
                    "volume_db": round(Volume(trk.volume).to_db(), 2),
                    "pan": round(trk.pan, 4),
                    "muted": trk.muted,
                    "solo": trk.solo,
                    "armed": trk.armed,
                    "color": trk.color,
                    "peak": round(trk.peak, 4),
                }
            )

        projected, next_cursor = apply_pagination_and_fields(
            raw_items, cursor=cursor, limit=limit, fields=fields
        )

        structured = {
            "tracks": projected,
            "total": len(raw_items),
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        summary_text = (
            f"Mixer tracks {cursor}..{cursor + len(projected) - 1} of {len(raw_items)} "
            f"(limit {limit})"
            + (f", next cursor: {next_cursor}" if next_cursor is not None else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def mixer_get(self, track: int | str, **kwargs: Any) -> ToolResult:
        """Get detailed status, levels, peak metering, and routing for a single mixer track."""
        client = self._get_active_client()

        if isinstance(track, str) and not track.isdigit():
            track_ref = client.mixer.find(track)
            track_idx = track_ref.index
        else:
            track_idx = int(track)

        t = client.mixer.get_track(track_idx)
        peak = client.mixer.get_peak(track_idx)

        structured = {
            "index": t.index,
            "name": t.name,
            "volume": round(t.volume, 4),
            "volume_db": round(Volume(t.volume).to_db(), 2),
            "pan": round(t.pan, 4),
            "muted": t.muted,
            "solo": t.solo,
            "armed": t.armed,
            "color": t.color,
            "peak": peak,
        }
        summary_text = (
            f"Mixer Track {t.index} ('{t.name}'): {structured['volume_db']} dB, "
            f"Pan: {t.pan:+.2f}, {'MUTED' if t.muted else 'ACTIVE'}, {'SOLO' if t.solo else ''}"
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def channels_list(
        self,
        limit: int = 20,
        cursor: int = 0,
        fields: Sequence[str] | str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """List generator channels with volume, pan, mute/solo, and step bits."""
        client = self._get_active_client()
        total_channels = client.channels.count()
        all_channels = client.channels.list()

        raw_items: list[dict[str, Any]] = []
        for ch in all_channels:
            step_grid = getattr(ch, "step_grid", []) or []
            step_bits = sum((1 << i) for i, bit in enumerate(step_grid) if bit)
            raw_items.append(
                {
                    "index": ch.index,
                    "name": ch.name,
                    "color": ch.color,
                    "volume": round(ch.volume, 4),
                    "pan": round(ch.pan, 4),
                    "pitch": round(ch.pitch, 2),
                    "muted": ch.muted,
                    "solo": ch.solo,
                    "step_bits": step_bits,
                }
            )

        projected, next_cursor = apply_pagination_and_fields(
            raw_items, cursor=cursor, limit=limit, fields=fields
        )

        structured = {
            "channels": projected,
            "total": total_channels,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        summary_text = (
            f"Channels {cursor}..{cursor + len(projected) - 1} of {total_channels} (limit {limit})"
            + (f", next cursor: {next_cursor}" if next_cursor is not None else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def channel_get(self, channel: int | str, **kwargs: Any) -> ToolResult:
        """Get detailed properties of a generator channel, including step sequencer grid."""
        client = self._get_active_client()

        if isinstance(channel, str) and not channel.isdigit():
            ch_ref = client.channels.find(channel)
            ch_idx = ch_ref.index
        else:
            ch_idx = int(channel)

        ch = client.channels.get_channel(ch_idx)
        grid = client.channels.get_step_grid(ch_idx)
        step_bits = sum((1 << i) for i, bit in enumerate(grid) if bit)

        structured = {
            "index": ch.index,
            "name": ch.name,
            "color": ch.color,
            "volume": round(ch.volume, 4),
            "pan": round(ch.pan, 4),
            "pitch": round(ch.pitch, 2),
            "muted": ch.muted,
            "solo": ch.solo,
            "step_grid": grid,
            "step_bits": step_bits,
        }
        summary_text = (
            f"Channel {ch.index} ('{ch.name}'): Vol: {ch.volume:.2f}, Pan: {ch.pan:+.2f}, "
            f"{'MUTED' if ch.muted else 'ACTIVE'}, Steps: {step_bits:016b}"
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def patterns_list(
        self,
        limit: int = 20,
        cursor: int = 1,
        fields: Sequence[str] | str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """List patterns in the project with names, lengths, colors, and active selection."""
        client = self._get_active_client()
        total_patterns = client.patterns.count()
        active_pattern = int(
            getattr(client.patterns.get_active(), "number", client.patterns.get_active())
        )
        all_patterns = client.patterns.list()

        raw_items: list[dict[str, Any]] = []
        for pat in all_patterns:
            length = client.patterns.get_length(pat.number)
            raw_items.append(
                {
                    "number": pat.number,
                    "name": pat.name,
                    "color": pat.color,
                    "length_ticks": length,
                    "is_active": pat.number == active_pattern,
                }
            )

        # Note: patterns are 1-based, cursor is 1-based
        offset = max(0, cursor - 1)
        sliced = raw_items[offset : offset + limit]
        next_cursor = cursor + limit if cursor + limit <= total_patterns else None

        if fields and fields != "all" and fields != ["all"]:
            field_set = (
                set(fields)
                if not isinstance(fields, str)
                else {f.strip() for f in fields.split(",") if f.strip()}
            )
            projected = [{k: v for k, v in item.items() if k in field_set} for item in sliced]
        else:
            projected = sliced

        structured = {
            "patterns": projected,
            "total": total_patterns,
            "active_pattern": active_pattern,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        summary_text = (
            f"Patterns {cursor}..{cursor + len(projected) - 1} of {total_patterns} "
            f"(active: Pattern {active_pattern}, limit {limit})"
            + (f", next cursor: {next_cursor}" if next_cursor is not None else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def playlist_get(
        self,
        limit: int = 40,
        cursor: int = 1,
        fields: Sequence[str] | str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Get playlist track information, track counts, names, and mute/solo states."""
        client = self._get_active_client()
        total_tracks = client.playlist.count()
        all_tracks = client.playlist.list()

        raw_items: list[dict[str, Any]] = []
        for trk in all_tracks:
            raw_items.append(
                {
                    "number": trk.number,
                    "name": trk.name,
                    "color": trk.color,
                    "muted": trk.muted,
                    "solo": trk.solo,
                }
            )

        offset = max(0, cursor - 1)
        sliced = raw_items[offset : offset + limit]
        next_cursor = cursor + limit if cursor + limit <= total_tracks else None

        if fields and fields != "all" and fields != ["all"]:
            field_set = (
                set(fields)
                if not isinstance(fields, str)
                else {f.strip() for f in fields.split(",") if f.strip()}
            )
            projected = [{k: v for k, v in item.items() if k in field_set} for item in sliced]
        else:
            projected = sliced

        structured = {
            "track_count": total_tracks,
            "tracks": projected,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        range_end = cursor + len(projected) - 1
        summary_text = (
            f"Playlist Tracks {cursor}..{range_end} of {total_tracks} (limit {limit})"
            + (f", next cursor: {next_cursor}" if next_cursor is not None else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def plugin_params_list(
        self,
        track: int,
        slot: int,
        limit: int = 50,
        cursor: int = 0,
        fields: Sequence[str] | str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """List parameters of an effect plugin on a mixer track slot."""
        client = self._get_active_client()

        info = client.plugins.get_plugin(track, slot)
        param_count = info.param_count

        raw_items: list[dict[str, Any]] = []
        for p_idx in range(param_count):
            param = client.plugins.get_param(track, slot, p_idx)
            raw_items.append(
                {
                    "param_id": param.param_id,
                    "name": param.name,
                    "value": round(param.value, 4),
                    "min_value": param.min_value,
                    "max_value": param.max_value,
                    "text": param.text,
                }
            )

        projected, next_cursor = apply_pagination_and_fields(
            raw_items, cursor=cursor, limit=limit, fields=fields
        )

        structured = {
            "plugin_name": info.name,
            "param_count": param_count,
            "params": projected,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        summary_text = (
            f"Plugin '{info.name}' (Track {track}, Slot {slot}) params "
            f"{cursor}..{cursor + len(projected) - 1} of {param_count} (limit {limit})"
            + (f", next cursor: {next_cursor}" if next_cursor is not None else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def plugin_param_get(
        self,
        track: int,
        slot: int,
        param_id: int,
        **kwargs: Any,
    ) -> ToolResult:
        """Get the current value and metadata of a specific plugin parameter."""
        client = self._get_active_client()

        param = client.plugins.get_param(track, slot, param_id)
        structured = {
            "track": track,
            "slot": slot,
            "param_id": param.param_id,
            "name": param.name,
            "value": round(param.value, 4),
            "min_value": param.min_value,
            "max_value": param.max_value,
            "text": param.text,
        }
        summary_text = (
            f"Param {param.param_id} ('{param.name}') on Track {track}, Slot {slot}: "
            f"{param.value:.4f} ('{param.text}')"
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )

    def events_recent(
        self,
        limit: int = 20,
        cursor: int = 0,
        topic: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Retrieve recent events dispatched by the broker and FL Studio device script."""
        client = self._get_active_client()

        events = client.events.get_recent(limit=limit, cursor=cursor, topic=topic)
        total_matching = client.events.count_recent(topic=topic)
        next_cursor = cursor + limit if cursor + limit < total_matching else None

        event_dicts = [e.to_dict() for e in events]
        structured = {
            "events": event_dicts,
            "total": total_matching,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
        }
        summary_text = (
            f"Recent events: {len(events)} returned of {total_matching} total "
            f"(offset {cursor}, limit {limit})" + (f" [topic filter: '{topic}']" if topic else "")
        )
        return ToolResult(
            content=[{"type": "text", "text": summary_text}],
            structured_content=structured,
            is_error=False,
        )


def get_inspect_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Instantiate and return the list of inspect ToolDefinitions."""
    provider = InspectTools(client=client, server=server)

    s_transport = get_schema("transport_get")
    s_mixer_list = get_schema("mixer_list")
    s_mixer_get = get_schema("mixer_get")
    s_ch_list = get_schema("channels_list")
    s_ch_get = get_schema("channel_get")
    s_pat_list = get_schema("patterns_list")
    s_play_get = get_schema("playlist_get")
    s_plug_list = get_schema("plugin_params_list")
    s_plug_get = get_schema("plugin_param_get")
    s_evt_recent = get_schema("events_recent")

    return [
        ToolDefinition(
            name="transport_get",
            title=s_transport.get("title", "Transport Get"),
            description=s_transport.get(
                "description",
                "Get current FL Studio transport state: status, tempo, position, signature.",
            ),
            input_schema=s_transport.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.transport_get,
        ),
        ToolDefinition(
            name="mixer_list",
            title=s_mixer_list.get("title", "Mixer List"),
            description=s_mixer_list.get(
                "description",
                "List mixer tracks with volume, pan, peak meters, mute/solo, and routing.",
            ),
            input_schema=s_mixer_list.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.mixer_list,
        ),
        ToolDefinition(
            name="mixer_get",
            title=s_mixer_get.get("title", "Mixer Get"),
            description=s_mixer_get.get(
                "description",
                "Get detailed status, levels, peak metering, and routing for a mixer track.",
            ),
            input_schema=s_mixer_get.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.mixer_get,
        ),
        ToolDefinition(
            name="channels_list",
            title=s_ch_list.get("title", "Channels List"),
            description=s_ch_list.get(
                "description",
                "List generator channels in the channel rack with volume, pan, mute/solo.",
            ),
            input_schema=s_ch_list.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.channels_list,
        ),
        ToolDefinition(
            name="channel_get",
            title=s_ch_get.get("title", "Channel Get"),
            description=s_ch_get.get(
                "description",
                "Get detailed properties of a single generator channel by index or name.",
            ),
            input_schema=s_ch_get.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.channel_get,
        ),
        ToolDefinition(
            name="patterns_list",
            title=s_pat_list.get("title", "Patterns List"),
            description=s_pat_list.get(
                "description",
                "List patterns in the project with names, lengths, colors, and active status.",
            ),
            input_schema=s_pat_list.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.patterns_list,
        ),
        ToolDefinition(
            name="playlist_get",
            title=s_play_get.get("title", "Playlist Get"),
            description=s_play_get.get(
                "description",
                "Get playlist track information, counts, names, mute/solo, and settings.",
            ),
            input_schema=s_play_get.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.playlist_get,
        ),
        ToolDefinition(
            name="plugin_params_list",
            title=s_plug_list.get("title", "Plugin Params List"),
            description=s_plug_list.get(
                "description",
                "List parameters of an effect or generator plugin.",
            ),
            input_schema=s_plug_list.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.plugin_params_list,
        ),
        ToolDefinition(
            name="plugin_param_get",
            title=s_plug_get.get("title", "Plugin Param Get"),
            description=s_plug_get.get(
                "description",
                "Get current value and metadata of a specific plugin parameter.",
            ),
            input_schema=s_plug_get.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.plugin_param_get,
        ),
        ToolDefinition(
            name="events_recent",
            title=s_evt_recent.get("title", "Events Recent"),
            description=s_evt_recent.get(
                "description",
                "Retrieve recent events dispatched by broker and FL Studio device script.",
            ),
            input_schema=s_evt_recent.get("inputSchema", {}),
            toolset="inspect",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.events_recent,
        ),
    ]


__all__ = [
    "InspectTools",
    "apply_pagination_and_fields",
    "get_inspect_tools",
]
