"""Local HTTP REST and Streamable HTTP interface for StudioBridge."""

from __future__ import annotations

from studiobridge.http.mcp_transport import StreamableMcpTransport
from studiobridge.http.routes import build_openapi_spec, dispatch_v1
from studiobridge.http.server import (
    HttpServer,
    is_trusted_host,
    is_trusted_origin,
    is_trusted_referer,
)

__all__ = [
    "HttpServer",
    "StreamableMcpTransport",
    "build_openapi_spec",
    "dispatch_v1",
    "is_trusted_host",
    "is_trusted_origin",
    "is_trusted_referer",
]
