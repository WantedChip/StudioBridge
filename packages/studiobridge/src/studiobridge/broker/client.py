"""Async client and process supervisor for StudioBridge local TCP daemon.

Implements BrokerClient with JSON-RPC 2.0 NDJSON communication, automatic response
matching, event fan-out subscription handling, and ensure_broker() detached process
auto-start and crash recovery per [BRK-02], [BRK-03], [BRK-05], [BRK-06].
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from anyio.abc import ByteStream, TaskGroup

from studiobridge.core.errors import BrokerError
from studiobridge.core.logging import get_logger
from studiobridge.core.paths import get_app_data_dir, get_broker_json_path, get_broker_token_path

logger = get_logger("broker.client")


def is_process_alive(pid: int) -> bool:
    """Check if a process with given PID is currently running."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == 259  # STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@contextlib.contextmanager
def file_lock(lock_path: Path, timeout: float = 5.0):
    """Exclusive file lock using OS primitives to prevent startup races [BRK-03]."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout

    fd = None
    while time.monotonic() < deadline:
        try:
            if sys.platform == "win32":
                import msvcrt

                fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            else:
                import fcntl

                fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
        except OSError:
            if fd is not None:
                os.close(fd)
                fd = None
            time.sleep(0.05)

    if fd is None:
        raise BrokerError(
            f"Could not acquire broker startup lock at {lock_path} within {timeout}s",
            code="E_BUSY",
            retryable=True,
        )

    try:
        yield
    finally:
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except Exception:
            pass


async def _ping_port(host: str, port: int, token: str, timeout: float = 1.0) -> bool:
    """Quickly verify if a broker is running on host:port and responds to ping."""
    try:
        with anyio.fail_after(timeout):
            stream = await anyio.connect_tcp(host, port)
            async with stream:
                # Send auth
                auth_req = (
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "auth",
                            "params": {"token": token},
                        }
                    ).encode("utf-8")
                    + b"\n"
                )
                await stream.send(auth_req)

                chunk = await stream.receive()
                if b'"authenticated": true' not in chunk and b'"authenticated":true' not in chunk:
                    return False

                # Send ping
                ping_req = (
                    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "broker.ping"}).encode("utf-8")
                    + b"\n"
                )
                await stream.send(ping_req)

                chunk2 = await stream.receive()
                return b'"pong"' in chunk2
    except Exception:
        return False


def ensure_broker(
    *,
    host: str = "127.0.0.1",
    timeout: float = 8.0,
    metadata_path: Path | None = None,
    token_path: Path | None = None,
) -> tuple[str, int]:
    """Ensure a local broker daemon is running, starting a detached process if needed.

    Adheres to [BRK-03] and [BRK-06]:
    1. Checks broker.json metadata.
    2. Verifies PID is alive.
    3. Cleans up stale broker.json if dead.
    4. Acquires exclusive lockfile and spawns detached process with DETACHED_PROCESS flag.
    5. Polls for readiness within timeout.

    Returns:
        (host, port) of the active broker daemon.
    """
    meta_p = metadata_path or get_broker_json_path()
    tok_p = token_path or get_broker_token_path()
    lock_p = get_app_data_dir() / "broker.lock"

    # Step 1: Check existing broker.json
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            pid = int(meta.get("pid", 0))
            port = int(meta.get("port", 0))
            token = tok_p.read_text(encoding="utf-8").strip() if tok_p.exists() else ""

            if is_process_alive(pid) and port > 0 and token:
                ok = anyio.run(_ping_port, host, port, token, 1.0)
                if ok:
                    return host, port

            # Process dead or unresponsive: crash recovery per [BRK-06]
            logger.warning("stale_broker_detected", f"Removing stale broker metadata (pid={pid})")
            meta_p.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("broker_check_error", f"Error checking existing broker: {exc}")
            meta_p.unlink(missing_ok=True)

    # Step 2: Spawn detached broker under lockfile synchronization
    with file_lock(lock_p, timeout=5.0):
        # Double check if another process started it while we waited for lock
        if meta_p.exists():
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                pid = int(meta.get("pid", 0))
                port = int(meta.get("port", 0))
                if is_process_alive(pid) and port > 0:
                    return host, port
            except Exception:
                pass

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        cmd = [sys.executable, "-m", "studiobridge.broker.server"]
        logger.info("spawning_broker", f"Starting detached broker daemon: {cmd}")
        subprocess.Popen(
            cmd,
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Step 3: Poll for readiness
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if meta_p.exists():
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                pid = int(meta.get("pid", 0))
                port = int(meta.get("port", 0))
                if port > 0 and is_process_alive(pid):
                    token = tok_p.read_text(encoding="utf-8").strip() if tok_p.exists() else ""
                    if token:
                        ok = anyio.run(_ping_port, host, port, token, 0.5)
                        if ok:
                            return host, port
            except Exception:
                pass
        time.sleep(0.1)

    raise BrokerError(
        f"Broker failed to start and respond on {host} within {timeout}s",
        code="E_NOBROKER",
        retryable=True,
        remedy=(
            "Run 'sbridge broker start' manually or inspect logs in "
            "%LOCALAPPDATA%\\studiobridge\\logs."
        ),
    )


class BrokerClient:
    """Async client communicating with local StudioBridge broker over TCP."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int | None = None,
        token: str | None = None,
        client_id: str | None = None,
        metadata_path: Path | None = None,
        token_path: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.client_id = client_id or f"client-{os.getpid()}-{time.time_ns() % 1000000}"
        self.metadata_path = metadata_path or get_broker_json_path()
        self.token_path = token_path or get_broker_token_path()

        self._stream: ByteStream | None = None
        self._is_connected: bool = False
        self._next_id: int = 1
        self._buffer: bytearray = bytearray()

        # id -> (anyio.Event, dict result/error)
        self._pending: dict[int, tuple[anyio.Event, dict[str, Any]]] = {}

        # topic -> list[Callable[[str, Any], None]]
        self._event_callbacks: dict[str, list[Callable[[str, Any], None]]] = {}

        self._reader_running: bool = False
        self._tg: TaskGroup | None = None
        self._tg_cm: Any = None

    @property
    def is_connected(self) -> bool:
        """Whether TCP connection to the broker is open and authenticated."""
        return self._is_connected

    async def connect(self) -> None:
        """Connect to local broker daemon and authenticate."""
        if self._is_connected:
            return

        # Resolve port
        if self.port is None:
            if not self.metadata_path.exists():
                raise BrokerError(
                    f"Broker metadata not found at {self.metadata_path}. Broker is not running.",
                    code="E_NOBROKER",
                    retryable=True,
                )
            meta = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self.port = int(meta["port"])

        # Resolve token
        if self.token is None:
            if not self.token_path.exists():
                raise BrokerError(
                    f"Broker token not found at {self.token_path}.",
                    code="E_AUTH",
                    retryable=False,
                )
            self.token = self.token_path.read_text(encoding="utf-8").strip()

        # Connect TCP socket
        self._stream = await anyio.connect_tcp(self.host, self.port)

        # Authenticate immediately within 2 seconds [BRK-02]
        auth_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "auth",
            "params": {"token": self.token, "client_id": self.client_id},
        }
        await self._stream.send(json.dumps(auth_msg).encode("utf-8") + b"\n")

        # Read auth acknowledgment
        self._buffer.clear()
        with anyio.fail_after(2.0):
            while b"\n" not in self._buffer:
                chunk = await self._stream.receive()
                if not chunk:
                    raise BrokerError("Connection closed during authentication", code="E_AUTH")
                self._buffer.extend(chunk)

            line, _, remaining = self._buffer.partition(b"\n")
            self._buffer = bytearray(remaining)
            ack = json.loads(line.decode("utf-8"))
            if "error" in ack or not ack.get("result", {}).get("authenticated"):
                await self._stream.aclose()
                raise BrokerError(
                    "Broker rejected authentication token",
                    code="E_AUTH",
                    retryable=False,
                )

        self._is_connected = True

    async def _background_reader(self) -> None:
        """Continuously read lines from stream and dispatch responses / events."""
        assert self._stream is not None
        self._reader_running = True
        try:
            while self._is_connected:
                chunk = await self._stream.receive()
                if not chunk:
                    break
                self._buffer.extend(chunk)
                while b"\n" in self._buffer:
                    line, _, rem = self._buffer.partition(b"\n")
                    self._buffer = bytearray(rem)
                    line_str = line.decode("utf-8").strip()
                    if line_str:
                        self._handle_incoming_line(line_str)
        except (anyio.ClosedResourceError, anyio.EndOfStream):
            pass
        except Exception as exc:
            logger.debug("client_reader_error", f"Reader loop error: {exc}")
        finally:
            self._reader_running = False

    async def close(self) -> None:
        """Close client connection."""
        self._is_connected = False
        if self._stream is not None:
            with contextlib.suppress(Exception):
                await self._stream.aclose()
            self._stream = None

    async def __aenter__(self) -> BrokerClient:
        await self.connect()
        self._tg_cm = anyio.create_task_group()
        tg = await self._tg_cm.__aenter__()
        self._tg = tg
        tg.start_soon(self._background_reader)
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
        if self._tg_cm is not None:
            await self._tg_cm.__aexit__(*args)

    def _handle_incoming_line(self, line: str) -> None:
        """Handle a single parsed NDJSON line (response or event notification)."""
        try:
            msg = json.loads(line)
        except Exception:
            return

        if not isinstance(msg, dict):
            return

        # 1. Event notification
        if msg.get("method") == "device.event":
            params = msg.get("params") or {}
            topic = params.get("topic", "")
            data = params.get("data")
            callbacks = self._event_callbacks.get(topic, []) + self._event_callbacks.get("*", [])
            for cb in callbacks:
                with contextlib.suppress(Exception):
                    cb(topic, data)
            return

        # 2. Response to a pending request
        req_id = msg.get("id")
        if req_id in self._pending:
            event, holder = self._pending[req_id]
            holder["response"] = msg
            event.set()

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Any:
        """Send a JSON-RPC 2.0 request and wait for the response."""
        if not self._is_connected or self._stream is None:
            await self.connect()
            assert self._stream is not None

        req_id = self._next_id
        self._next_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        event = anyio.Event()
        holder: dict[str, Any] = {}
        self._pending[req_id] = (event, holder)

        line = json.dumps(payload).encode("utf-8") + b"\n"
        await self._stream.send(line)

        try:
            if self._reader_running:
                # Background reader task is consuming stream
                with anyio.fail_after(timeout):
                    await event.wait()
            else:
                # Inline read loop when background reader is not active
                with anyio.fail_after(timeout):
                    while "response" not in holder:
                        chunk = await self._stream.receive()
                        if not chunk:
                            raise BrokerError("Connection closed by broker", code="E_DISCONNECTED")
                        self._buffer.extend(chunk)
                        while b"\n" in self._buffer:
                            l_bytes, _, rem = self._buffer.partition(b"\n")
                            self._buffer = bytearray(rem)
                            l_str = l_bytes.decode("utf-8").strip()
                            if l_str:
                                self._handle_incoming_line(l_str)

            msg = holder["response"]
            if "error" in msg:
                err = msg["error"]
                data = err.get("data", {})
                code = data.get("code", "E_FL") if isinstance(data, dict) else "E_FL"
                details = data.get("details", {}) if isinstance(data, dict) else {}
                remedy = data.get("remedy") if isinstance(data, dict) else None
                raise BrokerError(
                    err.get("message", "Broker error"),
                    code=code,
                    details=details,
                    remedy=remedy,
                )
            return msg.get("result")

        except TimeoutError as exc:
            raise BrokerError(
                f"Request {method} (id={req_id}) timed out after {timeout}s",
                code="E_TIMEOUT",
                retryable=True,
            ) from exc
        finally:
            self._pending.pop(req_id, None)

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def session_info(self) -> dict[str, Any]:
        """Query active session information."""
        return await self.call("session.info")

    async def ping(self) -> dict[str, Any]:
        """Ping broker daemon."""
        return await self.call("broker.ping")

    async def status(self) -> dict[str, Any]:
        """Fetch broker telemetry and health status."""
        return await self.call("broker.status")

    async def shutdown(self) -> dict[str, Any]:
        """Ask broker daemon to shut down."""
        return await self.call("broker.shutdown")

    async def device_call(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        opts: dict[str, Any] | None = None,
        priority: str | None = None,
        timeout: float = 5.0,
    ) -> Any:
        """Call a device operation through the broker."""
        params: dict[str, Any] = {"op": op, "args": args or {}, "timeout": timeout}
        if opts is not None:
            params["opts"] = opts
        if priority is not None:
            params["priority"] = priority
        return await self.call("device.call", params, timeout=timeout + 2.0)

    async def device_batch(self, ops: list[dict[str, Any]], timeout: float = 15.0) -> list[Any]:
        """Execute a batch of device operations through the broker."""
        return await self.call(
            "device.batch",
            {"ops": ops, "timeout": timeout},
            timeout=timeout + 2.0,
        )

    async def device_subscribe(
        self,
        topics: list[str],
        callback: Callable[[str, Any], None] | None = None,
    ) -> dict[str, Any]:
        """Subscribe to device events."""
        if callback is not None:
            for topic in topics:
                self._event_callbacks.setdefault(topic, []).append(callback)
        return await self.call("device.subscribe", {"topics": topics})

    async def device_unsubscribe(self, topics: list[str]) -> dict[str, Any]:
        """Unsubscribe from device events."""
        for topic in topics:
            self._event_callbacks.pop(topic, None)
        return await self.call("device.unsubscribe", {"topics": topics})

    async def lease_acquire(self, ttl: float = 15.0, purpose: str = "") -> dict[str, Any]:
        """Acquire writer lease."""
        return await self.call("lease.acquire", {"ttl": ttl, "purpose": purpose})

    async def lease_renew(self, ttl: float = 15.0) -> dict[str, Any]:
        """Renew writer lease."""
        return await self.call("lease.renew", {"ttl": ttl})

    async def lease_release(self) -> dict[str, Any]:
        """Release writer lease."""
        return await self.call("lease.release")
