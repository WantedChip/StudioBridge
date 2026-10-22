"""Unit and integration tests for Model Context Protocol (MCP) resources.

Verifies:
1. Static resource catalog: studio://status, studio://capabilities, studio://project/summary, studio://journal/latest.
2. Resource templates catalog: studio://api/{module} and studio://api/{module}/{function}.
3. Offline and live resource URI resolution.
4. JSON-RPC protocol dispatch via resources/list, resources/templates/list, and resources/read.
"""

from __future__ import annotations

import json

import pytest

from studiobridge.mcp.host import JsonRpcErrorCode, McpHost
from studiobridge.mcp.resources import (
    ResourceContent,
    ResourceDefinition,
    ResourceProvider,
    ResourceTemplate,
    get_default_resource_templates,
    get_default_resources,
    read_resource,
)
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.sdk.client import Studio


class TestResourceDefinitions:
    """Tests verifying resource definitions and serialization."""

    def test_default_resources_catalog(self) -> None:
        """Verify static catalog returns the 4 expected core resources."""
        resources = get_default_resources()
        uris = [r.uri for r in resources]
        assert "studio://status" in uris
        assert "studio://capabilities" in uris
        assert "studio://project/summary" in uris
        assert "studio://journal/latest" in uris
        assert len(resources) == 4

    def test_default_resource_templates_catalog(self) -> None:
        """Verify templates catalog returns API module and function templates."""
        templates = get_default_resource_templates()
        uri_templates = [t.uri_template for t in templates]
        assert "studio://api/{module}" in uri_templates
        assert "studio://api/{module}/{function}" in uri_templates
        assert len(templates) == 2

    def test_resource_definition_serialization(self) -> None:
        """Verify ResourceDefinition to_mcp_dict matches MCP specification."""
        res = ResourceDefinition(
            uri="studio://status",
            name="Live Bridge Status",
            description="Live status overview",
            mime_type="application/json",
        )
        d = res.to_mcp_dict()
        assert d["uri"] == "studio://status"
        assert d["name"] == "Live Bridge Status"
        assert d["description"] == "Live status overview"
        assert d["mimeType"] == "application/json"

    def test_resource_template_serialization(self) -> None:
        """Verify ResourceTemplate to_mcp_dict matches MCP specification."""
        tpl = ResourceTemplate(
            uri_template="studio://api/{module}",
            name="Module Functions",
            description="Catalog of functions",
            mime_type="application/json",
        )
        d = tpl.to_mcp_dict()
        assert d["uriTemplate"] == "studio://api/{module}"
        assert d["name"] == "Module Functions"
        assert d["description"] == "Catalog of functions"
        assert d["mimeType"] == "application/json"

    def test_resource_content_serialization(self) -> None:
        """Verify ResourceContent to_mcp_dict matches MCP specification."""
        content = ResourceContent(
            uri="studio://status",
            mime_type="application/json",
            text='{"connected": true}',
        )
        d = content.to_mcp_dict()
        assert d["uri"] == "studio://status"
        assert d["mimeType"] == "application/json"
        assert d["text"] == '{"connected": true}'


class TestResourceResolutionOffline:
    """Tests for resource URI resolution without an active FL Studio connection."""

    def test_read_status_offline(self) -> None:
        """Read studio://status when disconnected returns structured offline payload."""
        content = read_resource("studio://status")
        assert content.uri == "studio://status"
        assert content.mime_type == "application/json"
        assert content.text is not None

        data = json.loads(content.text)
        assert data["connected"] is False
        assert data["mode"] == "read_only"
        assert "broker" in data

    def test_read_capabilities_offline(self) -> None:
        """Read studio://capabilities returns aggregate capability status matrix."""
        content = read_resource("studio://capabilities")
        assert content.uri == "studio://capabilities"
        assert content.mime_type == "application/json"
        assert content.text is not None

        data = json.loads(content.text)
        assert "summary" in data
        assert "capabilities" in data
        assert data["summary"]["total"] > 0

    def test_read_project_summary_offline(self) -> None:
        """Read studio://project/summary offline returns disconnected status."""
        content = read_resource("studio://project/summary")
        assert content.uri == "studio://project/summary"
        assert content.mime_type == "application/json"
        assert content.text is not None

        data = json.loads(content.text)
        assert data["connected"] is False
        assert data["project"] is None

    def test_read_journal_latest_offline(self) -> None:
        """Read studio://journal/latest returns journal entries dictionary."""
        content = read_resource("studio://journal/latest")
        assert content.uri == "studio://journal/latest"
        assert content.mime_type == "application/json"
        assert content.text is not None

        data = json.loads(content.text)
        assert "session_id" in data
        assert "count" in data
        assert isinstance(data["entries"], list)

    def test_read_api_module_catalog(self) -> None:
        """Read studio://api/mixer returns JSON catalog of mixer functions."""
        content = read_resource("studio://api/mixer")
        assert content.uri == "studio://api/mixer"
        assert content.mime_type == "application/json"
        assert content.text is not None

        data = json.loads(content.text)
        assert data["module"] == "mixer"
        assert data["function_count"] > 0
        assert isinstance(data["functions"], list)

        # Check function fields
        fn_names = [f["name"] for f in data["functions"]]
        assert "getTrackVolume" in fn_names
        assert "setTrackVolume" in fn_names

        track_vol_entry = next(f for f in data["functions"] if f["name"] == "getTrackVolume")
        assert "signature" in track_vol_entry
        assert "def getTrackVolume" in track_vol_entry["signature"]
        assert track_vol_entry["uri"] == "studio://api/mixer/getTrackVolume"

    def test_read_api_function_card(self) -> None:
        """Read studio://api/mixer/getTrackVolume returns Markdown documentation card."""
        content = read_resource("studio://api/mixer/getTrackVolume")
        assert content.uri == "studio://api/mixer/getTrackVolume"
        assert content.mime_type == "text/markdown"
        assert content.text is not None

        card_md = content.text
        assert "# mixer.getTrackVolume" in card_md
        assert "studio://api/mixer/getTrackVolume" in card_md
        assert "```python" in card_md

    def test_read_unknown_uri_raises_value_error(self) -> None:
        """Unrecognized URI scheme raises ValueError."""
        with pytest.raises(ValueError, match="Resource URI not recognized"):
            read_resource("studio://invalid/resource/path")

    def test_read_unknown_api_module_raises_value_error(self) -> None:
        """Querying a non-existent API module raises ValueError."""
        with pytest.raises(ValueError, match="not found in API manifest"):
            read_resource("studio://api/nonexistent_mod")

    def test_read_unknown_api_function_raises_value_error(self) -> None:
        """Querying a non-existent API function raises ValueError."""
        with pytest.raises(ValueError, match="Function 'nonexistent_fn' not found"):
            read_resource("studio://api/mixer/nonexistent_fn")


class TestResourceResolutionLive:
    """Tests for resource URI resolution against live connected Studio client."""

    def test_live_read_status(self, studio: Studio) -> None:
        """Read studio://status with live client returns connected=True."""
        provider = ResourceProvider(client=studio)
        content = provider.read_resource("studio://status")
        data = json.loads(content.text or "{}")

        assert data["connected"] is True
        assert data["fl_version"] is not None
        assert data["mode"] in ("write", "write_autonomous")
        assert "transport" in data
        assert isinstance(data["transport"]["tempo"], float)

    def test_live_read_project_summary(self, studio: Studio) -> None:
        """Read studio://project/summary with live client returns populated project summary."""
        provider = ResourceProvider(client=studio)
        content = provider.read_resource("studio://project/summary")
        data = json.loads(content.text or "{}")

        assert data["connected"] is True
        assert "project" in data
        assert data["project"]["untrusted"] is True
        assert data["tempo"] > 0
        assert data["channel_count"] > 0
        assert len(data["channels"]) > 0
        assert data["channels"][0]["untrusted"] is True
        assert data["pattern_count"] > 0
        assert len(data["patterns"]) > 0
        assert data["patterns"][0]["untrusted"] is True
        assert data["mixer_track_count"] > 0

    def test_live_read_journal_latest(self, studio: Studio) -> None:
        """Mutations performed on live client are reflected in studio://journal/latest."""
        # Perform verified mutation
        studio.mixer.set_volume(1, 0.75)

        provider = ResourceProvider(client=studio)
        content = provider.read_resource("studio://journal/latest")
        data = json.loads(content.text or "{}")

        assert data["count"] > 0
        assert len(data["entries"]) > 0
        ops = [e.get("op") for e in data["entries"]]
        assert any("mixer" in str(op) for op in ops)


class TestMcpHostResourceIntegration:
    """Tests verifying JSON-RPC 2.0 protocol dispatch for resource methods."""

    def _init_host(self, host: McpHost) -> None:
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        host.handle_request(init_req)

    def test_jsonrpc_resources_list(self) -> None:
        """Verify 'resources/list' JSON-RPC returns all static resources."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "resources/list",
            "params": {},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 10
        assert "result" in resp

        res = resp["result"]
        assert "resources" in res
        uris = [r["uri"] for r in res["resources"]]
        assert "studio://status" in uris
        assert "studio://capabilities" in uris
        assert "studio://project/summary" in uris
        assert "studio://journal/latest" in uris

    def test_jsonrpc_resources_templates_list(self) -> None:
        """Verify 'resources/templates/list' JSON-RPC returns URI templates."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "resources/templates/list",
            "params": {},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert resp["id"] == 11
        assert "result" in resp

        res = resp["result"]
        assert "resourceTemplates" in res
        templates = [t["uriTemplate"] for t in res["resourceTemplates"]]
        assert "studio://api/{module}" in templates
        assert "studio://api/{module}/{function}" in templates

    def test_jsonrpc_resources_read_status(self) -> None:
        """Verify 'resources/read' JSON-RPC resolves studio://status."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "resources/read",
            "params": {"uri": "studio://status"},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert resp["id"] == 12
        assert "result" in resp

        res = resp["result"]
        assert "contents" in res
        assert len(res["contents"]) == 1
        item = res["contents"][0]
        assert item["uri"] == "studio://status"
        assert item["mimeType"] == "application/json"
        data = json.loads(item["text"])
        assert "connected" in data

    def test_jsonrpc_resources_read_api_card(self) -> None:
        """Verify 'resources/read' JSON-RPC resolves studio://api/transport/getSongPos."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "resources/read",
            "params": {"uri": "studio://api/transport/getSongPos"},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert resp["id"] == 13
        assert "result" in resp

        res = resp["result"]
        assert "contents" in res
        item = res["contents"][0]
        assert item["uri"] == "studio://api/transport/getSongPos"
        assert item["mimeType"] == "text/markdown"
        assert "# transport.getSongPos" in item["text"]

    def test_jsonrpc_resources_read_invalid_uri_returns_error_frame(self) -> None:
        """Invalid resource URI returns standard JSON-RPC error frame."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "resources/read",
            "params": {"uri": "studio://unknown/uri"},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert resp["id"] == 14
        assert "error" in resp
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_PARAMS
        assert "Resource URI not recognized" in resp["error"]["message"]

    def test_jsonrpc_resources_read_missing_uri_returns_invalid_params(self) -> None:
        """Missing 'uri' in params returns INVALID_PARAMS error frame."""
        server = StudioMcpServer(toolsets="core")
        self._init_host(server.host)

        req = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "resources/read",
            "params": {},
        }
        resp = server.host.handle_request(req)
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_PARAMS
