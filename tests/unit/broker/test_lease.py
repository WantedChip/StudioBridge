"""Unit tests for Single-Writer Lease Manager and Ownership Arbitration.

Verifies:
- Lease acquisition (owner, ttl=15s, purpose).
- Conflicting acquisition rejection with E_LEASE carrying current owner and remaining TTL.
- Write validation rejecting non-holders with E_LEASE.
- Auto-renewal while holder requests in flight [BRK-10].
- Deterministic expiration using fake clock.
- Clean release and disconnect revocation [BRK-10].
"""

from __future__ import annotations

import pytest

from studiobridge.broker.lease import LeaseManager
from studiobridge.core.errors import BrokerError


class FakeClock:
    """Controllable monotonic clock for deterministic time manipulation."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current: float = start

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_lease_acquisition_and_state() -> None:
    """Verify standard lease acquisition, TTL, and state inspection."""
    clock = FakeClock(100.0)
    manager = LeaseManager(default_ttl=15.0, clock=clock)

    assert manager.current_lease is None
    assert manager.current_owner is None

    lease = manager.acquire("client_A", ttl=15.0, purpose="recording")
    assert lease.owner == "client_A"
    assert lease.ttl == 15.0
    assert lease.acquired_at == 100.0
    assert lease.expires_at == 115.0
    assert lease.purpose == "recording"
    assert not lease.is_expired(100.0)
    assert lease.remaining_ttl(100.0) == 15.0

    state = manager.get_state()
    assert state["active"] is True
    assert state["owner"] == "client_A"
    assert state["remaining_ttl"] == 15.0
    assert state["purpose"] == "recording"


def test_conflicting_lease_acquisition_rejected_with_e_lease() -> None:
    """Verify conflicting acquisition while held by another owner raises E_LEASE."""
    clock = FakeClock(100.0)
    manager = LeaseManager(clock=clock)

    manager.acquire("client_A", ttl=15.0, purpose="track_rename")
    clock.advance(5.0)  # 10s remaining

    # client_B attempts to acquire while client_A holds active lease
    with pytest.raises(BrokerError) as exc_info:
        manager.acquire("client_B", ttl=15.0)

    err = exc_info.value
    assert err.code == "E_LEASE"
    assert err.details["owner"] == "client_A"
    assert abs(err.details["remaining_ttl"] - 10.0) < 0.01
    assert err.details["purpose"] == "track_rename"


def test_validate_write_permits_holder_and_rejects_others() -> None:
    """Verify validate_write allows holder and raises E_LEASE for unleased clients."""
    clock = FakeClock(100.0)
    manager = LeaseManager(clock=clock)

    # 1. No lease held at all
    with pytest.raises(BrokerError) as exc_none:
        manager.validate_write("client_A")
    assert exc_none.value.code == "E_LEASE"
    assert exc_none.value.details["owner"] is None

    # 2. Acquire lease for client_A
    manager.acquire("client_A", ttl=15.0)

    # client_A write validation MUST succeed
    manager.validate_write("client_A")

    # client_B write validation MUST fail with E_LEASE
    with pytest.raises(BrokerError) as exc_other:
        manager.validate_write("client_B")
    assert exc_other.value.code == "E_LEASE"
    assert exc_other.value.details["owner"] == "client_A"
    assert exc_other.value.details["remaining_ttl"] > 0


def test_lease_renewal() -> None:
    """Verify explicit lease renewal extends expiration time."""
    clock = FakeClock(100.0)
    manager = LeaseManager(clock=clock)

    manager.acquire("client_A", ttl=15.0)
    clock.advance(10.0)  # expires_at was 115.0, current time 110.0 (5s left)

    # Renew lease with fresh 15s
    renewed = manager.renew("client_A", ttl=15.0)
    assert renewed.expires_at == 125.0  # 110 + 15
    assert renewed.remaining_ttl(clock()) == 15.0

    # Non-holder cannot renew
    with pytest.raises(BrokerError) as exc_renew:
        manager.renew("client_B", ttl=15.0)
    assert exc_renew.value.code == "E_LEASE"


def test_auto_renewal_while_in_flight_requests() -> None:
    """Verify auto-renewal while holder requests are in flight per [BRK-10]."""
    clock = FakeClock(100.0)
    manager = LeaseManager(clock=clock)

    manager.acquire("client_A", ttl=15.0)  # expires at 115.0

    # Start long-running in-flight request for client_A
    manager.begin_request("client_A")

    # Advance clock past original 15s expiration (e.g. 20s forward to 120.0)
    clock.advance(20.0)

    # Because a request is in flight, lease is NOT expired!
    assert manager.current_owner == "client_A"
    manager.validate_write("client_A")

    # Complete request
    manager.end_request("client_A")

    # Lease was refreshed to have fresh 15s TTL from completion time (120 + 15 = 135)
    assert manager.current_lease is not None
    assert manager.current_lease.expires_at == 135.0
    assert manager.current_lease.remaining_ttl(clock()) == 15.0


def test_expiration_with_fake_clock() -> None:
    """Verify deterministic expiration when clock advances past TTL with no in-flight requests."""
    clock = FakeClock(100.0)
    manager = LeaseManager(default_ttl=15.0, clock=clock)

    manager.acquire("client_A", ttl=15.0)
    assert manager.current_owner == "client_A"

    # Advance past 15s
    clock.advance(15.1)

    # Lease has expired
    assert manager.current_lease is None
    assert manager.current_owner is None

    # Write attempt by client_A is rejected
    with pytest.raises(BrokerError) as exc_info:
        manager.validate_write("client_A")
    assert exc_info.value.code == "E_LEASE"

    # Another client can now acquire the lease immediately without error
    new_lease = manager.acquire("client_B", ttl=15.0)
    assert new_lease.owner == "client_B"
    assert manager.current_owner == "client_B"


def test_release_and_revoke_owner() -> None:
    """Verify explicit release and disconnect revocation."""
    clock = FakeClock(100.0)
    manager = LeaseManager(clock=clock)

    # 1. Release
    manager.acquire("client_A", ttl=15.0)
    assert manager.release("client_A") is True
    assert manager.current_owner is None
    assert manager.release("client_A") is False

    # 2. Revoke on disconnect [BRK-10]
    manager.acquire("client_B", ttl=15.0)
    assert manager.current_owner == "client_B"
    manager.revoke_owner("client_B")
    assert manager.current_owner is None
