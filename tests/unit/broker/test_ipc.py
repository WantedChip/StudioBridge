"""Component and integration tests for Broker TCP Server, Client, and IPC.

Verifies:
- Multi-client concurrent TCP connections.
- Unauthenticated TCP connection dropped within 2 seconds [BRK-02].
- Concurrent reads from multiple clients execute without blocking.
- Non-lease holders attempting mutating writes are rejected with E_LEASE.
- Event fan-out across multiple connected client subscriptions.
- Abrupt client disconnection automatically revokes writer lease [BRK-10].
- Auto-start recovery with ensure_broker().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import pytest

from studiobridge.broker.client import BrokerClient, ensure_broker
from studiobridge.broker.embedded import EmbeddedBroker
from studiobridge.broker.server import BrokerServer
from studiobridge.core.errors import BrokerError


@pytest.fixture
def broker_paths(tmp_path: Path) -> tuple[Path, Path]:
    """Create isolated temporary paths for broker metadata and token."""
    meta_path = tmp_path / "broker.json"
    tok_path = tmp_path / "broker.token"
    return meta_path, tok_path


@pytest.mark.anyio
async def test_auth_timeout_drops_unauthenticated_connection(
    broker_paths: tuple[Path, Path],
) -> None:
    """Verify that connections failing to authenticate within 2s are dropped [BRK-02]."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    tok_path.write_text(token, encoding="utf-8")

    server = BrokerServer(
        port=0,
        token=token,
        metadata_path=meta_path,
        token_path=tok_path,
        auth_timeout=0.3,  # Fast timeout for test
    )
    await server.start()

    try:
        # Open raw connection and do NOT send auth token
        stream = await anyio.connect_tcp("127.0.0.1", server.bound_port)
        async with stream:
            # Wait for server to drop connection due to auth timeout
            try:
                with anyio.fail_after(1.0):
                    chunk = await stream.receive()
                    assert not chunk
            except (anyio.EndOfStream, anyio.ClosedResourceError):
                pass
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_invalid_auth_token_rejected_immediately(broker_paths: tuple[Path, Path]) -> None:
    """Verify that connections sending invalid token credentials are rejected."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    server = BrokerServer(
        port=0,
        token=token,
        metadata_path=meta_path,
        token_path=tok_path,
        auth_timeout=2.0,
    )
    await server.start()

    try:
        stream = await anyio.connect_tcp("127.0.0.1", server.bound_port)
        async with stream:
            # Send invalid token
            bad_auth = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "auth",
                        "params": {"token": "wrong_token"},
                    }
                ).encode("utf-8")
                + b"\n"
            )
            await stream.send(bad_auth)

            try:
                with anyio.fail_after(1.0):
                    chunk = await stream.receive()
                    assert not chunk
            except (anyio.EndOfStream, anyio.ClosedResourceError):
                pass
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_multi_client_concurrent_reads(broker_paths: tuple[Path, Path]) -> None:
    """Verify concurrent reads from multiple clients execute in parallel without blocking."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    server = BrokerServer(
        port=0,
        token=token,
        metadata_path=meta_path,
        token_path=tok_path,
    )
    await server.start()

    try:
        client_1 = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="client_1",
        )
        client_2 = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="client_2",
        )

        await client_1.connect()
        await client_2.connect()

        results_1: list[dict] = []
        results_2: list[dict] = []

        async def read_worker_1() -> None:
            for _ in range(5):
                res = await client_1.session_info()
                results_1.append(res)
                await anyio.sleep(0.01)

        async def read_worker_2() -> None:
            for _ in range(5):
                res = await client_2.ping()
                results_2.append(res)
                await anyio.sleep(0.01)

        # Run concurrent read workloads across both clients simultaneously
        async with anyio.create_task_group() as tg:
            tg.start_soon(read_worker_1)
            tg.start_soon(read_worker_2)

        assert len(results_1) == 5
        assert len(results_2) == 5
        assert all(r.get("sid") == 1 for r in results_1)
        assert all(r.get("pong") is True for r in results_2)

        await client_1.close()
        await client_2.close()
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_exclusive_write_lockout_and_rejection(broker_paths: tuple[Path, Path]) -> None:
    """Verify non-lease holders attempting writes are rejected with E_LEASE."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    device_state: dict[str, Any] = {"vol": 0.5}

    def direct_handler(op: str, args: dict[str, Any]) -> Any:
        if op == "set_vol":
            device_state["vol"] = args.get("val", 0.0)
            return {"set": True, "val": device_state["vol"]}
        if op == "get_vol":
            return device_state["vol"]
        return True

    embedded = EmbeddedBroker(direct_handler=direct_handler)
    server = BrokerServer(
        port=0,
        token=token,
        broker=embedded,
        metadata_path=meta_path,
        token_path=tok_path,
    )
    await server.start()

    try:
        client_writer = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="writer_client",
        )
        client_reader = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="reader_client",
        )

        await client_writer.connect()
        await client_reader.connect()

        # Step 1: Writer client acquires exclusive lease
        lease = await client_writer.lease_acquire(ttl=15.0, purpose="volume_change")
        assert lease["owner"] == "writer_client"
        assert lease["active"] is True

        # Step 2: Writer client executes mutating write successfully
        res = await client_writer.device_call("set_vol", {"val": 0.8})
        assert res["val"] == 0.8
        assert device_state["vol"] == 0.8

        # Step 3: Reader client (without lease) attempts mutating write -> rejected with E_LEASE
        with pytest.raises(BrokerError) as exc_info:
            await client_reader.device_call("set_vol", {"val": 0.2})

        err = exc_info.value
        assert err.code == "E_LEASE"
        assert err.details.get("owner") == "writer_client"
        assert err.details.get("remaining_ttl", 0) > 0

        # Non-mutating read from reader client succeeds without needing a lease
        vol = await client_reader.device_call("get_vol")
        assert vol == 0.8

        # Step 4: Writer releases lease
        rel = await client_writer.lease_release()
        assert rel.get("released") is True

        # Step 5: Reader client acquires lease and can now write
        await client_reader.lease_acquire(ttl=15.0)
        res2 = await client_reader.device_call("set_vol", {"val": 0.3})
        assert res2["val"] == 0.3
        assert device_state["vol"] == 0.3

        await client_writer.close()
        await client_reader.close()
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_abrupt_client_disconnect_revokes_lease(broker_paths: tuple[Path, Path]) -> None:
    """Verify abrupt client disconnection automatically revokes lease within TTL [BRK-10]."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    server = BrokerServer(
        port=0,
        token=token,
        metadata_path=meta_path,
        token_path=tok_path,
    )
    await server.start()

    try:
        client_A = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="client_A",
        )
        client_B = BrokerClient(
            port=server.bound_port,
            token=token,
            client_id="client_B",
        )

        await client_A.connect()
        await client_B.connect()

        # client_A acquires lease
        await client_A.lease_acquire(ttl=15.0)
        assert server.broker.lease_manager.current_owner == "client_A"

        # client_B is blocked
        with pytest.raises(BrokerError):
            await client_B.lease_acquire(ttl=15.0)

        # client_A abruptly disconnects (closes TCP stream)
        await client_A.close()

        # Allow server to process disconnect callback
        await anyio.sleep(0.05)

        # Lease held by client_A was immediately revoked upon disconnection!
        assert server.broker.lease_manager.current_owner is None

        # client_B can now acquire lease immediately without waiting 15s
        new_lease = await client_B.lease_acquire(ttl=15.0)
        assert new_lease["owner"] == "client_B"

        await client_B.close()
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_event_fan_out_to_multiple_subscribers(broker_paths: tuple[Path, Path]) -> None:
    """Verify event fan-out multiplexes notifications across connected client queues."""
    meta_path, tok_path = broker_paths
    token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    server = BrokerServer(
        port=0,
        token=token,
        metadata_path=meta_path,
        token_path=tok_path,
    )
    await server.start()

    try:
        events_1: list[dict] = []
        events_2: list[dict] = []

        async with (
            BrokerClient(port=server.bound_port, token=token, client_id="sub_client_1") as client_1,
            BrokerClient(port=server.bound_port, token=token, client_id="sub_client_2") as client_2,
        ):
            await client_1.device_subscribe(["transport"], callback=lambda t, d: events_1.append(d))
            await client_2.device_subscribe(["transport"], callback=lambda t, d: events_2.append(d))

            # Embedded broker publishes event to topic "transport"
            server.broker.publish_event("transport", {"state": "playing", "tempo": 128.0})

            # Allow fan-out distribution
            await anyio.sleep(0.05)

            # Both subscribers received the event
            assert len(events_1) == 1
            assert events_1[0]["state"] == "playing"
            assert len(events_2) == 1
            assert events_2[0]["state"] == "playing"
    finally:
        await server.stop()


def test_ensure_broker_recovers_stale_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify ensure_broker detects dead PID in broker.json and cleans it up [BRK-06]."""
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(tmp_path))

    meta_file = tmp_path / "broker.json"
    token_file = tmp_path / "broker.token"

    # Write stale metadata pointing to an invalid dead PID (e.g. 99999999)
    stale_meta = {
        "pid": 99999999,
        "port": 54321,
        "version": "1.0.0",
        "started": "2026-10-18T00:00:00Z",
    }
    meta_file.write_text(json.dumps(stale_meta), encoding="utf-8")
    token_file.write_text("dummy_token", encoding="utf-8")

    # Call ensure_broker with mock spawner that simulates starting broker
    def mock_popen(*args: Any, **kwargs: Any) -> None:
        new_meta = {
            "pid": 12345,
            "port": 54322,
            "version": "1.0.0",
            "started": "2026-10-18T01:00:00Z",
        }
        meta_file.write_text(json.dumps(new_meta), encoding="utf-8")

    async def mock_ping(host: str, port: int, token: str, timeout: float = 1.0) -> bool:
        return True

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr("studiobridge.broker.client.is_process_alive", lambda pid: pid == 12345)
    monkeypatch.setattr("studiobridge.broker.client._ping_port", mock_ping)

    host, port = ensure_broker(
        metadata_path=meta_file,
        token_path=token_file,
        timeout=1.0,
    )
    assert host == "127.0.0.1"
    assert port == 54322
