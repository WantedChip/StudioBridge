"""Local TCP broker daemon, JSON-RPC 2.0 NDJSON server, and token authentication.

Implements TCP daemon on 127.0.0.1 (OS-assigned port), publishes broker.json metadata,
enforces 256-bit token authentication within 2 seconds [BRK-02], provides NDJSON framing,
handles event fan-out, and auto-exits on idle [BRK-04].
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from anyio.abc import ByteStream, Listener, TaskGroup
from anyio.streams.memory import MemoryObjectSendStream

from studiobridge._version import __version__
from studiobridge.broker.embedded import EmbeddedBroker
from studiobridge.core.errors import BrokerError, StudioBridgeError
from studiobridge.core.logging import get_logger
from studiobridge.core.paths import ensure_app_dirs, get_broker_json_path, get_broker_token_path

logger = get_logger("broker.server")

DEFAULT_AUTH_TIMEOUT: float = 2.0  # seconds per [BRK-02]
DEFAULT_IDLE_EXIT: float = 600.0  # 10 minutes per [BRK-04]
MAX_FRAME_SIZE: int = 8 * 1024 * 1024  # 8 MiB max NDJSON frame


def ensure_broker_token(token_path: Path | None = None) -> str:
    """Ensure a 256-bit random broker token exists on disk with user-only permissions.

    Generates 32 random bytes (64 hex characters) if missing, and restricts file ACLs.
    """
    path = token_path or get_broker_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with contextlib.suppress(Exception):
            token = path.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token

    # Generate fresh 256-bit token
    token = secrets.token_hex(32)
    path.write_text(token, encoding="utf-8")

    # Set user-only read/write permissions (best effort on Windows)
    with contextlib.suppress(Exception):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    return token


class BrokerServer:
    """Local TCP daemon serving JSON-RPC 2.0 requests over NDJSON streams."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        broker: EmbeddedBroker | None = None,
        token: str | None = None,
        token_path: Path | None = None,
        metadata_path: Path | None = None,
        auth_timeout: float = DEFAULT_AUTH_TIMEOUT,
        idle_exit_seconds: float = DEFAULT_IDLE_EXIT,
    ) -> None:
        if host not in ("127.0.0.1", "localhost", "::1"):
            from studiobridge.core.errors import SecurityError

            raise SecurityError(
                f"Broker daemon must bind exclusively to loopback interface: '{host}' is forbidden",
                code="E_SECURITY",
                remedy="Configure broker host to 127.0.0.1 or localhost.",
            )

        self.host: str = host
        self.requested_port: int = port
        self.bound_port: int = 0
        self.auth_timeout: float = auth_timeout
        self.idle_exit_seconds: float = idle_exit_seconds

        self.token_path: Path = token_path or get_broker_token_path()
        self.metadata_path: Path = metadata_path or get_broker_json_path()
        self.token: str = token or ensure_broker_token(self.token_path)

        self.broker: EmbeddedBroker = broker if broker is not None else EmbeddedBroker()

        self._listener: Listener[ByteStream] | None = None
        self._is_running: bool = False
        self._started_at: str = ""
        self._client_senders: dict[str, MemoryObjectSendStream[bytes]] = {}
        self._active_clients: dict[str, ByteStream] = {}
        self._last_activity_time: float = time.monotonic()
        self._tg: TaskGroup | None = None
        self._tg_cm: Any = None

    @property
    def is_running(self) -> bool:
        """Whether the TCP server is currently accepting connections."""
        return self._is_running

    def _write_metadata(self) -> None:
        """Publish broker connection details to broker.json."""
        ensure_app_dirs()
        meta = {
            "pid": os.getpid(),
            "port": self.bound_port,
            "version": __version__,
            "started": self._started_at,
        }
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.metadata_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        temp_path.replace(self.metadata_path)
        logger.info("metadata_written", f"Published broker metadata to {self.metadata_path}")

    def _remove_metadata(self) -> None:
        """Remove broker.json file if it belongs to this process."""
        try:
            if self.metadata_path.exists():
                content = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                if content.get("pid") == os.getpid():
                    self.metadata_path.unlink(missing_ok=True)
        except Exception:
            pass

    async def start(self) -> None:
        """Bind TCP socket, publish metadata, and start background listener."""
        if self._is_running:
            return

        await self.broker.start()

        # Listen exclusively on loopback
        listener = await anyio.create_tcp_listener(
            local_host=self.host,
            local_port=self.requested_port,
        )
        self._listener = listener

        # Retrieve OS-assigned port
        extra = listener.extra(anyio.abc.SocketAttribute.local_port)
        self.bound_port = int(extra)

        self._started_at = datetime.now(timezone.utc).isoformat()
        self._write_metadata()
        self._is_running = True
        self._last_activity_time = time.monotonic()

        self._tg_cm = anyio.create_task_group()
        tg = await self._tg_cm.__aenter__()
        self._tg = tg
        tg.start_soon(self._serve_listener)

        logger.info(
            "server_bound",
            f"Broker listening on {self.host}:{self.bound_port}",
            port=self.bound_port,
        )

    async def _serve_listener(self) -> None:
        """Background worker serving listener incoming connections."""
        assert self._listener is not None
        assert self._tg is not None
        self._tg.start_soon(self._idle_monitor)
        with contextlib.suppress(anyio.get_cancelled_exc_class(), anyio.ClosedResourceError):
            await self._listener.serve(self._handle_client)

    async def serve(self) -> None:
        """Serve connections until cancelled or idle exit triggers."""
        if not self._is_running:
            await self.start()
        while self._is_running:
            await anyio.sleep(0.5)

    async def stop(self) -> None:
        """Gracefully shut down server, disconnect clients, and release ports."""
        if not self._is_running:
            return

        self._is_running = False
        self._remove_metadata()

        for stream in list(self._active_clients.values()):
            with contextlib.suppress(Exception):
                await stream.aclose()
        self._active_clients.clear()
        self._client_senders.clear()

        if self._listener is not None:
            with contextlib.suppress(Exception):
                await self._listener.aclose()
            self._listener = None

        if self._tg is not None:
            self._tg.cancel_scope.cancel()
        if self._tg_cm is not None:
            with contextlib.suppress(Exception):
                await self._tg_cm.__aexit__(None, None, None)
            self._tg_cm = None
            self._tg = None

        await self.broker.stop()
        logger.info("server_stopped", "Broker daemon stopped")

    async def __aenter__(self) -> BrokerServer:
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    # -------------------------------------------------------------------------
    # Idle Watchdog per [BRK-04]
    # -------------------------------------------------------------------------

    async def _idle_monitor(self) -> None:
        """Periodically check for idle inactivity and trigger exit after timeout."""
        if self.idle_exit_seconds <= 0:
            return

        while self._is_running:
            await anyio.sleep(1.0)
            now = time.monotonic()
            no_clients = len(self._active_clients) == 0
            no_subs = len(self.broker._subscriptions) == 0

            if no_clients and no_subs:
                if (now - self._last_activity_time) >= self.idle_exit_seconds:
                    logger.info(
                        "idle_exit",
                        f"No activity for {self.idle_exit_seconds}s, shutting down",
                    )
                    await self.stop()
                    break
            else:
                self._last_activity_time = now

    # -------------------------------------------------------------------------
    # Client Connection & Handshake per [BRK-02]
    # -------------------------------------------------------------------------

    async def _handle_client(self, stream: ByteStream) -> None:
        """Handle individual client TCP stream lifetime."""
        client_id = f"client-{secrets.token_hex(4)}"
        buffer = bytearray()

        # Step 1: Authentication within auth_timeout (2s)
        try:
            with anyio.fail_after(self.auth_timeout):
                authenticated, client_name = await self._authenticate_stream(stream, buffer)
                if not authenticated:
                    await stream.aclose()
                    return
                if client_name:
                    client_id = client_name
        except (TimeoutError, Exception):
            # Auth failed or timed out: drop connection immediately [BRK-02]
            with contextlib.suppress(Exception):
                await stream.aclose()
            return

        self._active_clients[client_id] = stream
        self._last_activity_time = time.monotonic()

        # Channel for writing frames to this client stream asynchronously
        send_stream, receive_stream = anyio.create_memory_object_stream[bytes](max_buffer_size=256)
        self._client_senders[client_id] = send_stream

        async def _client_writer() -> None:
            async with receive_stream:
                async for payload in receive_stream:
                    await stream.send(payload)

        async with anyio.create_task_group() as tg:
            tg.start_soon(_client_writer)
            try:
                # Step 2: NDJSON request/response loop
                while self._is_running:
                    chunk = await stream.receive()
                    if not chunk:
                        break

                    buffer.extend(chunk)
                    if len(buffer) > MAX_FRAME_SIZE:
                        break

                    while b"\n" in buffer:
                        line, _, remaining = buffer.partition(b"\n")
                        buffer = bytearray(remaining)

                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        self._last_activity_time = time.monotonic()
                        response = await self._dispatch_message(line_str, client_id)
                        if response is not None:
                            payload = json.dumps(response).encode("utf-8") + b"\n"
                            await send_stream.send(payload)

            except (anyio.ClosedResourceError, anyio.EndOfStream):
                pass
            except Exception as exc:
                logger.debug("client_error", f"Client {client_id} error: {exc}")
            finally:
                self._active_clients.pop(client_id, None)
                self._client_senders.pop(client_id, None)
                self._last_activity_time = time.monotonic()
                self.broker.on_client_disconnect(client_id)
                with contextlib.suppress(Exception):
                    await send_stream.aclose()
                with contextlib.suppress(Exception):
                    await stream.aclose()
                tg.cancel_scope.cancel()

    async def _authenticate_stream(
        self,
        stream: ByteStream,
        buffer: bytearray,
    ) -> tuple[bool, str | None]:
        """Read and verify the first message containing token credentials within 2s."""
        while b"\n" not in buffer:
            chunk = await stream.receive()
            if not chunk:
                return False, None
            buffer.extend(chunk)
            if len(buffer) > 4096:
                return False, None

        line, _, remaining = buffer.partition(b"\n")
        buffer.clear()
        buffer.extend(remaining)

        msg_str = line.decode("utf-8").strip()
        client_name = None

        # Check raw 'auth <token>' format
        if msg_str.startswith("auth "):
            given_token = msg_str[5:].strip()
            if secrets.compare_digest(given_token, self.token):
                ack = (
                    json.dumps({"jsonrpc": "2.0", "result": {"authenticated": True}}).encode(
                        "utf-8"
                    )
                    + b"\n"
                )
                await stream.send(ack)
                return True, None
            return False, None

        # Check JSON-RPC 'auth' method format
        try:
            msg = json.loads(msg_str)
            if isinstance(msg, dict) and msg.get("method") == "auth":
                req_id = msg.get("id")
                params = msg.get("params") or {}
                if isinstance(params, list) and params:
                    given_token = str(params[0])
                elif isinstance(params, dict):
                    given_token = str(params.get("token", ""))
                    client_name = params.get("client_id")
                else:
                    given_token = str(params)

                if secrets.compare_digest(given_token, self.token):
                    ack_dict = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"authenticated": True, "client_id": client_name},
                    }
                    ack = json.dumps(ack_dict).encode("utf-8") + b"\n"
                    await stream.send(ack)
                    return True, client_name
        except Exception:
            pass

        return False, None

    # -------------------------------------------------------------------------
    # JSON-RPC 2.0 Request Dispatcher
    # -------------------------------------------------------------------------

    async def _dispatch_message(
        self,
        raw_msg: str,
        client_id: str,
    ) -> dict[str, Any] | None:
        """Parse NDJSON line and dispatch to embedded broker."""
        try:
            req = json.loads(raw_msg)
        except json.JSONDecodeError as exc:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }

        if not isinstance(req, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: must be a JSON object"},
            }

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: method is required"},
            }

        # Dispatch method
        try:
            result = await self._execute_method(method, params, client_id)
            if req_id is not None:
                return {"jsonrpc": "2.0", "id": req_id, "result": result}
            return None
        except StudioBridgeError as sbe:
            logger.debug("method_studiobridge_error", f"Error executing {method}: {sbe}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": sbe.message,
                    "data": {
                        "code": sbe.code,
                        "details": sbe.details,
                        "remedy": sbe.remedy,
                    },
                },
            }
        except Exception as exc:
            logger.error("method_unhandled_error", f"Unhandled error in {method}: {exc}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {exc}",
                    "data": {"code": "E_FL", "details": {"exception": str(exc)}},
                },
            }

    async def _execute_method(
        self,
        method: str,
        params: dict[str, Any],
        client_id: str,
    ) -> Any:
        """Map JSON-RPC method name to EmbeddedBroker operations."""
        if method in {"broker.ping", "ping"}:
            return await self.broker.ping()

        if method == "session.info":
            return await self.broker.session_info()

        if method == "broker.status":
            return await self.broker.broker_status()

        if method == "broker.shutdown":
            if self._tg is not None:
                self._tg.cancel_scope.cancel()
            return {"shutdown": True}

        if method == "device.call":
            op = params.get("op", "")
            args = params.get("args") or {}
            opts = params.get("opts")
            priority = params.get("priority")
            timeout = float(params.get("timeout", 5.0))
            return await self.broker.device_call(
                op=op,
                args=args,
                opts=opts,
                client_id=client_id,
                priority=priority,
                timeout=timeout,
            )

        if method == "device.batch":
            ops = params.get("ops") or []
            timeout = float(params.get("timeout", 15.0))
            return await self.broker.device_batch(ops=ops, client_id=client_id, timeout=timeout)

        if method == "device.subscribe":
            topics = params.get("topics") or []

            # Setup streaming callback to push events to this client via memory stream
            def forward_event(topic: str, data: Any) -> None:
                sender = self._client_senders.get(client_id)
                if sender is not None:
                    evt_msg = {
                        "jsonrpc": "2.0",
                        "method": "device.event",
                        "params": {"topic": topic, "data": data},
                    }
                    payload = json.dumps(evt_msg).encode("utf-8") + b"\n"
                    with contextlib.suppress(Exception):
                        sender.send_nowait(payload)

            return await self.broker.device_subscribe(
                topics=topics,
                client_id=client_id,
                callback=forward_event,
            )

        if method == "device.unsubscribe":
            topics = params.get("topics") or []
            return await self.broker.device_unsubscribe(topics=topics, client_id=client_id)

        if method == "lease.acquire":
            ttl = float(params.get("ttl", 15.0))
            purpose = str(params.get("purpose", ""))
            return await self.broker.lease_acquire(owner=client_id, ttl=ttl, purpose=purpose)

        if method == "lease.renew":
            ttl = float(params.get("ttl", 15.0))
            return await self.broker.lease_renew(owner=client_id, ttl=ttl)

        if method == "lease.release":
            return await self.broker.lease_release(owner=client_id)

        raise BrokerError(
            f"Method not found: '{method}'",
            code="E_ARGS",
            details={"method": method},
        )


def main() -> None:
    """CLI / detached process entry point for 'python -m studiobridge.broker.server'."""
    server = BrokerServer()
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        anyio.run(server.serve)


if __name__ == "__main__":
    main()
