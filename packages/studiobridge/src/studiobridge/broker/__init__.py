"""Broker daemon, scheduling, lease management, and event routing.

Implements L0.B Broker layer per spec 04_l0b_ports_broker.md §8:
- Prioritized request queues and rate limiting (scheduler.py)
- Single-writer lease management and auto-renewal (lease.py)
- In-process broker facade for direct SDK execution (embedded.py)
- Local TCP daemon, token auth, and NDJSON framing (server.py)
- Async client and auto-start process supervisor (client.py)
"""

from __future__ import annotations

from studiobridge.broker.client import BrokerClient, ensure_broker, is_process_alive
from studiobridge.broker.embedded import EmbeddedBroker
from studiobridge.broker.lease import DEFAULT_LEASE_TTL, LeaseInfo, LeaseManager
from studiobridge.broker.scheduler import (
    DEFAULT_CLIENT_RATE,
    DEFAULT_GLOBAL_RATE,
    DEFAULT_MAX_CLIENT_QUEUE,
    Priority,
    RateLimiter,
    ScheduledRequest,
    Scheduler,
    TokenBucket,
    classify_priority,
)
from studiobridge.broker.server import BrokerServer, ensure_broker_token

__all__ = [
    "DEFAULT_CLIENT_RATE",
    "DEFAULT_GLOBAL_RATE",
    "DEFAULT_LEASE_TTL",
    "DEFAULT_MAX_CLIENT_QUEUE",
    "BrokerClient",
    "BrokerServer",
    "EmbeddedBroker",
    "LeaseInfo",
    "LeaseManager",
    "Priority",
    "RateLimiter",
    "ScheduledRequest",
    "Scheduler",
    "TokenBucket",
    "classify_priority",
    "ensure_broker",
    "ensure_broker_token",
    "is_process_alive",
]
