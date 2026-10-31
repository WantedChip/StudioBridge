"""REST route handlers and OpenAPI specification generator for StudioBridge HTTP server.

Maps high-level client operations to JSON REST endpoints under /v1/ and provides
OpenAPI 3.1 specification generation.
"""

from __future__ import annotations

import re
from typing import Any

from studiobridge._version import __version__

# Pre-compiled route pattern regular expressions
_RE_MIXER_TRACK = re.compile(r"^/v1/mixer/(?P<track>\d+)$")
_RE_MIXER_VOLUME = re.compile(r"^/v1/mixer/(?P<track>\d+)/volume$")
_RE_TRANSPORT_CMD = re.compile(r"^/v1/transport/(?P<cmd>[a-zA-Z0-9_-]+)$")


def build_openapi_spec(server_url: str = "http://127.0.0.1:8080") -> dict[str, Any]:
    """Generate OpenAPI 3.1.0 specification for StudioBridge local HTTP service."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "StudioBridge Local API",
            "version": __version__,
            "description": (
                "Local REST API and Streamable HTTP MCP interface for StudioBridge. "
                "Provides programmatic control of transport, mixer, and session state."
            ),
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        },
        "servers": [
            {
                "url": server_url,
                "description": "Local loopback instance",
            }
        ],
        "security": [{"BearerAuth": []}],
        "paths": {
            "/v1/status": {
                "get": {
                    "summary": "Get session and engine status",
                    "description": (
                        "Returns current session status, engine version, and active mode."
                    ),
                    "operationId": "getStatus",
                    "responses": {
                        "200": {
                            "description": "Successful status snapshot",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StatusResponse"}
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/v1/capabilities": {
                "get": {
                    "summary": "Get capability registry status",
                    "description": (
                        "Returns all registered capabilities and their evaluated states."
                    ),
                    "operationId": "getCapabilities",
                    "responses": {
                        "200": {
                            "description": "Registered capabilities dictionary",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/CapabilitiesResponse"}
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/v1/mixer": {
                "get": {
                    "summary": "List mixer tracks",
                    "description": (
                        "Returns mixer track parameters (volume, pan, mute, solo, peak)."
                    ),
                    "operationId": "listMixerTracks",
                    "parameters": [
                        {
                            "name": "count",
                            "in": "query",
                            "description": "Optional maximum number of tracks to return",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 1, "maximum": 127},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of mixer tracks",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MixerTracksResponse"}
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "503": {"$ref": "#/components/responses/ServiceUnavailable"},
                    },
                }
            },
            "/v1/mixer/{track}": {
                "get": {
                    "summary": "Get specific mixer track",
                    "description": "Returns parameters for an individual mixer track by index.",
                    "operationId": "getMixerTrack",
                    "parameters": [
                        {
                            "name": "track",
                            "in": "path",
                            "description": "0-based mixer track index (0 = Master)",
                            "required": True,
                            "schema": {"type": "integer", "minimum": 0, "maximum": 126},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Mixer track details",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MixerTrackResponse"}
                                }
                            },
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "503": {"$ref": "#/components/responses/ServiceUnavailable"},
                    },
                }
            },
            "/v1/mixer/{track}/volume": {
                "post": {
                    "summary": "Set mixer track volume",
                    "description": (
                        "Sets the fader volume level (0.0 to 1.0) for a specified mixer track."
                    ),
                    "operationId": "setMixerVolume",
                    "parameters": [
                        {
                            "name": "track",
                            "in": "path",
                            "description": "0-based mixer track index (0 = Master)",
                            "required": True,
                            "schema": {"type": "integer", "minimum": 0, "maximum": 126},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/VolumeRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Volume updated successfully",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/VolumeResponse"}
                                }
                            },
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "503": {"$ref": "#/components/responses/ServiceUnavailable"},
                    },
                }
            },
            "/v1/transport/{cmd}": {
                "post": {
                    "summary": "Execute transport command",
                    "description": "Controls playback, recording, tempo, and song position.",
                    "operationId": "executeTransportCommand",
                    "parameters": [
                        {
                            "name": "cmd",
                            "in": "path",
                            "description": "Transport command: play, stop, record, tempo, pos",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "enum": ["play", "stop", "record", "tempo", "pos"],
                            },
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TransportRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Transport command executed",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TransportResponse"}
                                }
                            },
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                        "503": {"$ref": "#/components/responses/ServiceUnavailable"},
                    },
                }
            },
            "/mcp": {
                "post": {
                    "summary": "Streamable HTTP MCP JSON-RPC endpoint",
                    "description": (
                        "Streamable HTTP transport endpoint accepting JSON-RPC 2.0 requests "
                        "for Model Context Protocol (MCP) clients."
                    ),
                    "operationId": "postMcpMessage",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "JSON-RPC 2.0 response",
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                                "text/event-stream": {"schema": {"type": "string"}},
                            },
                        },
                        "204": {"description": "Notification acknowledged without response"},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
            "/openapi.json": {
                "get": {
                    "summary": "Retrieve OpenAPI 3.1 specification",
                    "description": (
                        "Returns the machine-readable OpenAPI 3.1 schema for this server."
                    ),
                    "operationId": "getOpenApiSpec",
                    "responses": {
                        "200": {
                            "description": "OpenAPI specification document",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "403": {"$ref": "#/components/responses/Forbidden"},
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Token",
                    "description": "Bearer token matching broker.token on local host",
                }
            },
            "schemas": {
                "StatusResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "fl_version": {"type": "string"},
                                "api": {"type": "integer"},
                                "project": {"type": ["string", "null"]},
                                "mode": {"type": "string"},
                                "rtt": {"type": "number"},
                                "connected": {"type": "boolean"},
                            },
                        },
                    },
                },
                "CapabilitiesResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "capabilities": {"type": "object"},
                            },
                        },
                    },
                },
                "MixerTrack": {
                    "type": "object",
                    "required": ["index", "name", "volume", "pan", "muted", "solo"],
                    "properties": {
                        "index": {"type": "integer"},
                        "name": {"type": "string"},
                        "volume": {"type": "number"},
                        "pan": {"type": "number"},
                        "muted": {"type": "boolean"},
                        "solo": {"type": "boolean"},
                        "color": {"type": "integer"},
                        "armed": {"type": "boolean"},
                        "peak": {"type": "number"},
                    },
                },
                "MixerTracksResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "tracks": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/MixerTrack"},
                                },
                            },
                        },
                    },
                },
                "MixerTrackResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {"$ref": "#/components/schemas/MixerTrack"},
                    },
                },
                "VolumeRequest": {
                    "type": "object",
                    "required": ["volume"],
                    "properties": {
                        "volume": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Fader volume level (0.0 to 1.0)",
                        },
                    },
                },
                "VolumeResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "track": {"type": "integer"},
                                "volume": {"type": "number"},
                            },
                        },
                    },
                },
                "TransportRequest": {
                    "type": "object",
                    "properties": {
                        "tempo": {
                            "type": "number",
                            "description": "Tempo in BPM (for tempo command)",
                        },
                        "pos": {
                            "type": "number",
                            "description": "Position in song (for pos command)",
                        },
                    },
                },
                "TransportResponse": {
                    "type": "object",
                    "required": ["status", "data"],
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string"},
                            },
                        },
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "required": ["status", "code", "message"],
                    "properties": {
                        "status": {"type": "string", "example": "error"},
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                    },
                },
            },
            "responses": {
                "BadRequest": {
                    "description": "Invalid parameters or malformed request payload",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                },
                "Unauthorized": {
                    "description": "Missing, invalid, or expired Bearer token",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                },
                "Forbidden": {
                    "description": (
                        "Request rejected due to untrusted Origin, Referer, or Host header"
                    ),
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                },
                "NotFound": {
                    "description": "Requested resource or path does not exist",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                },
                "ServiceUnavailable": {
                    "description": "Engine or client disconnected",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                },
            },
        },
    }


def dispatch_v1(
    method: str,
    path: str,
    query_params: dict[str, list[str]],
    body: Any,
    client: Any,
) -> tuple[int, dict[str, Any]]:
    """Dispatch REST operations under /v1/ to client methods."""
    method = method.upper()

    # GET /v1/status
    if method == "GET" and path == "/v1/status":
        if client is not None:
            try:
                if hasattr(client, "status"):
                    status_obj = client.status()
                    data = status_obj.to_dict() if hasattr(status_obj, "to_dict") else status_obj
                    return 200, {"status": "ok", "data": data}
            except Exception as exc:
                return 200, {
                    "status": "ok",
                    "data": {
                        "connected": False,
                        "error": str(exc),
                    },
                }
        return 200, {
            "status": "ok",
            "data": {
                "connected": False,
                "mode": "disconnected",
                "fl_version": "unknown",
            },
        }

    # GET /v1/capabilities
    if method == "GET" and path == "/v1/capabilities":
        caps_dict: dict[str, Any] = {}
        if client is not None and hasattr(client, "caps"):
            if hasattr(client.caps, "to_dict"):
                caps_dict = client.caps.to_dict()
            elif hasattr(client.caps, "aggregate_status"):
                caps_dict = client.caps.aggregate_status()
        return 200, {"status": "ok", "data": {"capabilities": caps_dict}}

    # GET /v1/mixer
    if method == "GET" and path == "/v1/mixer":
        if client is None or not getattr(client, "is_connected", True):
            return 503, {
                "status": "error",
                "code": "E_DISCONNECTED",
                "message": "Client is not connected to engine.",
            }

        count: int | None = None
        if "count" in query_params and query_params["count"]:
            try:
                count = int(query_params["count"][0])
            except ValueError:
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "Query parameter 'count' must be an integer.",
                }

        try:
            tracks_raw = client.mixer.get_tracks(count=count)
            tracks: list[dict[str, Any]] = []
            for t in tracks_raw:
                if hasattr(t, "index"):
                    tracks.append(
                        {
                            "index": t.index,
                            "name": str(t.name),
                            "volume": float(t.volume),
                            "pan": float(t.pan),
                            "muted": bool(t.muted),
                            "solo": bool(t.solo),
                            "color": int(t.color),
                            "armed": bool(t.armed),
                            "peak": float(t.peak),
                        }
                    )
                elif isinstance(t, dict):
                    tracks.append(t)
            return 200, {"status": "ok", "data": {"tracks": tracks}}
        except Exception as exc:
            return 500, {
                "status": "error",
                "code": "E_INTERNAL",
                "message": f"Failed to retrieve mixer tracks: {exc}",
            }

    # GET /v1/mixer/{track}
    m_track = _RE_MIXER_TRACK.match(path)
    if method == "GET" and m_track:
        if client is None or not getattr(client, "is_connected", True):
            return 503, {
                "status": "error",
                "code": "E_DISCONNECTED",
                "message": "Client is not connected to engine.",
            }

        track_idx = int(m_track.group("track"))
        try:
            t = client.mixer.get_track(track_idx)
            track_data = {
                "index": t.index if hasattr(t, "index") else track_idx,
                "name": str(t.name) if hasattr(t, "name") else "",
                "volume": float(t.volume) if hasattr(t, "volume") else 0.8,
                "pan": float(t.pan) if hasattr(t, "pan") else 0.0,
                "muted": bool(t.muted) if hasattr(t, "muted") else False,
                "solo": bool(t.solo) if hasattr(t, "solo") else False,
                "color": int(t.color) if hasattr(t, "color") else 0,
                "armed": bool(t.armed) if hasattr(t, "armed") else False,
                "peak": float(t.peak) if hasattr(t, "peak") else 0.0,
            }
            return 200, {"status": "ok", "data": track_data}
        except Exception as exc:
            return 404, {
                "status": "error",
                "code": "E_NOT_FOUND",
                "message": f"Track {track_idx} not found or error occurred: {exc}",
            }

    # POST /v1/mixer/{track}/volume
    m_vol = _RE_MIXER_VOLUME.match(path)
    if method == "POST" and m_vol:
        if client is None or not getattr(client, "is_connected", True):
            return 503, {
                "status": "error",
                "code": "E_DISCONNECTED",
                "message": "Client is not connected to engine.",
            }

        track_idx = int(m_vol.group("track"))
        if not isinstance(body, dict) or "volume" not in body:
            return 400, {
                "status": "error",
                "code": "E_INVALID_PARAMS",
                "message": "Request body must contain 'volume' float parameter.",
            }

        try:
            vol_val = float(body["volume"])
        except (ValueError, TypeError):
            return 400, {
                "status": "error",
                "code": "E_INVALID_PARAMS",
                "message": "'volume' parameter must be a numeric float value.",
            }

        if not (0.0 <= vol_val <= 1.0):
            return 400, {
                "status": "error",
                "code": "E_INVALID_PARAMS",
                "message": "'volume' parameter must be between 0.0 and 1.0 inclusive.",
            }

        try:
            client.mixer.set_volume(track_idx, vol_val)
            return 200, {
                "status": "ok",
                "data": {
                    "track": track_idx,
                    "volume": vol_val,
                },
            }
        except Exception as exc:
            return 500, {
                "status": "error",
                "code": "E_INTERNAL",
                "message": f"Failed to set mixer volume: {exc}",
            }

    # POST /v1/transport/{cmd}
    m_trans = _RE_TRANSPORT_CMD.match(path)
    if method == "POST" and m_trans:
        if client is None or not getattr(client, "is_connected", True):
            return 503, {
                "status": "error",
                "code": "E_DISCONNECTED",
                "message": "Client is not connected to engine.",
            }

        cmd = m_trans.group("cmd").lower()
        if cmd == "play":
            try:
                client.transport.play()
                return 200, {"status": "ok", "data": {"command": "play"}}
            except Exception as exc:
                return 500, {
                    "status": "error",
                    "code": "E_INTERNAL",
                    "message": f"Transport play failed: {exc}",
                }

        if cmd == "stop":
            try:
                client.transport.stop()
                return 200, {"status": "ok", "data": {"command": "stop"}}
            except Exception as exc:
                return 500, {
                    "status": "error",
                    "code": "E_INTERNAL",
                    "message": f"Transport stop failed: {exc}",
                }

        if cmd == "record":
            try:
                client.transport.record()
                return 200, {"status": "ok", "data": {"command": "record"}}
            except Exception as exc:
                return 500, {
                    "status": "error",
                    "code": "E_INTERNAL",
                    "message": f"Transport record failed: {exc}",
                }

        if cmd == "tempo":
            if not isinstance(body, dict) or "tempo" not in body:
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": (
                        "Request body must contain 'tempo' float parameter for tempo command."
                    ),
                }
            try:
                bpm = float(body["tempo"])
            except (ValueError, TypeError):
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "'tempo' parameter must be a numeric BPM float.",
                }
            if bpm <= 0.0 or bpm > 1000.0:
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "'tempo' must be a positive BPM value between 1.0 and 1000.0.",
                }

            try:
                client.transport.set_tempo(bpm)
                return 200, {
                    "status": "ok",
                    "data": {
                        "command": "tempo",
                        "tempo": bpm,
                    },
                }
            except Exception as exc:
                return 500, {
                    "status": "error",
                    "code": "E_INTERNAL",
                    "message": f"Failed to set tempo: {exc}",
                }

        if cmd in ("pos", "time"):
            if not isinstance(body, dict) or ("pos" not in body and "time" not in body):
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "Request body must contain 'pos' or 'time' float parameter.",
                }
            raw_pos = body.get("pos") if "pos" in body else body.get("time")
            if raw_pos is None:
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "Position parameter cannot be null.",
                }
            try:
                pos_val = float(raw_pos)
            except (ValueError, TypeError):
                return 400, {
                    "status": "error",
                    "code": "E_INVALID_PARAMS",
                    "message": "Position parameter must be numeric.",
                }

            try:
                client.transport.set_time(pos_val)
                return 200, {
                    "status": "ok",
                    "data": {
                        "command": "pos",
                        "pos": pos_val,
                    },
                }
            except Exception as exc:
                return 500, {
                    "status": "error",
                    "code": "E_INTERNAL",
                    "message": f"Failed to set song position: {exc}",
                }

        return 400, {
            "status": "error",
            "code": "E_INVALID_COMMAND",
            "message": f"Unsupported transport command '{cmd}'.",
            "supported_commands": ["play", "stop", "record", "tempo", "pos"],
        }

    return 404, {
        "status": "error",
        "code": "E_NOT_FOUND",
        "message": f"Endpoint '{method} {path}' not found.",
    }
