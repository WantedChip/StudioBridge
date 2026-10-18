"""Broker request scheduler, priority queues, round-robin dispatch, and rate limiting.

Implements multi-tier priority scheduling (control > read > write > bulk),
client queue limits (256 requests per client), fair round-robin scheduling,
and token-bucket rate limiting per [BRK-12] and spec 04_l0b_ports_broker.md §8.4.
"""

from __future__ import annotations

import collections
import enum
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anyio

from studiobridge.core.errors import BrokerError

DEFAULT_CLIENT_RATE: float = 200.0  # requests per second
DEFAULT_GLOBAL_RATE: float = 400.0  # requests per second
DEFAULT_MAX_CLIENT_QUEUE: int = 256


class Priority(str, enum.Enum):
    """Scheduling priority classes in descending precedence."""

    CONTROL = "control"  # panic, ping, immediate broker management
    READ = "read"  # state queries, getters, parameter inspections
    WRITE = "write"  # state mutations, setters, command executions
    BULK = "bulk"  # batch operations, dumps, large transfers

    @property
    def rank(self) -> int:
        """Numerical rank for sorting (lower is higher priority)."""
        ranks = {
            Priority.CONTROL: 0,
            Priority.READ: 1,
            Priority.WRITE: 2,
            Priority.BULK: 3,
        }
        return ranks[self]


PRIORITY_ORDER: tuple[Priority, ...] = (
    Priority.CONTROL,
    Priority.READ,
    Priority.WRITE,
    Priority.BULK,
)


def classify_priority(op: str, explicit: str | Priority | None = None) -> Priority:
    """Classify the priority of an operation.

    If an explicit priority is passed and recognized, it is returned.
    Otherwise, heuristics classify panic/ping as CONTROL, reads/queries as READ,
    mutations/calls as WRITE, and batches/scans as BULK.
    """
    if explicit is not None:
        if isinstance(explicit, Priority):
            return explicit
        try:
            return Priority(str(explicit).lower())
        except ValueError:
            pass

    op_lower = op.lower()
    if op_lower in {"panic", "ping", "control", "broker.ping", "broker.shutdown"}:
        return Priority.CONTROL

    if op_lower.startswith(
        ("get", "read", "is", "list", "probe", "info", "find", "check")
    ) or op_lower in {"session.info", "broker.status", "capabilities.get"}:
        return Priority.READ

    if op_lower.startswith(("batch", "bulk", "dump", "scan", "sync")) or op_lower == "device.batch":
        return Priority.BULK

    return Priority.WRITE


@dataclass(slots=True)
class ScheduledRequest:
    """A scheduled client request awaiting execution."""

    request_id: str
    client_id: str
    priority: Priority
    op: str
    args: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    future_event: anyio.Event = field(default_factory=anyio.Event)
    result: Any = None
    error: Exception | None = None

    def set_result(self, result: Any) -> None:
        """Mark request complete with a result value and unblock awaiter."""
        self.result = result
        self.future_event.set()

    def set_error(self, error: Exception) -> None:
        """Mark request failed with an exception and unblock awaiter."""
        self.error = error
        self.future_event.set()


class TokenBucket:
    """Thread-safe token bucket rate limiter for fractional-second intervals."""

    def __init__(
        self,
        rate: float,
        capacity: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate: float = rate
        self.capacity: float = capacity
        self.tokens: float = capacity
        self.clock: Callable[[], float] = clock
        self.last_update: float = clock()

    def can_acquire(self, cost: float = 1.0) -> tuple[bool, float]:
        """Check if tokens can be acquired without mutating bucket state.

        Returns:
            (True, 0.0) if tokens are available.
            (False, retry_ms) if limit would be exceeded.
        """
        now = self.clock()
        elapsed = max(0.0, now - self.last_update)
        current_tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if current_tokens >= cost:
            return True, 0.0

        missing = cost - current_tokens
        wait_seconds = missing / self.rate
        retry_ms = max(1.0, wait_seconds * 1000.0)
        return False, retry_ms

    def consume(self, cost: float = 1.0) -> None:
        """Replenish tokens up to now and deduct cost."""
        now = self.clock()
        elapsed = max(0.0, now - self.last_update)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        self.tokens -= cost

    def try_acquire(self, cost: float = 1.0) -> tuple[bool, float]:
        """Attempt to acquire tokens immediately mutating state."""
        ok, retry_ms = self.can_acquire(cost)
        if ok:
            self.consume(cost)
            return True, 0.0
        return False, retry_ms


class RateLimiter:
    """Enforces per-client and global rate limits per [BRK-12].

    Defaults: per-client <= 200 req/s, global <= 400 req/s.
    Exceeding yields E_BUSY with retry_ms detail.
    """

    def __init__(
        self,
        client_rate: float = DEFAULT_CLIENT_RATE,
        client_capacity: float = DEFAULT_CLIENT_RATE,
        global_rate: float = DEFAULT_GLOBAL_RATE,
        global_capacity: float = DEFAULT_GLOBAL_RATE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client_rate = client_rate
        self.client_capacity = client_capacity
        self.global_rate = global_rate
        self.global_capacity = global_capacity
        self.clock = clock

        self._global_bucket = TokenBucket(global_rate, global_capacity, clock=clock)
        self._client_buckets: dict[str, TokenBucket] = {}

    def _get_client_bucket(self, client_id: str) -> TokenBucket:
        if client_id not in self._client_buckets:
            self._client_buckets[client_id] = TokenBucket(
                self.client_rate, self.client_capacity, clock=self.clock
            )
        return self._client_buckets[client_id]

    def check(self, client_id: str) -> None:
        """Check rate limits for a request from client_id.

        Raises:
            BrokerError: With code 'E_BUSY' and 'retry_ms' in details if limit exceeded.
        """
        # Test both buckets before deducting tokens
        g_ok, g_wait = self._global_bucket.can_acquire(1.0)
        c_bucket = self._get_client_bucket(client_id)
        c_ok, c_wait = c_bucket.can_acquire(1.0)

        if not g_ok or not c_ok:
            retry_ms = int(max(g_wait, c_wait) + 0.999)
            raise BrokerError(
                f"Rate limit exceeded. Retry after {retry_ms}ms.",
                code="E_BUSY",
                retryable=True,
                details={"retry_ms": retry_ms, "client_id": client_id},
            )

        # Both passed: atomically consume from both buckets
        self._global_bucket.consume(1.0)
        c_bucket.consume(1.0)

    def remove_client(self, client_id: str) -> None:
        """Remove cached bucket for disconnected client."""
        self._client_buckets.pop(client_id, None)


class Scheduler:
    """Priority request scheduler with fair round-robin scheduling within priority classes.

    Enforces:
    1. Strict priority ordering: CONTROL > READ > WRITE > BULK.
    2. Fair round-robin across clients within the same priority class.
    3. Client queue capacity (max 256 requests per client).
    """

    def __init__(
        self,
        max_client_queue: int = DEFAULT_MAX_CLIENT_QUEUE,
        rate_limiter: RateLimiter | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_client_queue = max_client_queue
        self.rate_limiter = rate_limiter
        self.clock = clock

        # Priority -> {client_id: deque[ScheduledRequest]}
        self._queues: dict[Priority, dict[str, collections.deque[ScheduledRequest]]] = {
            p: collections.defaultdict(collections.deque) for p in PRIORITY_ORDER
        }
        # Priority -> deque of active client_ids for fair round-robin rotation
        self._active_clients: dict[Priority, collections.deque[str]] = {
            p: collections.deque() for p in PRIORITY_ORDER
        }
        # client_id -> total active request count across all priorities
        self._client_counts: collections.defaultdict[str, int] = collections.defaultdict(int)
        self._total_count: int = 0
        self._has_items_event: anyio.Event = anyio.Event()

    @property
    def pending_count(self) -> int:
        """Total number of requests currently pending across all queues."""
        return self._total_count

    def client_pending_count(self, client_id: str) -> int:
        """Number of requests pending for a specific client."""
        return self._client_counts.get(client_id, 0)

    def enqueue(self, request: ScheduledRequest) -> None:
        """Enqueue a request into its priority class queue.

        Raises:
            BrokerError: If client queue capacity is exceeded (code 'E_BUSY')
                         or rate limits are exceeded (code 'E_BUSY').
        """
        if self.rate_limiter is not None:
            self.rate_limiter.check(request.client_id)

        current_client_count = self._client_counts[request.client_id]
        if current_client_count >= self.max_client_queue:
            raise BrokerError(
                f"Client queue capacity of {self.max_client_queue} requests exceeded",
                code="E_BUSY",
                retryable=True,
                details={
                    "capacity": self.max_client_queue,
                    "current": current_client_count,
                    "client_id": request.client_id,
                },
            )

        priority = request.priority
        client_queue = self._queues[priority][request.client_id]
        if not client_queue:
            # Client was not active in this priority class; register for round-robin
            self._active_clients[priority].append(request.client_id)

        client_queue.append(request)
        self._client_counts[request.client_id] += 1
        self._total_count += 1
        self._has_items_event.set()

    def dequeue_nowait(self) -> ScheduledRequest | None:
        """Non-blocking dequeue of the next highest-priority request.

        Selects the highest non-empty priority class, and rotates active clients
        fairly in round-robin fashion.
        """
        for priority in PRIORITY_ORDER:
            active_clients = self._active_clients[priority]
            while active_clients:
                client_id = active_clients.popleft()
                client_queue = self._queues[priority].get(client_id)
                if not client_queue:
                    continue

                request = client_queue.popleft()
                self._client_counts[client_id] = max(0, self._client_counts[client_id] - 1)
                self._total_count = max(0, self._total_count - 1)

                if client_queue:
                    # Client still has requests in this priority tier; place at back of RR queue
                    active_clients.append(client_id)

                if self._total_count == 0:
                    self._has_items_event = anyio.Event()

                return request

        return None

    async def dequeue(self) -> ScheduledRequest:
        """Asynchronously dequeue the next highest-priority request, waiting if empty."""
        while True:
            req = self.dequeue_nowait()
            if req is not None:
                return req
            await self._has_items_event.wait()

    def cancel_client(self, client_id: str) -> list[ScheduledRequest]:
        """Cancel and purge all queued requests for client_id.

        Returns:
            List of purged ScheduledRequest objects.
        """
        purged: list[ScheduledRequest] = []
        for priority in PRIORITY_ORDER:
            client_queue = self._queues[priority].pop(client_id, None)
            if client_queue:
                while client_queue:
                    req = client_queue.popleft()
                    purged.append(req)
                    self._total_count = max(0, self._total_count - 1)

            # Clean client_id from active round-robin deque
            active_clients = self._active_clients[priority]
            if client_id in active_clients:
                self._active_clients[priority] = collections.deque(
                    c for c in active_clients if c != client_id
                )

        self._client_counts.pop(client_id, None)
        if self.rate_limiter is not None:
            self.rate_limiter.remove_client(client_id)

        if self._total_count == 0:
            self._has_items_event = anyio.Event()

        return purged
