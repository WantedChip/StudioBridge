"""Local HTTP REST and Streamable HTTP server for StudioBridge.

Binds strictly to loopback (127.0.0.1), enforces Bearer token authentication
matching broker.token, and validates Origin, Referer, and Host headers to defend
against cross-site request forgery and DNS rebinding attacks.
"""

from __future__ import annotations

import hmac
import http.server
import json
import logging
import threading
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from studiobridge.broker.server import ensure_broker_token
from studiobridge.core.paths import get_broker_token_path
from studiobridge.http.mcp_transport import StreamableMcpTransport
from studiobridge.http.routes import build_openapi_spec, dispatch_v1
from studiobridge.mcp.server import StudioMcpServer

logger = logging.getLogger("studiobridge.http.server")

# Default body size limit (1 MiB)
DEFAULT_MAX_BODY_SIZE = 1024 * 1024

# Allowed loopback host strings
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1"})


def is_trusted_origin(origin: str | None) -> bool:
    """Validate that Origin header is a trusted loopback source or extension."""
    if not origin:
        return True
    try:
        parsed = urllib.parse.urlsplit(origin)
    except Exception:
        return False

    # Browser extensions operate outside web origin restrictions
    if parsed.scheme in ("chrome-extension", "moz-extension"):
        return True

    hostname = (parsed.hostname or "").lower().strip("[]")
    return hostname in LOOPBACK_HOSTS


def is_trusted_referer(referer: str | None) -> bool:
    """Validate that Referer header origin is a trusted loopback address."""
    if not referer:
        return True
    try:
        parsed = urllib.parse.urlsplit(referer)
    except Exception:
        return False

    hostname = (parsed.hostname or "").lower().strip("[]")
    if not hostname:
        return True
    return hostname in LOOPBACK_HOSTS


def is_trusted_host(host_header: str | None) -> bool:
    """Validate Host header against DNS rebinding attacks."""
    if not host_header:
        return True

    if host_header.startswith("["):
        bracket_end = host_header.find("]")
        host_part = host_header[1:bracket_end] if bracket_end != -1 else host_header
    else:
        host_part = host_header.split(":")[0]

    host_part = host_part.lower().strip("[]")
    return host_part in LOOPBACK_HOSTS


class _StudioThreadingHttpServer(http.server.ThreadingHTTPServer):
    """Threading HTTPServer subclass storing server state attributes."""

    expected_token: str
    max_body_size: int
    client: Any
    mcp_transport: StreamableMcpTransport
    url_func: Callable[[], str]


class _StudioHttpRequestHandler(http.server.BaseHTTPRequestHandler):
    """Internal HTTP request handler with origin protection and token authentication."""

    server_version = "StudioBridge-HTTP/1.0"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        """Route request logs to standard logging instead of raw stderr."""
        logger.debug("%s - " + format, self.address_string(), *args)

    def _send_json_response(
        self,
        status_code: int,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a JSON response with standard status headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _verify_security_and_auth(self) -> bool:
        """Enforce origin checks and bearer token authentication."""
        # 1. DNS rebinding protection via Host header validation
        host_hdr = self.headers.get("Host")
        if not is_trusted_host(host_hdr):
            logger.warning("Rejected request with untrusted Host header: %r", host_hdr)
            self._send_json_response(
                403,
                {
                    "status": "error",
                    "code": "E_FORBIDDEN",
                    "message": "Untrusted Host header. Server binds strictly to loopback.",
                },
            )
            return False

        # 2. Cross-site request forgery protection via Origin header check
        origin_hdr = self.headers.get("Origin")
        if not is_trusted_origin(origin_hdr):
            logger.warning("Rejected cross-site request from untrusted Origin: %r", origin_hdr)
            self._send_json_response(
                403,
                {
                    "status": "error",
                    "code": "E_FORBIDDEN",
                    "message": "Untrusted Origin rejected. Server accepts only loopback origins.",
                },
            )
            return False

        # 3. Referer header check
        referer_hdr = self.headers.get("Referer")
        if not is_trusted_referer(referer_hdr):
            logger.warning("Rejected request with untrusted Referer: %r", referer_hdr)
            self._send_json_response(
                403,
                {
                    "status": "error",
                    "code": "E_FORBIDDEN",
                    "message": "Untrusted Referer rejected.",
                },
            )
            return False

        # 4. Bearer token authentication
        auth_hdr = self.headers.get("Authorization")
        if not auth_hdr or not auth_hdr.startswith("Bearer "):
            self._send_json_response(
                401,
                {
                    "status": "error",
                    "code": "E_UNAUTHORIZED",
                    "message": "Missing or invalid Bearer authentication token.",
                },
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )
            return False

        token_candidate = auth_hdr[7:].strip()
        expected_token: str = getattr(self.server, "expected_token", "")
        if not hmac.compare_digest(token_candidate, expected_token):
            self._send_json_response(
                401,
                {
                    "status": "error",
                    "code": "E_UNAUTHORIZED",
                    "message": "Invalid Bearer token.",
                },
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )
            return False

        return True

    def _read_body(self) -> bytes | None:
        """Read and validate request body length against size cap."""
        length_str = self.headers.get("Content-Length")
        if not length_str:
            return b""

        try:
            length = int(length_str)
        except ValueError:
            self._send_json_response(
                400,
                {
                    "status": "error",
                    "code": "E_BAD_REQUEST",
                    "message": "Invalid Content-Length header.",
                },
            )
            return None

        max_size: int = getattr(self.server, "max_body_size", DEFAULT_MAX_BODY_SIZE)
        if length > max_size:
            self._send_json_response(
                413,
                {
                    "status": "error",
                    "code": "E_PAYLOAD_TOO_LARGE",
                    "message": f"Request body exceeds limit of {max_size} bytes.",
                },
            )
            return None

        return self.rfile.read(length)

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS request."""
        if not self._verify_security_and_auth():
            return
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests."""
        if not self._verify_security_and_auth():
            return

        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # OpenAPI schema endpoint
        if path in ("/openapi.json", "/v1/openapi.json"):
            url_func: Callable[[], str] | None = getattr(self.server, "url_func", None)
            server_url = url_func() if url_func else "http://127.0.0.1:8080"
            spec = build_openapi_spec(server_url)
            self._send_json_response(200, spec)
            return

        # MCP GET endpoint probe
        if path == "/mcp":
            self._send_json_response(
                200,
                {
                    "status": "ok",
                    "transport": "streamable_http",
                    "protocol": "mcp",
                },
            )
            return

        # REST routes
        if path.startswith("/v1/"):
            client = getattr(self.server, "client", None)
            status_code, data = dispatch_v1(
                method="GET",
                path=path,
                query_params=query,
                body=None,
                client=client,
            )
            self._send_json_response(status_code, data)
            return

        self._send_json_response(
            404,
            {
                "status": "error",
                "code": "E_NOT_FOUND",
                "message": f"Path '{path}' not found.",
            },
        )

    def do_POST(self) -> None:
        """Handle POST requests."""
        if not self._verify_security_and_auth():
            return

        body_bytes = self._read_body()
        if body_bytes is None:
            return

        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # MCP Streamable HTTP endpoint
        if path == "/mcp":
            mcp_transport: StreamableMcpTransport | None = getattr(
                self.server, "mcp_transport", None
            )
            if mcp_transport is None:
                self._send_json_response(
                    503,
                    {
                        "status": "error",
                        "code": "E_SERVICE_UNAVAILABLE",
                        "message": "MCP transport not configured.",
                    },
                )
                return

            hdr_dict = {k.lower(): v for k, v in self.headers.items()}
            code, res_headers, res_bytes = mcp_transport.handle_request(body_bytes, hdr_dict)
            self.send_response(code)
            for k, v in res_headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(res_bytes)))
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        # REST routes
        if path.startswith("/v1/"):
            client = getattr(self.server, "client", None)
            parsed_body: Any = None
            if body_bytes:
                try:
                    parsed_body = json.loads(body_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json_response(
                        400,
                        {
                            "status": "error",
                            "code": "E_INVALID_PARAMS",
                            "message": "Malformed JSON request body.",
                        },
                    )
                    return

            status_code, data = dispatch_v1(
                method="POST",
                path=path,
                query_params=query,
                body=parsed_body,
                client=client,
            )
            self._send_json_response(status_code, data)
            return

        self._send_json_response(
            404,
            {
                "status": "error",
                "code": "E_NOT_FOUND",
                "message": f"Path '{path}' not found.",
            },
        )


class HttpServer:
    """Local HTTP REST and Streamable HTTP server for StudioBridge."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        token: str | None = None,
        token_path: Path | None = None,
        client: Any = None,
        mcp_server: StudioMcpServer | None = None,
        toolsets: str | None = None,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    ) -> None:
        """Initialize HTTP server.

        Args:
            host: Must be a loopback address ("127.0.0.1", "localhost", "::1").
            port: Port to bind (0 for dynamic ephemeral port).
            token: Explicit Bearer token string override.
            token_path: Path to token file (defaults to %LOCALAPPDATA%/studiobridge/broker.token).
            client: Optional Studio/AsyncStudio high-level client instance.
            mcp_server: Optional StudioMcpServer instance.
            toolsets: Optional MCP toolsets string.
            max_body_size: Request body size cap in bytes (default: 1 MiB).
        """
        normalized_host = host.lower().strip("[]")
        if normalized_host not in LOOPBACK_HOSTS:
            raise ValueError(f"Server must bind strictly to loopback (127.0.0.1), got {host!r}.")

        self.host: str = "127.0.0.1"
        self.requested_port: int = port
        self.token_path: Path = token_path or get_broker_token_path()
        self.token: str = token or ensure_broker_token(self.token_path)
        self.max_body_size: int = max_body_size

        self.client: Any = client
        self.mcp_server: StudioMcpServer = (
            mcp_server if mcp_server is not None else StudioMcpServer(toolsets=toolsets)
        )
        self.mcp_transport: StreamableMcpTransport = StreamableMcpTransport(self.mcp_server)

        self._httpd: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._bound_port: int = 0
        self._is_running: bool = False

    @property
    def is_running(self) -> bool:
        """Whether the HTTP server is currently accepting connections."""
        return self._is_running

    @property
    def bound_port(self) -> int:
        """The port on which the server is listening."""
        return self._bound_port

    @property
    def url(self) -> str:
        """Full loopback base URL of the running server."""
        return f"http://127.0.0.1:{self.bound_port}"

    def start(self, background: bool = True) -> None:
        """Start the HTTP server.

        Args:
            background: If True, runs the server on a daemon background thread.
        """
        if self._is_running:
            return

        httpd = _StudioThreadingHttpServer(
            (self.host, self.requested_port),
            _StudioHttpRequestHandler,
        )

        httpd.expected_token = self.token
        httpd.max_body_size = self.max_body_size
        httpd.client = self.client
        httpd.mcp_transport = self.mcp_transport
        httpd.url_func = lambda: self.url

        self._httpd = httpd
        self._bound_port = httpd.server_address[1]
        self._is_running = True

        if background:
            self._thread = threading.Thread(
                target=httpd.serve_forever,
                name="StudioBridge-HttpServer",
                daemon=True,
            )
            self._thread.start()
            logger.info("HTTP server started at %s", self.url)
        else:
            logger.info("HTTP server serving in foreground at %s", self.url)
            try:
                httpd.serve_forever()
            finally:
                self.stop()

    def stop(self) -> None:
        """Stop the HTTP server and release port."""
        if not self._is_running:
            return

        self._is_running = False
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None

        logger.info("HTTP server stopped.")

    def __enter__(self) -> HttpServer:
        self.start(background=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.stop()
