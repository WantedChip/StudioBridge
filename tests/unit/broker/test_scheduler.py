"""Unit tests for Broker Scheduler, Priority Queues, Round-Robin and Rate Limiting.

Verifies:
- Multi-tier priority ordering: CONTROL > READ > WRITE > BULK.
- Maximum client queue capacity of 256 requests per client.
- Fair round-robin scheduling across clients within the same priority class.
- Token bucket rate limiting (client <= 200 req/s, global <= 400 req/s)
  returning E_BUSY with retry_ms [BRK-12].
"""

from __future__ import annotations

import pytest

from studiobridge.broker.scheduler import (
    DEFAULT_CLIENT_RATE,
    DEFAULT_GLOBAL_RATE,
    Priority,
    RateLimiter,
    ScheduledRequest,
    Scheduler,
    classify_priority,
)
from studiobridge.core.errors import BrokerError


class FakeClock:
    """Deterministic controllable clock for scheduler and rate limit tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current: float = start

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_classify_priority() -> None:
    """Verify operation names map to appropriate priority classes."""
    assert classify_priority("panic") == Priority.CONTROL
    assert classify_priority("ping") == Priority.CONTROL
    assert classify_priority("broker.ping") == Priority.CONTROL
    assert classify_priority("broker.shutdown") == Priority.CONTROL

    assert classify_priority("get_volume") == Priority.READ
    assert classify_priority("read_tempo") == Priority.READ
    assert classify_priority("session.info") == Priority.READ
    assert classify_priority("broker.status") == Priority.READ
    assert classify_priority("capabilities.get") == Priority.READ

    assert classify_priority("set_volume") == Priority.WRITE
    assert classify_priority("call") == Priority.WRITE
    assert classify_priority("device.call") == Priority.WRITE

    assert classify_priority("batch") == Priority.BULK
    assert classify_priority("device.batch") == Priority.BULK
    assert classify_priority("scan_plugins") == Priority.BULK

    # Explicit override
    assert classify_priority("get_volume", explicit=Priority.CONTROL) == Priority.CONTROL
    assert classify_priority("call", explicit="bulk") == Priority.BULK


def test_priority_ordering() -> None:
    """Verify requests are dequeued strictly in priority order: CONTROL > READ > WRITE > BULK."""
    clock = FakeClock()
    scheduler = Scheduler(clock=clock)

    # Enqueue requests in inverted priority order
    req_bulk = ScheduledRequest("1", "client_1", Priority.BULK, "batch", created_at=clock())
    req_write = ScheduledRequest("2", "client_1", Priority.WRITE, "set_vol", created_at=clock())
    req_read = ScheduledRequest("3", "client_1", Priority.READ, "get_vol", created_at=clock())
    req_control = ScheduledRequest("4", "client_1", Priority.CONTROL, "panic", created_at=clock())

    scheduler.enqueue(req_bulk)
    scheduler.enqueue(req_write)
    scheduler.enqueue(req_read)
    scheduler.enqueue(req_control)

    assert scheduler.pending_count == 4

    # Dequeued order MUST be CONTROL, then READ, then WRITE, then BULK
    out_1 = scheduler.dequeue_nowait()
    assert out_1 is not None and out_1.priority == Priority.CONTROL and out_1.op == "panic"

    out_2 = scheduler.dequeue_nowait()
    assert out_2 is not None and out_2.priority == Priority.READ and out_2.op == "get_vol"

    out_3 = scheduler.dequeue_nowait()
    assert out_3 is not None and out_3.priority == Priority.WRITE and out_3.op == "set_vol"

    out_4 = scheduler.dequeue_nowait()
    assert out_4 is not None and out_4.priority == Priority.BULK and out_4.op == "batch"

    assert scheduler.dequeue_nowait() is None
    assert scheduler.pending_count == 0


def test_fair_round_robin_within_priority_class() -> None:
    """Verify fair round-robin scheduling among multiple clients within a single priority class."""
    clock = FakeClock()
    scheduler = Scheduler(clock=clock)

    # 3 clients each enqueue 3 requests of Priority.READ
    for i in range(3):
        scheduler.enqueue(
            ScheduledRequest(f"A{i}", "client_A", Priority.READ, "get_A", created_at=clock())
        )
        scheduler.enqueue(
            ScheduledRequest(f"B{i}", "client_B", Priority.READ, "get_B", created_at=clock())
        )
        scheduler.enqueue(
            ScheduledRequest(f"C{i}", "client_C", Priority.READ, "get_C", created_at=clock())
        )

    assert scheduler.pending_count == 9
    assert scheduler.client_pending_count("client_A") == 3
    assert scheduler.client_pending_count("client_B") == 3
    assert scheduler.client_pending_count("client_C") == 3

    # Dequeue all 9 requests: expected interleaved order is A, B, C, A, B, C, A, B, C
    expected_clients = [
        "client_A",
        "client_B",
        "client_C",
        "client_A",
        "client_B",
        "client_C",
        "client_A",
        "client_B",
        "client_C",
    ]

    actual_clients = []
    for _ in range(9):
        req = scheduler.dequeue_nowait()
        assert req is not None
        actual_clients.append(req.client_id)

    assert actual_clients == expected_clients
    assert scheduler.pending_count == 0


def test_max_client_queue_capacity() -> None:
    """Verify max client queue capacity (256 requests); 257th request raises E_BUSY."""
    clock = FakeClock()
    scheduler = Scheduler(max_client_queue=256, clock=clock)

    # Enqueue 256 requests for client_1
    for i in range(256):
        scheduler.enqueue(
            ScheduledRequest(str(i), "client_1", Priority.READ, "read", created_at=clock())
        )

    assert scheduler.client_pending_count("client_1") == 256

    # 257th request for client_1 MUST fail with E_BUSY
    with pytest.raises(BrokerError) as exc_info:
        scheduler.enqueue(
            ScheduledRequest("overflow", "client_1", Priority.READ, "read", created_at=clock())
        )

    err = exc_info.value
    assert err.code == "E_BUSY"
    assert err.details.get("capacity") == 256
    assert err.details.get("client_id") == "client_1"

    # Other clients (client_2) can still enqueue requests
    scheduler.enqueue(
        ScheduledRequest("c2_1", "client_2", Priority.READ, "read", created_at=clock())
    )
    assert scheduler.client_pending_count("client_2") == 1


def test_rate_limiter_client_and_global_limits() -> None:
    """Verify per-client and global rate limiting returning E_BUSY with retry_ms [BRK-12]."""
    clock = FakeClock()
    limiter = RateLimiter(
        client_rate=DEFAULT_CLIENT_RATE,  # 200 req/s
        client_capacity=200.0,
        global_rate=DEFAULT_GLOBAL_RATE,  # 400 req/s
        global_capacity=400.0,
        clock=clock,
    )

    # Exhaust client_1's 200 tokens
    for _ in range(200):
        limiter.check("client_1")

    # 201st request from client_1 in same second fails with E_BUSY and retry_ms
    with pytest.raises(BrokerError) as exc_info:
        limiter.check("client_1")

    err = exc_info.value
    assert err.code == "E_BUSY"
    assert "retry_ms" in err.details
    assert err.details["retry_ms"] > 0
    assert err.details["client_id"] == "client_1"

    # Meanwhile client_2 can still consume up to 200 tokens (global has 200 left)
    for _ in range(200):
        limiter.check("client_2")

    # Now global bucket (total 400) is also exhausted!
    # Even a fresh client_3 will fail due to global limit
    with pytest.raises(BrokerError) as exc_info_global:
        limiter.check("client_3")

    err_global = exc_info_global.value
    assert err_global.code == "E_BUSY"
    assert err_global.details["retry_ms"] > 0

    # Advance fake clock by 0.5s (200 global tokens replenish, 100 client tokens replenish)
    clock.advance(0.5)

    # client_1 can now make requests again
    limiter.check("client_1")
    limiter.check("client_3")


def test_cancel_client_purges_all_queues() -> None:
    """Verify cancel_client purges all pending requests across all priority classes for a client."""
    clock = FakeClock()
    scheduler = Scheduler(clock=clock)

    scheduler.enqueue(ScheduledRequest("1", "client_A", Priority.CONTROL, "ping"))
    scheduler.enqueue(ScheduledRequest("2", "client_A", Priority.READ, "get"))
    scheduler.enqueue(ScheduledRequest("3", "client_B", Priority.READ, "get"))
    scheduler.enqueue(ScheduledRequest("4", "client_A", Priority.WRITE, "set"))

    assert scheduler.pending_count == 4
    assert scheduler.client_pending_count("client_A") == 3

    purged = scheduler.cancel_client("client_A")
    assert len(purged) == 3
    assert scheduler.pending_count == 1
    assert scheduler.client_pending_count("client_A") == 0
    assert scheduler.client_pending_count("client_B") == 1

    remaining = scheduler.dequeue_nowait()
    assert remaining is not None and remaining.client_id == "client_B"
    assert scheduler.dequeue_nowait() is None


@pytest.mark.anyio
async def test_async_dequeue_waits_for_enqueue() -> None:
    """Verify asynchronous dequeue waits until an item is enqueued."""
    scheduler = Scheduler()

    import anyio

    dequeued_items: list[ScheduledRequest] = []

    async def _consumer() -> None:
        req = await scheduler.dequeue()
        dequeued_items.append(req)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_consumer)
        await anyio.sleep(0.02)
        assert len(dequeued_items) == 0

        scheduler.enqueue(ScheduledRequest("1", "client_1", Priority.READ, "get_tempo"))
        await anyio.sleep(0.02)
        assert len(dequeued_items) == 1
        assert dequeued_items[0].op == "get_tempo"
