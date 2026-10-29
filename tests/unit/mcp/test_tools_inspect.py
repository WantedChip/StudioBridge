"""Unit tests for StudioBridge inspect MCP tools.

Verifies:
1. Tool catalog and annotations: readOnlyHint=True, idempotentHint=True, openWorldHint=False.
2. Pagination and field selection across mixer_list, channels_list, patterns_list,
   playlist_get, plugin_params_list, and events_recent.
3. Functional inspection of transport_get, mixer_get, channel_get, plugin_param_get.
4. Conformance against frozen JSON schemas in studiobridge.mcp.schemas.
"""

from __future__ import annotations

import pytest

from studiobridge.core.errors import DisconnectedError
from studiobridge.mcp.schemas import get_schema, validate_schema
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.mcp.tools.inspect import (
    InspectTools,
    apply_pagination_and_fields,
    get_inspect_tools,
)
from studiobridge.sdk.client import Studio


class TestInspectToolsMetadata:
    """Verifies catalog, annotations, and input schemas for all inspect tools."""

    def test_inspect_tools_catalog_and_annotations(self) -> None:
        """All 10 inspect tools are defined with correct read-only hints."""
        tools = get_inspect_tools()
        assert len(tools) == 10

        names = {t.name for t in tools}
        expected = {
            "transport_get",
            "mixer_list",
            "mixer_get",
            "channels_list",
            "channel_get",
            "patterns_list",
            "playlist_get",
            "plugin_params_list",
            "plugin_param_get",
            "events_recent",
        }
        assert names == expected

        for t in tools:
            assert t.toolset == "inspect"
            assert t.read_only is True
            assert t.destructive is False
            assert t.idempotent is True
            assert t.open_world is False
            assert t.title is not None

            # Verify MCP annotations
            mcp_dict = t.to_mcp_dict()
            ann = mcp_dict["annotations"]
            assert ann["readOnlyHint"] is True
            assert ann["destructiveHint"] is False
            assert ann["idempotentHint"] is True
            assert ann["openWorldHint"] is False

    def test_input_schemas_match_stored_definitions(self) -> None:
        """Input schemas match frozen JSON schemas."""
        tools = get_inspect_tools()
        for t in tools:
            schema = get_schema(t.name)
            assert t.input_schema == schema.get("inputSchema")


class TestPaginationHelper:
    """Verifies apply_pagination_and_fields helper function."""

    def test_pagination_slicing(self) -> None:
        items = [{"id": i, "name": f"item_{i}"} for i in range(10)]
        sliced, next_cur = apply_pagination_and_fields(items, cursor=2, limit=3)

        assert len(sliced) == 3
        assert sliced[0]["id"] == 2
        assert sliced[2]["id"] == 4
        assert next_cur == 5

    def test_pagination_end_of_list(self) -> None:
        items = [{"id": i} for i in range(5)]
        sliced, next_cur = apply_pagination_and_fields(items, cursor=3, limit=5)

        assert len(sliced) == 2
        assert next_cur is None

    def test_field_projection(self) -> None:
        items = [{"id": 1, "name": "foo", "extra": "bar"}]
        projected, _ = apply_pagination_and_fields(items, cursor=0, limit=1, fields=["id", "name"])

        assert projected[0] == {"id": 1, "name": "foo"}
        assert "extra" not in projected[0]


class TestTransportGetTool:
    """Tests for transport_get tool."""

    def test_transport_get_connected(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.transport_get()

        assert res.is_error is False
        data = res.structured_content
        assert isinstance(data["is_playing"], bool)
        assert isinstance(data["tempo"], float)
        assert isinstance(data["song_pos"], int)
        assert isinstance(data["time_signature"], list)
        assert len(data["time_signature"]) == 2

        schema = get_schema("transport_get")
        validate_schema(data, schema["outputSchema"])


class TestMixerTools:
    """Tests for mixer_list and mixer_get tools."""

    def test_mixer_list_default_pagination(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.mixer_list(limit=5, cursor=0)

        assert res.is_error is False
        data = res.structured_content
        assert len(data["tracks"]) == 5
        assert data["total"] >= 16
        assert data["limit"] == 5
        assert data["cursor"] == 0
        assert data["next_cursor"] == 5

        schema = get_schema("mixer_list")
        validate_schema(data, schema["outputSchema"])

    def test_mixer_list_field_projection(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.mixer_list(limit=5, cursor=0, fields=["index", "name", "volume"])

        data = res.structured_content
        assert len(data["tracks"]) == 5
        for trk in data["tracks"]:
            assert set(trk.keys()) == {"index", "name", "volume"}

    def test_mixer_get_by_index_and_name(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)

        # By index 0 (Master)
        res0 = inspect.mixer_get(track=0)
        assert res0.is_error is False
        data0 = res0.structured_content
        assert data0["index"] == 0
        assert data0["name"] == "Master"
        assert "volume" in data0
        assert "pan" in data0
        assert "peak" in data0

        schema = get_schema("mixer_get")
        validate_schema(data0, schema["outputSchema"])

        # By name "Master"
        res_named = inspect.mixer_get(track="Master")
        assert res_named.structured_content["index"] == 0


class TestChannelsTools:
    """Tests for channels_list and channel_get tools."""

    def test_channels_list_pagination(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.channels_list(limit=10, cursor=0)

        assert res.is_error is False
        data = res.structured_content
        assert "channels" in data
        assert data["total"] >= 0
        assert data["limit"] == 10

        schema = get_schema("channels_list")
        validate_schema(data, schema["outputSchema"])

    def test_channel_get_properties_and_grid(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.channel_get(channel=0)

        assert res.is_error is False
        data = res.structured_content
        assert data["index"] == 0
        assert "name" in data
        assert "volume" in data
        assert "step_grid" in data
        assert isinstance(data["step_grid"], list)

        schema = get_schema("channel_get")
        validate_schema(data, schema["outputSchema"])


class TestPatternsTools:
    """Tests for patterns_list tool."""

    def test_patterns_list_pagination(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.patterns_list(limit=10, cursor=1)

        assert res.is_error is False
        data = res.structured_content
        assert "patterns" in data
        assert data["total"] >= 1
        assert "active_pattern" in data
        assert data["cursor"] == 1

        schema = get_schema("patterns_list")
        validate_schema(data, schema["outputSchema"])


class TestPlaylistTools:
    """Tests for playlist_get tool."""

    def test_playlist_get_pagination(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.playlist_get(limit=10, cursor=1)

        assert res.is_error is False
        data = res.structured_content
        assert "tracks" in data
        assert data["track_count"] >= 1
        assert len(data["tracks"]) <= 10

        schema = get_schema("playlist_get")
        validate_schema(data, schema["outputSchema"])


class TestPluginParamsTools:
    """Tests for plugin_params_list and plugin_param_get tools."""

    def test_plugin_params_list(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.plugin_params_list(track=0, slot=0, limit=5, cursor=0)

        assert res.is_error is False
        data = res.structured_content
        assert "plugin_name" in data
        assert "param_count" in data
        assert "params" in data

        schema = get_schema("plugin_params_list")
        validate_schema(data, schema["outputSchema"])

    def test_plugin_param_get(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)
        res = inspect.plugin_param_get(track=0, slot=0, param_id=0)

        assert res.is_error is False
        data = res.structured_content
        assert data["track"] == 0
        assert data["slot"] == 0
        assert data["param_id"] == 0
        assert "name" in data
        assert "value" in data

        schema = get_schema("plugin_param_get")
        validate_schema(data, schema["outputSchema"])


class TestEventsRecentTool:
    """Tests for events_recent tool."""

    def test_events_recent_captures_dispatched_events(self, studio: Studio) -> None:
        inspect = InspectTools(client=studio)

        # Dispatch test events
        studio.events.dispatch("transport", {"is_playing": True, "tempo": 128.0})
        studio.events.dispatch("beat", {"beat": 1, "bar": 1, "tick": 0})
        studio.events.dispatch("dirty.mixer", {"target": "mixer", "is_dirty": True})

        # Query all recent events
        res = inspect.events_recent(limit=10, cursor=0)
        assert res.is_error is False
        data = res.structured_content
        assert data["total"] >= 3
        assert len(data["events"]) >= 3

        schema = get_schema("events_recent")
        validate_schema(data, schema["outputSchema"])

        # Query filtered by topic
        res_filtered = inspect.events_recent(limit=10, topic="transport")
        data_filtered = res_filtered.structured_content
        assert all(e["topic"] == "transport" for e in data_filtered["events"])


class TestDisconnectedHandling:
    """Verifies that calling inspection tools without active connection raises DisconnectedError."""

    def test_disconnected_error_raised(self) -> None:
        inspect = InspectTools(client=None)
        with pytest.raises(DisconnectedError):
            inspect.transport_get()


class TestServerInspectToolsIntegration:
    """Tests StudioMcpServer dispatch for inspect tools."""

    def test_server_call_tool_transport_get(self, studio: Studio) -> None:
        server = StudioMcpServer(toolsets="inspect", client=studio)
        res = server.call_tool("transport_get", {})

        assert res["isError"] is False
        assert "structuredContent" in res
        assert "tempo" in res["structuredContent"]
