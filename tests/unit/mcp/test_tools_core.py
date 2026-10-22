"""Unit tests for StudioBridge core MCP tools per spec 10_l2_interfaces.md §2.4.

Verifies:
1. Registration and annotations: readOnlyHint=True, idempotentHint=True, openWorldHint=False.
2. Token budget: description words <= 60 words (<< 250 tokens), total tokens << 8,000 tokens.
3. Functional correctness of studio_status, studio_capabilities, studio_doctor,
   api_search, api_describe, and project_snapshot.
4. Conformance against frozen JSON schemas in studiobridge.mcp.schemas.
"""

from __future__ import annotations

import pytest

from studiobridge.mcp.schemas import get_schema, validate_schema
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.mcp.tools.core import CoreTools, get_core_tools
from studiobridge.sdk.client import Studio


class TestCoreToolsMetadataAndBudget:
    """Verifies annotations, token budgets, and schema conformity for all core tools."""

    def test_core_tools_catalog_and_annotations(self) -> None:
        """All 6 core tools are defined with correct read-only and idempotent hints."""
        tools = get_core_tools()
        assert len(tools) == 6

        names = {t.name for t in tools}
        expected = {
            "studio_status",
            "studio_capabilities",
            "studio_doctor",
            "api_search",
            "api_describe",
            "project_snapshot",
        }
        assert names == expected

        for t in tools:
            assert t.toolset == "core"
            assert t.read_only is True
            assert t.destructive is False
            assert t.idempotent is True
            assert t.open_world is False
            assert t.title is not None

            # Verify MCP serialization
            mcp_dict = t.to_mcp_dict()
            assert mcp_dict["name"] == t.name
            ann = mcp_dict["annotations"]
            assert ann["readOnlyHint"] is True
            assert ann["destructiveHint"] is False
            assert ann["idempotentHint"] is True
            assert ann["openWorldHint"] is False

    def test_description_token_budget(self) -> None:
        """Every tool description is <= 250 tokens and total descriptions sum <= 8,000 tokens."""
        tools = get_core_tools()
        total_tokens_approx = 0

        for t in tools:
            # Word count is a conservative lower bound on tokens; 1 word ≈ 1.33 tokens
            words = len(t.description.split())
            approx_tokens = int(words * 1.34) + 1
            assert approx_tokens <= 250, (
                f"Tool '{t.name}' description too verbose: {approx_tokens} tokens"
            )
            total_tokens_approx += approx_tokens

        assert total_tokens_approx <= 8000, (
            f"Total description tokens exceed 8,000: {total_tokens_approx}"
        )
        # In practice, our concise descriptions should total < 500 tokens
        assert total_tokens_approx < 500

    def test_input_schemas_match_stored_definitions(self) -> None:
        """Input schemas for core tools match frozen JSON schemas."""
        tools = get_core_tools()
        for t in tools:
            schema = get_schema(t.name)
            assert t.input_schema == schema.get("inputSchema")


class TestStudioStatusTool:
    """Tests for studio_status tool."""

    def test_status_disconnected_fallback(self) -> None:
        """When not connected to FL Studio, reports disconnected status and broker health."""
        core = CoreTools(client=None)
        res = core.studio_status()

        assert res.is_error is False
        assert len(res.content) == 1
        data = res.structured_content
        assert data["connected"] is False
        assert data["mode"] == "read_only"
        assert "broker" in data
        assert isinstance(data["broker"]["status"], str)

        schema = get_schema("studio_status")
        validate_schema(data, schema["outputSchema"])

    def test_status_connected(self, studio: Studio) -> None:
        """When connected to FL Studio emulator, reports active connection and transport state."""
        core = CoreTools(client=studio)
        res = core.studio_status()

        assert res.is_error is False
        data = res.structured_content
        assert data["connected"] is True
        assert data["fl_version"] == "24.1.0"
        assert data["api"] == 44
        assert "transport" in data
        assert isinstance(data["transport"]["tempo"], float)
        assert isinstance(data["transport"]["is_playing"], bool)

        schema = get_schema("studio_status")
        validate_schema(data, schema["outputSchema"])


class TestStudioCapabilitiesTool:
    """Tests for studio_capabilities tool."""

    def test_capabilities_full_matrix(self) -> None:
        """Querying without filters returns total counts and registered capabilities."""
        core = CoreTools()
        res = core.studio_capabilities()

        assert res.is_error is False
        data = res.structured_content
        assert "summary" in data
        assert data["summary"]["total"] > 10
        assert "capabilities" in data
        assert "offline.flp.read" in data["capabilities"]

        schema = get_schema("studio_capabilities")
        validate_schema(data, schema["outputSchema"])

    def test_capabilities_filter_by_state(self) -> None:
        """Filtering by state returns only matching capabilities."""
        core = CoreTools()
        res = core.studio_capabilities(state="available")

        data = res.structured_content
        for cap_data in data["capabilities"].values():
            assert cap_data["state"] == "available"

    def test_capabilities_single_id(self) -> None:
        """Querying a specific capability ID returns its prerequisites and alternatives."""
        core = CoreTools()
        res = core.studio_capabilities(capability="offline.flp.read")

        data = res.structured_content
        assert "capability" in data
        cap = data["capability"]
        assert cap["id"] == "offline.flp.read"
        assert cap["state"] == "available"

        schema = get_schema("studio_capabilities")
        validate_schema(data, schema["outputSchema"])


class TestStudioDoctorTool:
    """Tests for studio_doctor tool."""

    def test_doctor_runs_health_checks(self) -> None:
        """Running doctor diagnostic checks returns checks list, status, and summary."""
        core = CoreTools()
        res = core.studio_doctor(skip_live=True)

        data = res.structured_content
        assert "status" in data
        assert "has_errors" in data
        assert "checks" in data
        assert len(data["checks"]) > 0
        assert "summary" in data

        schema = get_schema("studio_doctor")
        validate_schema(data, schema["outputSchema"])


class TestApiSearchTool:
    """Tests for api_search progressive disclosure tool."""

    def test_search_by_keyword(self) -> None:
        """Searching by keyword 'volume' finds mixer and channel volume functions."""
        core = CoreTools()
        res = core.api_search(query="volume")

        assert res.is_error is False
        data = res.structured_content
        assert data["total"] >= 4
        names = {m["name"] for m in data["matches"]}
        assert "setTrackVolume" in names
        assert "getTrackVolume" in names
        assert "setChannelVolume" in names

        schema = get_schema("api_search")
        validate_schema(data, schema["outputSchema"])

    def test_search_by_module(self) -> None:
        """Filtering search by module 'transport' returns transport API methods."""
        core = CoreTools()
        res = core.api_search(module="transport", limit=10)

        data = res.structured_content
        assert data["total"] > 0
        for m in data["matches"]:
            assert m["module"] == "transport"

    def test_search_with_constants(self) -> None:
        """Searching with include_constants=True surfaces constants."""
        core = CoreTools()
        res = core.api_search(query="midi", include_constants=True)

        data = res.structured_content
        assert data["total"] > 0


class TestApiDescribeTool:
    """Tests for api_describe function documentation tool."""

    def test_describe_function_with_quirks(self) -> None:
        """Describing mixer.setTrackVolume returns signature, since, tolerances, and example."""
        core = CoreTools()
        res = core.api_describe(function="mixer.setTrackVolume")

        assert res.is_error is False
        data = res.structured_content
        assert data["module"] == "mixer"
        assert data["function"] == "setTrackVolume"
        assert "setTrackVolume" in data["signature"]
        assert data["since"] >= 1
        assert data["mutating"] is True
        assert len(data["args"]) >= 2

        # Check empirical quirks
        quirks = data["quirks"]
        assert quirks is not None
        assert quirks["tol"] == 0.01
        assert "spike:S2" in quirks["evidence"]

        # Check example
        assert "fl.mixer" in data["example"]

        schema = get_schema("api_describe")
        validate_schema(data, schema["outputSchema"])

    def test_describe_unprefixed_function(self) -> None:
        """Unprefixed function name resolves correctly if unique."""
        core = CoreTools()
        res = core.api_describe(function="getTrackVolume")

        data = res.structured_content
        assert data["module"] == "mixer"
        assert data["function"] == "getTrackVolume"
        assert data["mutating"] is False

    def test_describe_missing_function_raises(self) -> None:
        """Querying a non-existent function raises ValueError."""
        core = CoreTools()
        with pytest.raises(ValueError, match="not found"):
            core.api_describe(function="nonExistentFunction12345")


class TestProjectSnapshotTool:
    """Tests for project_snapshot compact project overview."""

    def test_snapshot_connected(self, studio: Studio) -> None:
        """Taking snapshot of running project returns tempo, channels, patterns, and mixer."""
        core = CoreTools(client=studio)
        res = core.project_snapshot()

        assert res.is_error is False
        data = res.structured_content
        assert isinstance(data["tempo"], float)
        assert isinstance(data["is_playing"], bool)
        assert data["channel_count"] >= 0
        assert data["pattern_count"] >= 1
        assert isinstance(data["mixer_tracks"], list)
        assert any(t["index"] == 0 for t in data["mixer_tracks"])  # Master track included

        schema = get_schema("project_snapshot")
        validate_schema(data, schema["outputSchema"])


class TestServerCoreToolsIntegration:
    """Tests StudioMcpServer dispatch for core tools."""

    def test_server_call_tool_studio_status(self) -> None:
        """StudioMcpServer executes studio_status tool call."""
        server = StudioMcpServer(toolsets="core")
        res = server.call_tool("studio_status", {})

        assert res["isError"] is False
        assert "structuredContent" in res
        assert res["structuredContent"]["connected"] is False

    def test_server_call_tool_api_search(self) -> None:
        """StudioMcpServer executes api_search tool call."""
        server = StudioMcpServer(toolsets="core")
        res = server.call_tool("api_search", {"query": "volume"})

        assert res["isError"] is False
        assert len(res["structuredContent"]["matches"]) > 0
