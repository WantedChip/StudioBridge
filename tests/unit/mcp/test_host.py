"""Protocol handshake, version negotiation, error frame, and toolset filtering unit tests.

Verifies:
1. Version negotiation targeting 2026-07-28 with fallback down to 2025-03-26 per [MCP-01].
2. Compliant JSON-RPC 2.0 error frames for incompatible, invalid, or malformed requests.
3. Framework-agnostic McpHost adapter running pure-Python stdio transport per [MCP-03].
4. Statelessness guaranteeing no volatile session state leaks across server instances [MCP-04].
5. Toolset filtering with default toolsets and CLI command flags per [MCP-11].
"""

from __future__ import annotations

import io
import json

import pytest

from studiobridge.cli import main as cli_main
from studiobridge.cli.main import ExitCode
from studiobridge.mcp.host import (
    LATEST_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    JsonRpcErrorCode,
    McpHost,
    negotiate_protocol_version,
)
from studiobridge.mcp.server import (
    StudioMcpServer,
    ToolDefinition,
    parse_toolsets,
)


class TestProtocolVersionNegotiation:
    """Tests for protocol version negotiation per [MCP-01]."""

    @pytest.mark.parametrize("version", SUPPORTED_PROTOCOL_VERSIONS)
    def test_handshake_all_supported_versions(self, version: str) -> None:
        """Verify handshake completes across all four supported protocol versions."""
        host = McpHost()
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        resp = host.handle_request(req)
        assert resp is not None
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp

        res = resp["result"]
        assert res["protocolVersion"] == version
        assert host.negotiated_version == version
        assert host.is_initialized is True

        # Check capabilities: tasks extension present only for 2026-07-28
        caps = res["capabilities"]
        assert "tools" in caps
        assert "resources" in caps
        assert "prompts" in caps
        if version == "2026-07-28":
            assert "tasks" in caps
        else:
            assert "tasks" not in caps

        # Instructions should be <= 120 words and describe modes/safety
        instr = res["instructions"]
        assert len(instr.split()) <= 120
        assert "studio_status" in instr

    def test_negotiate_newer_version_falls_back_to_latest(self) -> None:
        """Client requesting newer than latest receives latest supported version."""
        assert negotiate_protocol_version("2026-10-01") == LATEST_PROTOCOL_VERSION
        assert negotiate_protocol_version("2030-01-01") == LATEST_PROTOCOL_VERSION

        host = McpHost()
        req = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "initialize",
            "params": {"protocolVersion": "2026-10-01"},
        }
        resp = host.handle_request(req)
        assert resp is not None
        assert resp["result"]["protocolVersion"] == LATEST_PROTOCOL_VERSION

    def test_negotiate_intermediate_versions(self) -> None:
        """Client requesting intermediate dates falls back to highest supported <= date."""
        assert negotiate_protocol_version("2025-12-15") == "2025-11-25"
        assert negotiate_protocol_version("2025-08-01") == "2025-06-18"
        assert negotiate_protocol_version("2025-04-10") == "2025-03-26"

    def test_unsupported_old_version_returns_error_frame(self) -> None:
        """Client requesting version older than earliest supported returns compliant error frame."""
        host = McpHost()
        req = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = host.handle_request(req)
        assert resp is not None
        assert resp["id"] == 99
        assert "error" in resp
        err = resp["error"]
        assert err["code"] == JsonRpcErrorCode.INVALID_PARAMS
        assert "Unsupported protocol version: 2024-11-05" in err["message"]
        assert host.is_initialized is False

    def test_missing_or_invalid_protocol_version_returns_error_frame(self) -> None:
        """Missing or non-string protocolVersion returns compliant error frame."""
        host = McpHost()
        req = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "initialize",
            "params": {},
        }
        resp = host.handle_request(req)
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_PARAMS


class TestJsonRpcErrorFrames:
    """Tests verifying compliant JSON-RPC 2.0 error responses."""

    def test_malformed_json_returns_parse_error(self) -> None:
        """Non-JSON string returns code -32700 Parse Error."""
        host = McpHost()
        raw = "not a json string"
        resp_str = host.handle_message(raw)
        assert resp_str is not None
        resp = json.loads(resp_str)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] is None
        assert resp["error"]["code"] == JsonRpcErrorCode.PARSE_ERROR

    def test_non_dict_json_returns_invalid_request(self) -> None:
        """JSON array or scalar payload returns -32600 Invalid Request."""
        host = McpHost()
        resp_str = host.handle_message("[1, 2, 3]")
        assert resp_str is not None
        resp = json.loads(resp_str)
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST

    def test_missing_jsonrpc_2_returns_invalid_request(self) -> None:
        """Request without jsonrpc: '2.0' returns -32600 Invalid Request."""
        host = McpHost()
        resp = host.handle_request({"id": 1, "method": "ping"})
        assert resp is not None
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST

    def test_missing_or_nonstring_method_returns_invalid_request(self) -> None:
        """Request without a valid method returns -32600 Invalid Request."""
        host = McpHost()
        resp = host.handle_request({"jsonrpc": "2.0", "id": 1, "method": 1234})
        assert resp is not None
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST

    def test_unknown_method_returns_method_not_found(self) -> None:
        """Initialized host receiving unknown method returns -32601 Method Not Found."""
        host = McpHost()
        # Initialize first
        host.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2026-07-28"},
            }
        )
        resp = host.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "completely/unknown/method",
            }
        )
        assert resp is not None
        assert resp["error"]["code"] == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_request_before_initialize_returns_error(self) -> None:
        """Calling tools/list or other endpoints before initialize returns -32600 error."""
        host = McpHost()
        resp = host.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
            }
        )
        assert resp is not None
        assert resp["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST
        assert "Server not initialized" in resp["error"]["message"]

    def test_notifications_never_produce_response(self) -> None:
        """A JSON-RPC notification (no 'id' field) must never elicit a response."""
        host = McpHost()
        # Initialized notification
        resp = host.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )
        assert resp is None

        # Even on unknown notification, no response
        resp = host.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "unknown/notification",
            }
        )
        assert resp is None


class TestToolsetFiltering:
    """Tests for toolset registry and active tool filtering per [MCP-11]."""

    @pytest.fixture
    def server_with_tools(self) -> StudioMcpServer:
        """Fixture providing server populated with mock tools across various toolsets."""
        server = StudioMcpServer()
        tools = [
            ToolDefinition(
                name="studio_status",
                description="Status tool",
                input_schema={"type": "object"},
                toolset="core",
                read_only=True,
                handler=lambda **kw: {"status": "ok"},
            ),
            ToolDefinition(
                name="mixer_list",
                description="List mixer tracks",
                input_schema={"type": "object"},
                toolset="inspect",
                read_only=True,
                handler=lambda **kw: {"tracks": [0, 1, 2]},
            ),
            ToolDefinition(
                name="mixer_set",
                description="Set mixer volume",
                input_schema={"type": "object", "properties": {"track": {"type": "integer"}}},
                toolset="control",
                read_only=False,
                destructive=True,
                handler=lambda track=0, **kw: {"updated": track},
            ),
            ToolDefinition(
                name="flp_inspect",
                description="Inspect FLP binary",
                input_schema={"type": "object"},
                toolset="flp",
                read_only=True,
                handler=lambda **kw: {"flp": "ok"},
            ),
            ToolDefinition(
                name="fl_call",
                description="Raw API call",
                input_schema={"type": "object"},
                toolset="unsafe",
                read_only=False,
                handler=lambda **kw: {"raw": "executed"},
            ),
        ]
        for t in tools:
            server.register_tool(t)
        return server

    def test_default_toolsets(self, server_with_tools: StudioMcpServer) -> None:
        """Default toolset selection includes core, inspect, control; excludes flp, unsafe."""
        active_names = [t.name for t in server_with_tools.get_active_tools()]
        assert "studio_status" in active_names  # core
        assert "mixer_list" in active_names  # inspect
        assert "mixer_set" in active_names  # control
        assert "flp_inspect" not in active_names  # flp (offline)
        assert "fl_call" not in active_names  # unsafe

    def test_custom_toolsets_filter(self) -> None:
        """Explicit toolset selection properly filters tools."""
        server = StudioMcpServer(toolsets="core,flp")
        server.register_tool(
            ToolDefinition(
                name="t_core", description="", input_schema={}, toolset="core", handler=lambda: {}
            )
        )
        server.register_tool(
            ToolDefinition(
                name="t_inspect",
                description="",
                input_schema={},
                toolset="inspect",
                handler=lambda: {},
            )
        )
        server.register_tool(
            ToolDefinition(
                name="t_flp", description="", input_schema={}, toolset="flp", handler=lambda: {}
            )
        )

        active = [t.name for t in server.get_active_tools()]
        assert "t_core" in active
        assert "t_flp" in active
        assert "t_inspect" not in active

    def test_meta_mode_raw_unsafe_aliasing(self) -> None:
        """Specifying 'raw' enables 'unsafe' tools (meta mode --toolsets core,raw)."""
        server = StudioMcpServer(toolsets="core,raw")
        assert "unsafe" in server.active_toolsets
        assert "raw" in server.active_toolsets

        server.register_tool(
            ToolDefinition(
                name="fl_call",
                description="",
                input_schema={},
                toolset="unsafe",
                handler=lambda: {"raw": True},
            )
        )
        assert server.get_tool("fl_call") is not None

    def test_calling_disabled_toolset_returns_error(
        self, server_with_tools: StudioMcpServer
    ) -> None:
        """Calling a registered tool that belongs to a disabled toolset returns an error."""
        res = server_with_tools.call_tool("flp_inspect", {})
        assert res["isError"] is True
        assert "belongs to disabled toolset 'flp'" in res["content"][0]["text"]

    def test_calling_active_tool_succeeds(self, server_with_tools: StudioMcpServer) -> None:
        """Calling an active tool dispatches handler and returns structured output."""
        res = server_with_tools.call_tool("mixer_set", {"track": 5})
        assert res["isError"] is False
        assert res["structuredContent"] == {"updated": 5}

    def test_invalid_toolset_name_raises_value_error(self) -> None:
        """Providing an unrecognized toolset name raises ValueError with valid options."""
        with pytest.raises(ValueError, match="Invalid toolset"):
            StudioMcpServer(toolsets="core,non_existent_toolset")

    def test_tool_annotations_in_mcp_dict(self) -> None:
        """Tool definitions emit annotations per spec 10_l2_interfaces.md §2.2."""
        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            toolset="core",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            title="Test Tool Title",
        )
        d = tool.to_mcp_dict()
        assert d["name"] == "test_tool"
        assert d["title"] == "Test Tool Title"
        ann = d["annotations"]
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False
        assert ann["idempotentHint"] is True
        assert ann["openWorldHint"] is False

    def test_env_toolsets_respected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SBRIDGE_TOOLSETS environment variable is parsed when toolsets is None."""
        monkeypatch.setenv("SBRIDGE_TOOLSETS", "core,inspect")
        parsed = parse_toolsets(None)
        assert "core" in parsed
        assert "inspect" in parsed
        assert "control" not in parsed


class TestStatelessness:
    """Tests verifying server holds zero per-connection volatile state per [MCP-04]."""

    def test_server_instances_are_isolated(self) -> None:
        """Multiple StudioMcpServer instances hold zero shared volatile state."""
        server1 = StudioMcpServer(toolsets="core")
        server2 = StudioMcpServer(toolsets="inspect")

        assert server1.active_toolsets != server2.active_toolsets
        assert server1.host.negotiated_version is None
        assert server2.host.negotiated_version is None

        # Initialize server1
        server1.host.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2026-07-28"},
            }
        )
        assert server1.host.is_initialized is True
        assert server1.host.negotiated_version == "2026-07-28"

        # server2 must remain unaffected
        assert server2.host.is_initialized is False
        assert server2.host.negotiated_version is None

    def test_connection_reset_clears_transient_handshake(self) -> None:
        """Host reset_connection clears transport state without leaking across sessions."""
        host = McpHost()
        host.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            }
        )
        assert host.is_initialized is True
        assert host.negotiated_version == "2025-11-25"

        host.reset_connection()
        assert host.is_initialized is False
        assert host.negotiated_version is None
        assert host.is_ready is False


class TestStdioTransportSession:
    """Full simulated interactive stdio session tests."""

    def test_complete_stdio_lifecycle(self) -> None:
        """Simulate complete line-delimited stdio exchange: initialize, tools/list, ping."""
        server = StudioMcpServer(toolsets="core")
        server.register_tool(
            ToolDefinition(
                name="studio_status",
                description="Report status",
                input_schema={"type": "object"},
                toolset="core",
                handler=lambda: {"status": "ok"},
            )
        )

        input_lines = [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2026-07-28"},
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "ping",
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/list",
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "studio_status", "arguments": {}},
                }
            ),
        ]

        in_stream = io.StringIO("\n".join(input_lines) + "\n")
        out_stream = io.StringIO()

        server.run_stdio(reader=in_stream, writer=out_stream)

        output_lines = [
            json.loads(line) for line in out_stream.getvalue().splitlines() if line.strip()
        ]
        assert len(output_lines) == 4  # notification produced no response

        # 1. initialize response
        assert output_lines[0]["id"] == 1
        assert output_lines[0]["result"]["protocolVersion"] == "2026-07-28"

        # 2. ping response
        assert output_lines[1]["id"] == 2
        assert output_lines[1]["result"] == {}

        # 3. tools/list response
        assert output_lines[2]["id"] == 3
        tools = output_lines[2]["result"]["tools"]
        assert len(tools) >= 1
        assert any(t["name"] == "studio_status" for t in tools)

        # 4. tools/call response
        assert output_lines[3]["id"] == 4
        call_res = output_lines[3]["result"]
        assert call_res["isError"] is False
        assert call_res["structuredContent"] == {"status": "ok"}


class TestToolExecutionAndAdapters:
    """Tests for sync/async tool execution, error translation, and adapter selection."""

    def test_async_tool_handler_execution(self) -> None:
        """Async coroutine handlers execute cleanly via anyio runner."""
        server = StudioMcpServer()

        async def async_handler(target: str = "world") -> dict[str, str]:
            return {"greeting": f"hello {target}"}

        server.register_tool(
            ToolDefinition(
                name="async_hello",
                description="Async test",
                input_schema={},
                toolset="core",
                handler=async_handler,
            )
        )
        res = server.call_tool("async_hello", {"target": "fl studio"})
        assert res["isError"] is False
        assert res["structuredContent"] == {"greeting": "hello fl studio"}

    def test_tool_handler_studiobridge_error_reporting(self) -> None:
        """Errors that teach: StudioBridgeError returns isError: true with code, message, remedy."""
        from studiobridge.core.errors import ReadOnlyError

        server = StudioMcpServer()

        def mutating_handler() -> None:
            raise ReadOnlyError(
                "Cannot mutate in read_only mode",
                remedy="Switch safety mode to 'write' via studio_set_mode",
            )

        server.register_tool(
            ToolDefinition(
                name="mutator",
                description="",
                input_schema={},
                toolset="core",
                handler=mutating_handler,
            )
        )
        res = server.call_tool("mutator", {})
        assert res["isError"] is True
        sc = res["structuredContent"]
        assert sc["code"] == "E_READONLY"
        assert "Cannot mutate in read_only mode" in sc["message"]
        assert "studio_set_mode" in sc["remedy"]

    def test_tool_handler_generic_exception(self) -> None:
        """Generic unexpected exceptions return E_INTERNAL and isError: true."""
        server = StudioMcpServer()

        def broken_handler() -> None:
            raise RuntimeError("Unexpected failure")

        server.register_tool(
            ToolDefinition(
                name="broken",
                description="",
                input_schema={},
                toolset="core",
                handler=broken_handler,
            )
        )
        res = server.call_tool("broken", {})
        assert res["isError"] is True
        assert res["structuredContent"]["code"] == "E_INTERNAL"

    def test_adapter_mode_fallback_default(self) -> None:
        """Default adapter mode is fallback when official SDK is not installed."""
        host = McpHost(adapter="auto")
        assert host.adapter_mode == "fallback"

        host_explicit = McpHost(adapter="fallback")
        assert host_explicit.adapter_mode == "fallback"

    def test_adapter_mode_sdk_missing_raises_import_error(self) -> None:
        """Requesting official SDK when missing raises clear ImportError."""
        with pytest.raises(ImportError, match="Official Python MCP SDK"):
            McpHost(adapter="sdk")


class TestCliMcpCommand:
    """CLI tests for 'sbridge mcp' subcommand."""

    def test_cli_mcp_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge mcp --dry-run validates configuration and exits 0."""
        code = cli_main(["mcp", "--dry-run"])
        assert code == ExitCode.OK

    def test_cli_mcp_dry_run_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge mcp --dry-run --json emits structured active toolsets."""
        code = cli_main(["mcp", "--dry-run", "--json"])
        assert code == ExitCode.OK
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["status"] == "ok"
        assert "core" in data["active_toolsets"]

    def test_cli_mcp_invalid_toolsets(self, capsys: pytest.CaptureFixture[str]) -> None:
        """sbridge mcp with invalid toolset exits with USAGE error code."""
        code = cli_main(["mcp", "--toolsets", "bogus_toolset", "--dry-run"])
        assert code == ExitCode.USAGE
