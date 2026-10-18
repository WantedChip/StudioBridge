"""Single-writer lease management, auto-renewal, and ownership enforcement.

Implements single-writer lease arbitration per [BRK-10] and spec 04_l0b_ports_broker.md §8.4.
Enforces that state mutations require an active lease, auto-renews leases while requests
are in-flight, and automatically revokes leases on client disconnection or TTL expiry.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from studiobridge.core.errors import BrokerError

DEFAULT_LEASE_TTL: float = 15.0  # seconds per [BRK-10]


@dataclass(frozen=True, slots=True)
class LeaseInfo:
    """Snapshot metadata for an active writer lease."""

    owner: str
    acquired_at: float
    expires_at: float
    ttl: float
    purpose: str = ""

    def is_expired(self, now: float) -> bool:
        """Return True if lease has expired at timestamp now."""
        return now >= self.expires_at

    def remaining_ttl(self, now: float) -> float:
        """Return remaining time-to-live in seconds, minimum 0.0."""
        return max(0.0, self.expires_at - now)

    def to_dict(self, now: float | None = None) -> dict[str, Any]:
        """Serialize lease state to a dictionary."""
        current_time = time.monotonic() if now is None else now
        return {
            "owner": self.owner,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "ttl": self.ttl,
            "remaining_ttl": round(self.remaining_ttl(current_time), 3),
            "purpose": self.purpose,
            "is_expired": self.is_expired(current_time),
            "active": not self.is_expired(current_time),
        }


class LeaseManager:
    """Manages the exclusive single-writer lease for FL Studio state mutations.

    Rules:
    - Exactly one holder at any time per FL session.
    - Default TTL 15s; auto-renews while holder requests are in flight [BRK-10].
    - Reads do not require a lease; writes without a lease raise E_LEASE.
    - Revoked immediately when owner disconnects or on explicit release.
    """

    def __init__(
        self,
        default_ttl: float = DEFAULT_LEASE_TTL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.default_ttl: float = default_ttl
        self.clock: Callable[[], float] = clock
        self._current_lease: LeaseInfo | None = None
        self._in_flight_count: int = 0

    @property
    def current_lease(self) -> LeaseInfo | None:
        """Return active lease, or None if no lease or expired (with 0 in-flight)."""
        now = self.clock()
        if self._current_lease is None:
            return None
        if self._is_expired(now):
            return None
        return self._current_lease

    @property
    def current_owner(self) -> str | None:
        """Owner ID of currently active lease holder, or None."""
        lease = self.current_lease
        return lease.owner if lease is not None else None

    def _is_expired(self, now: float) -> bool:
        """Check if active lease is expired, respecting in-flight hold."""
        if self._current_lease is None:
            return True
        # Holder requests in flight auto-protect the lease from expiring mid-execution
        if self._in_flight_count > 0:
            return False
        return now >= self._current_lease.expires_at

    def acquire(
        self,
        owner: str,
        ttl: float | None = None,
        purpose: str = "",
    ) -> LeaseInfo:
        """Acquire the exclusive writer lease for owner.

        Args:
            owner: Unique identifier for the client requesting the lease.
            ttl: Lease duration in seconds (defaults to default_ttl).
            purpose: Optional human-readable purpose description.

        Returns:
            Newly acquired or renewed LeaseInfo.

        Raises:
            BrokerError: With code 'E_LEASE' if another client holds an active lease.
        """
        now = self.clock()
        lease_ttl = ttl if ttl is not None and ttl > 0 else self.default_ttl

        if (
            self._current_lease is not None
            and not self._is_expired(now)
            and self._current_lease.owner != owner
        ):
            rem_ttl = round(self._current_lease.remaining_ttl(now), 3)
            raise BrokerError(
                f"Lease already held by '{self._current_lease.owner}'",
                code="E_LEASE",
                retryable=True,
                details={
                    "owner": self._current_lease.owner,
                    "remaining_ttl": rem_ttl,
                    "purpose": self._current_lease.purpose,
                },
            )

        # Grant or renew lease to owner
        acquired_time = (
            self._current_lease.acquired_at
            if self._current_lease and self._current_lease.owner == owner
            else now
        )
        self._current_lease = LeaseInfo(
            owner=owner,
            acquired_at=acquired_time,
            expires_at=now + lease_ttl,
            ttl=lease_ttl,
            purpose=purpose or (self._current_lease.purpose if self._current_lease else ""),
        )
        return self._current_lease

    def renew(self, owner: str, ttl: float | None = None) -> LeaseInfo:
        """Extend the TTL of the currently held lease.

        Raises:
            BrokerError: With code 'E_LEASE' if owner is not the current active holder.
        """
        now = self.clock()
        if (
            self._current_lease is None
            or self._is_expired(now)
            or self._current_lease.owner != owner
        ):
            active_owner = (
                self._current_lease.owner
                if (self._current_lease and not self._is_expired(now))
                else None
            )
            rem_ttl = (
                round(self._current_lease.remaining_ttl(now), 3) if self._current_lease else 0.0
            )
            raise BrokerError(
                "Cannot renew lease: not currently lease holder or lease expired",
                code="E_LEASE",
                retryable=True,
                details={"owner": active_owner, "remaining_ttl": rem_ttl},
            )

        renew_ttl = ttl if ttl is not None and ttl > 0 else self._current_lease.ttl
        self._current_lease = LeaseInfo(
            owner=owner,
            acquired_at=self._current_lease.acquired_at,
            expires_at=now + renew_ttl,
            ttl=renew_ttl,
            purpose=self._current_lease.purpose,
        )
        return self._current_lease

    def release(self, owner: str) -> bool:
        """Explicitly release the lease if held by owner.

        Returns:
            True if lease was released, False if owner did not hold the lease.
        """
        if self._current_lease is not None and self._current_lease.owner == owner:
            self._current_lease = None
            self._in_flight_count = 0
            return True
        return False

    def revoke_owner(self, owner: str) -> bool:
        """Revoke any lease held by owner, e.g. on client disconnection [BRK-10]."""
        return self.release(owner)

    def begin_request(self, client_id: str) -> None:
        """Track in-flight request start, automatically renewing lease if client is holder."""
        if self._current_lease is not None and self._current_lease.owner == client_id:
            self._in_flight_count += 1
            now = self.clock()
            # Auto-renew while holder requests are in flight [BRK-10]
            self._current_lease = LeaseInfo(
                owner=client_id,
                acquired_at=self._current_lease.acquired_at,
                expires_at=now + self._current_lease.ttl,
                ttl=self._current_lease.ttl,
                purpose=self._current_lease.purpose,
            )

    def end_request(self, client_id: str) -> None:
        """Track in-flight request completion, granting full TTL post-execution."""
        if self._current_lease is not None and self._current_lease.owner == client_id:
            self._in_flight_count = max(0, self._in_flight_count - 1)
            now = self.clock()
            self._current_lease = LeaseInfo(
                owner=client_id,
                acquired_at=self._current_lease.acquired_at,
                expires_at=now + self._current_lease.ttl,
                ttl=self._current_lease.ttl,
                purpose=self._current_lease.purpose,
            )

    def validate_write(self, client_id: str) -> None:
        """Ensure client_id holds an active writer lease.

        Raises:
            BrokerError: With code 'E_LEASE' carrying current owner and remaining TTL.
        """
        now = self.clock()
        if self._current_lease is None or self._is_expired(now):
            # Check if this owner has an in-flight request keeping the lease alive
            if (
                self._current_lease is not None
                and self._current_lease.owner == client_id
                and self._in_flight_count > 0
            ):
                return

            active_owner = (
                self._current_lease.owner
                if (self._current_lease and not self._is_expired(now))
                else None
            )
            rem_ttl = (
                round(self._current_lease.remaining_ttl(now), 3) if self._current_lease else 0.0
            )
            raise BrokerError(
                "Write operation rejected: client does not hold writer lease",
                code="E_LEASE",
                retryable=True,
                details={"owner": active_owner, "remaining_ttl": rem_ttl},
            )

        if self._current_lease.owner != client_id:
            rem_ttl = round(self._current_lease.remaining_ttl(now), 3)
            raise BrokerError(
                f"Write operation rejected: lease held by '{self._current_lease.owner}'",
                code="E_LEASE",
                retryable=True,
                details={
                    "owner": self._current_lease.owner,
                    "remaining_ttl": rem_ttl,
                    "purpose": self._current_lease.purpose,
                },
            )

    def get_state(self) -> dict[str, Any]:
        """Return snapshot dictionary of current lease status."""
        now = self.clock()
        if self._current_lease is None or self._is_expired(now):
            return {
                "active": False,
                "owner": None,
                "remaining_ttl": 0.0,
                "purpose": "",
            }
        return {
            "active": True,
            "owner": self._current_lease.owner,
            "remaining_ttl": round(self._current_lease.remaining_ttl(now), 3),
            "purpose": self._current_lease.purpose,
            "in_flight": self._in_flight_count,
        }
