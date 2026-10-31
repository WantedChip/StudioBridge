"""Integration and unit tests for local HTTP REST server and Streamable HTTP MCP transport.

Verifies:
1. Loopback binding strictly to 127.0.0.1 and rejection of non-loopback hosts (# req: SEC-02).
2. Bearer token authentication matching broker.token on all endpoints (# req: SEC-02).
3. Origin and Referer validation rejecting untrusted web origins with 403 Forbidden (# req: SEC-02).
4. DNS rebinding protection via Host header validation (# req: SEC-02).
5. Body size limits enforcing payload caps (1 MiB default).
6. REST endpoints: GET /v1/status, GET /v1/capabilities, GET /v1/mixer,
   POST /v1/mixer/{track}/volume, POST /v1/transport/{cmd}.
7. Machine-readable OpenAPI 3.1 specification generation (/openapi.json).
8. Streamable HTTP MCP JSON-RPC transport (/mcp) for initialize, tools/list, and tools/call.
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from studiobridge.cli.main import build_parser, cli_entry
from studiobridge.core.capabilities import CapabilityRegistry
from studiobridge.http.server import (
    HttpServer,
    is_trusted_host,
    is_trusted_origin,
    is_trusted_referer,
)
from studiobridge.sdk.refs import MixerTrack
from studiobridge.sdk.session import Status

TEST_TOKEN = "test_bearer_token_secret_1234567890_abcdef"


class MockMixer:
    """Mock mixer namespace for HTTP endpoint testing."""

    def __init__(self) -> None:
        self.tracks: list[MixerTrack] = [
            MixerTrack(index=0, name="Master", volume=0.8, pan=0.0),
            MixerTrack(index=1, name="Kick", volume=0.75, pan=0.0),
            MixerTrack(index=2, name="Lead", volume=0.6, pan=-0.2),
        ]
        self.last_volume_set: tuple[int, float] | None = None

    def get_tracks(self, count: int | None = None) -> list[MixerTrack]:
        if count is not None:
            return self.tracks[:count]
        return self.tracks

    def get_track(self, index: int) -> MixerTrack:
        for t in self.tracks:
            if t.index == index:
                return t
        raise KeyError(f"Track {index} not found")

    def set_volume(self, index: int, volume: float) -> None:
        self.last_volume_set = (index, volume)
        for t in self.tracks:
            if t.index == index:
                t.volume = volume


class MockTransport:
    """Mock transport namespace for HTTP endpoint testing."""

    def __init__(self) -> None:
        self.playing: bool = False
        self.recording: bool = False
        self.tempo: float = 128.0
        self.pos: float = 0.0

    def play(self) -> None:
        self.playing = True

    def stop(self) -> None:
        self.playing = False

    def record(self) -> None:
        self.recording = not self.recording

    def set_tempo(self, tempo: float) -> None:
        self.tempo = tempo

    def set_time(self, pos: float) -> None:
        self.pos = pos


class MockStudioClient:
    """Mock high-level Studio client for REST routing tests."""

    def __init__(self) -> None:
        self.is_connected: bool = True
        self.caps: CapabilityRegistry = CapabilityRegistry()
        self.mixer: MockMixer = MockMixer()
        self.transport: MockTransport = MockTransport()

    def status(self) -> Status:
        return Status(
            fl_version="24.1.0",
            api=2,
            project="TestProject.flp",
            mode="write",
            caps_summary={"transport": "available", "mixer": "available"},
            rtt=0.0008,
            connected=True,
        )


def _http_request(
    port: int,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: Any = None,
) -> tuple[int, dict[str, str], bytes]:
    """Execute raw HTTP request to loopback server."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    req_headers = dict(headers) if headers else {}
    body_bytes: bytes | None = None

    if body is not None:
        if isinstance(body, (dict, list)):
            body_bytes = json.dumps(body).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif isinstance(body, bytes):
            body_bytes = body

    conn.request(method, path, body=body_bytes, headers=req_headers)
    resp = conn.getresponse()
    status_code = resp.status
    resp_headers = dict(resp.getheaders())
    resp_body = resp.read()
    conn.close()
    return status_code, resp_headers, resp_body


@pytest.fixture
def mock_client() -> MockStudioClient:
    return MockStudioClient()


@pytest.fixture
def http_server(tmp_path: Path, mock_client: MockStudioClient) -> Generator[HttpServer, None, None]:
    tok_path = tmp_path / "broker.token"
    tok_path.write_text(TEST_TOKEN, encoding="utf-8")
    server = HttpServer(
        host="127.0.0.1",
        port=0,  # dynamic ephemeral port
        token=TEST_TOKEN,
        token_path=tok_path,
        client=mock_client,
    )
    server.start(background=True)
    yield server
    server.stop()


class TestSecurityAndOriginValidation:
    """Tests for loopback binding, origin validation, and authentication (# req: SEC-02)."""

    def test_loopback_binding_enforced(self, tmp_path: Path) -> None:
        """Verify server refuses to bind to non-loopback addresses (# req: SEC-02)."""
        tok_path = tmp_path / "broker.token"
        tok_path.write_text(TEST_TOKEN, encoding="utf-8")

        with pytest.raises(ValueError, match="strictly to loopback"):
            HttpServer(host="0.0.0.0", port=0, token=TEST_TOKEN, token_path=tok_path)

        with pytest.raises(ValueError, match="strictly to loopback"):
            HttpServer(host="192.168.1.100", port=0, token=TEST_TOKEN, token_path=tok_path)

    def test_bearer_auth_missing_token_rejected(self, http_server: HttpServer) -> None:
        """Verify requests without Bearer token return 401 Unauthorized (# req: SEC-02)."""
        status, _, body = _http_request(http_server.bound_port, "GET", "/v1/status")
        assert status == 401
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_UNAUTHORIZED"

    def test_bearer_auth_invalid_token_rejected(self, http_server: HttpServer) -> None:
        """Verify requests with invalid Bearer token return 401 Unauthorized (# req: SEC-02)."""
        headers = {"Authorization": "Bearer wrong_token_value"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 401
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_UNAUTHORIZED"

    def test_bearer_auth_valid_token_accepted(self, http_server: HttpServer) -> None:
        """Verify requests with correct Bearer token succeed (# req: SEC-02)."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "ok"
        assert data["data"]["connected"] is True

    def test_untrusted_origin_rejected(self, http_server: HttpServer) -> None:
        """Verify cross-site requests with untrusted Origin header return 403 (# req: SEC-02)."""
        headers = {
            "Authorization": f"Bearer {TEST_TOKEN}",
            "Origin": "https://evil.com",
        }
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 403
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_FORBIDDEN"

    def test_trusted_loopback_origin_accepted(self, http_server: HttpServer) -> None:
        """Verify requests with loopback Origin headers succeed (# req: SEC-02)."""
        for origin in ("http://127.0.0.1:3000", "http://localhost:5173", "http://[::1]:8080"):
            headers = {
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Origin": origin,
            }
            status, _, body = _http_request(
                http_server.bound_port, "GET", "/v1/status", headers=headers
            )
            assert status == 200, f"Expected 200 for origin {origin}"

    def test_browser_extension_origin_accepted(self, http_server: HttpServer) -> None:
        """Verify requests from browser extensions (chrome-extension, moz-extension) succeed."""
        for origin in (
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "moz-extension://12345678-1234-1234-1234-123456789abc",
        ):
            headers = {
                "Authorization": f"Bearer {TEST_TOKEN}",
                "Origin": origin,
            }
            status, _, body = _http_request(
                http_server.bound_port, "GET", "/v1/status", headers=headers
            )
            assert status == 200, f"Expected 200 for extension origin {origin}"

    def test_untrusted_referer_rejected(self, http_server: HttpServer) -> None:
        """Verify requests with untrusted Referer header return 403 Forbidden (# req: SEC-02)."""
        headers = {
            "Authorization": f"Bearer {TEST_TOKEN}",
            "Referer": "https://evil.attacker.org/phishing.html",
        }
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 403
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_FORBIDDEN"

    def test_untrusted_host_header_rejected(self, http_server: HttpServer) -> None:
        """Verify DNS rebinding attacks via untrusted Host header return 403 (# req: SEC-02)."""
        headers = {
            "Authorization": f"Bearer {TEST_TOKEN}",
            "Host": "attacker.com",
        }
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 403
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_FORBIDDEN"

    def test_payload_size_limit_enforced(self, http_server: HttpServer) -> None:
        """Verify requests exceeding max_body_size return 413 Payload Too Large."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        oversized_payload = b"x" * (http_server.max_body_size + 1024)
        status, _, body = _http_request(
            http_server.bound_port,
            "POST",
            "/v1/mixer/0/volume",
            headers=headers,
            body=oversized_payload,
        )
        assert status == 413
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_PAYLOAD_TOO_LARGE"


class TestRestEndpoints:
    """Tests for REST endpoints mapping SDK operations."""

    def test_get_status(self, http_server: HttpServer) -> None:
        """Verify GET /v1/status returns session status snapshot."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/status", headers=headers
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "ok"
        snapshot = data["data"]
        assert snapshot["fl_version"] == "24.1.0"
        assert snapshot["project"] == "TestProject.flp"
        assert snapshot["mode"] == "write"

    def test_get_capabilities(self, http_server: HttpServer) -> None:
        """Verify GET /v1/capabilities returns capability registry status."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/capabilities", headers=headers
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "ok"
        assert "capabilities" in data["data"]

    def test_get_mixer_tracks(self, http_server: HttpServer) -> None:
        """Verify GET /v1/mixer returns list of mixer tracks."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(http_server.bound_port, "GET", "/v1/mixer", headers=headers)
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        tracks = data["data"]["tracks"]
        assert len(tracks) == 3
        assert tracks[0]["name"] == "Master"
        assert tracks[1]["name"] == "Kick"

    def test_get_mixer_tracks_with_count_query(self, http_server: HttpServer) -> None:
        """Verify GET /v1/mixer?count=1 respects count query parameter."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/mixer?count=1", headers=headers
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        tracks = data["data"]["tracks"]
        assert len(tracks) == 1
        assert tracks[0]["index"] == 0

    def test_get_single_mixer_track(self, http_server: HttpServer) -> None:
        """Verify GET /v1/mixer/{track} returns individual track."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/v1/mixer/1", headers=headers
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        track = data["data"]
        assert track["index"] == 1
        assert track["name"] == "Kick"
        assert track["volume"] == 0.75

    def test_set_mixer_volume(self, http_server: HttpServer, mock_client: MockStudioClient) -> None:
        """Verify POST /v1/mixer/{track}/volume modifies fader volume."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        payload = {"volume": 0.85}
        status, _, body = _http_request(
            http_server.bound_port,
            "POST",
            "/v1/mixer/1/volume",
            headers=headers,
            body=payload,
        )
        assert status == 200
        data = json.loads(body.decode("utf-8"))
        assert data["status"] == "ok"
        assert data["data"]["track"] == 1
        assert data["data"]["volume"] == 0.85
        assert mock_client.mixer.last_volume_set == (1, 0.85)

    def test_set_mixer_volume_invalid_value(self, http_server: HttpServer) -> None:
        """Verify POST /v1/mixer/{track}/volume rejects out-of-range volume."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port,
            "POST",
            "/v1/mixer/0/volume",
            headers=headers,
            body={"volume": 1.5},
        )
        assert status == 400
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_INVALID_PARAMS"

    def test_transport_commands(
        self, http_server: HttpServer, mock_client: MockStudioClient
    ) -> None:
        """Verify POST /v1/transport/{cmd} routes play, stop, record, tempo, pos."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

        # 1. play
        s, _, _ = _http_request(
            http_server.bound_port, "POST", "/v1/transport/play", headers=headers
        )
        assert s == 200
        assert mock_client.transport.playing is True

        # 2. stop
        s, _, _ = _http_request(
            http_server.bound_port, "POST", "/v1/transport/stop", headers=headers
        )
        assert s == 200
        assert mock_client.transport.playing is False

        # 3. record
        s, _, _ = _http_request(
            http_server.bound_port, "POST", "/v1/transport/record", headers=headers
        )
        assert s == 200
        assert mock_client.transport.recording is True

        # 4. tempo
        s, _, b = _http_request(
            http_server.bound_port,
            "POST",
            "/v1/transport/tempo",
            headers=headers,
            body={"tempo": 140.0},
        )
        assert s == 200
        assert mock_client.transport.tempo == 140.0

        # 5. pos
        s, _, b = _http_request(
            http_server.bound_port,
            "POST",
            "/v1/transport/pos",
            headers=headers,
            body={"pos": 384.0},
        )
        assert s == 200
        assert mock_client.transport.pos == 384.0

    def test_transport_unknown_command(self, http_server: HttpServer) -> None:
        """Verify unsupported transport commands return 400 Bad Request."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "POST", "/v1/transport/rewind", headers=headers
        )
        assert status == 400
        data = json.loads(body.decode("utf-8"))
        assert data["code"] == "E_INVALID_COMMAND"


class TestOpenApiSpecification:
    """Tests for OpenAPI 3.1 specification schema."""

    def test_openapi_schema_endpoint(self, http_server: HttpServer) -> None:
        """Verify /openapi.json delivers valid OpenAPI 3.1 specification."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        status, _, body = _http_request(
            http_server.bound_port, "GET", "/openapi.json", headers=headers
        )
        assert status == 200
        spec = json.loads(body.decode("utf-8"))

        assert spec["openapi"] == "3.1.0"
        assert spec["info"]["title"] == "StudioBridge Local API"
        assert "/v1/status" in spec["paths"]
        assert "/v1/capabilities" in spec["paths"]
        assert "/v1/mixer" in spec["paths"]
        assert "/v1/mixer/{track}/volume" in spec["paths"]
        assert "/v1/transport/{cmd}" in spec["paths"]
        assert "/mcp" in spec["paths"]

        components = spec["components"]
        assert "securitySchemes" in components
        assert "BearerAuth" in components["securitySchemes"]
        assert components["securitySchemes"]["BearerAuth"]["type"] == "http"
        assert components["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"


class TestStreamableMcpTransport:
    """Tests for Streamable HTTP MCP JSON-RPC transport (/mcp)."""

    def test_mcp_initialize_and_tools_list(self, http_server: HttpServer) -> None:
        """Verify MCP initialize and tools/list over HTTP POST /mcp."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}

        # 1. initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "test-http-agent", "version": "1.0"},
            },
        }
        status, _, body = _http_request(
            http_server.bound_port, "POST", "/mcp", headers=headers, body=init_req
        )
        assert status == 200
        init_res = json.loads(body.decode("utf-8"))
        assert init_res["jsonrpc"] == "2.0"
        assert init_res["id"] == 1
        assert "result" in init_res
        assert init_res["result"]["protocolVersion"] == "2026-07-28"

        # 2. tools/list
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        status, _, body = _http_request(
            http_server.bound_port, "POST", "/mcp", headers=headers, body=tools_req
        )
        assert status == 200
        tools_res = json.loads(body.decode("utf-8"))
        assert tools_res["id"] == 2
        tools = tools_res["result"]["tools"]
        assert isinstance(tools, list)
        tool_names = [t["name"] for t in tools]
        assert "studio_status" in tool_names

    def test_mcp_batch_requests(self, http_server: HttpServer) -> None:
        """Verify JSON-RPC batching over POST /mcp."""
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        batch_req = [
            {"jsonrpc": "2.0", "id": 10, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 11, "method": "ping", "params": {}},
        ]
        status, _, body = _http_request(
            http_server.bound_port, "POST", "/mcp", headers=headers, body=batch_req
        )
        assert status == 200
        batch_res = json.loads(body.decode("utf-8"))
        assert isinstance(batch_res, list)
        assert len(batch_res) == 2
        assert batch_res[0]["id"] == 10
        assert batch_res[1]["id"] == 11

    def test_mcp_malformed_json_returns_parse_error(self, http_server: HttpServer) -> None:
        """Verify malformed JSON payload returns JSON-RPC -32700 parse error."""
        headers = {
            "Authorization": f"Bearer {TEST_TOKEN}",
            "Content-Type": "application/json",
        }
        status, _, body = _http_request(
            http_server.bound_port,
            "POST",
            "/mcp",
            headers=headers,
            body="this is not valid json {{{",
        )
        assert status == 400
        err_res = json.loads(body.decode("utf-8"))
        assert err_res["error"]["code"] == -32700

    def test_mcp_text_event_stream_accept(self, http_server: HttpServer) -> None:
        """Verify Accept: text/event-stream header returns SSE event formatting."""
        headers = {
            "Authorization": f"Bearer {TEST_TOKEN}",
            "Accept": "text/event-stream",
        }
        ping_req = {"jsonrpc": "2.0", "id": 42, "method": "ping", "params": {}}
        status, res_headers, body = _http_request(
            http_server.bound_port, "POST", "/mcp", headers=headers, body=ping_req
        )
        assert status == 200
        content_type = res_headers.get("content-type", res_headers.get("Content-Type", ""))
        assert "text/event-stream" in content_type
        body_text = body.decode("utf-8")
        assert body_text.startswith("event: message\ndata: ")


class TestCliServeCommand:
    """Tests for 'sbridge serve' command line interface."""

    def test_parser_serve_arguments(self) -> None:
        """Verify argument parser recognizes serve options."""
        parser = build_parser()
        args = parser.parse_args(
            ["serve", "--port", "9090", "--toolsets", "core,inspect", "--json"]
        )
        assert args.command == "serve"
        assert args.port == 9090
        assert args.toolsets == "core,inspect"
        assert args.json is True

    def test_serve_invalid_host_returns_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify sbridge serve rejects non-loopback host with usage error."""
        code = cli_entry(["serve", "--host", "192.168.1.5", "--json"])
        assert code == 2  # EXIT_USAGE
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["code"] == "E_USAGE"


class TestHeaderValidationHelpers:
    """Tests for origin, referer, and host validation helper functions (# req: SEC-02)."""

    def test_is_trusted_origin(self) -> None:
        """Verify origin header classification (# req: SEC-02)."""
        assert is_trusted_origin(None) is True
        assert is_trusted_origin("") is True
        assert is_trusted_origin("http://127.0.0.1:8080") is True
        assert is_trusted_origin("http://localhost:3000") is True
        assert is_trusted_origin("http://[::1]:8080") is True
        assert is_trusted_origin("chrome-extension://abcdef123456") is True
        assert is_trusted_origin("moz-extension://abcdef123456") is True
        assert is_trusted_origin("https://evil.com") is False
        assert is_trusted_origin("http://192.168.1.1:8080") is False

    def test_is_trusted_referer(self) -> None:
        """Verify referer header classification (# req: SEC-02)."""
        assert is_trusted_referer(None) is True
        assert is_trusted_referer("") is True
        assert is_trusted_referer("http://127.0.0.1:8080/index.html") is True
        assert is_trusted_referer("http://localhost:3000/app") is True
        assert is_trusted_referer("https://evil.com/phish.html") is False

    def test_is_trusted_host(self) -> None:
        """Verify host header classification for DNS rebinding protection (# req: SEC-02)."""
        assert is_trusted_host(None) is True
        assert is_trusted_host("127.0.0.1:8080") is True
        assert is_trusted_host("localhost:8080") is True
        assert is_trusted_host("[::1]:8080") is True
        assert is_trusted_host("evil.com:8080") is False
        assert is_trusted_host("rebind.attacker.org") is False
