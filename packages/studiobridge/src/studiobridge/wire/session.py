"""Session state, sequence tracking, fingerprint validation, and idempotency cache.

Implements session lifecycle management, fingerprint guards (V1-A1), precondition
evaluation (V1-A2), and the 64-entry idempotency cache with [WIRE-20], [WIRE-31], and [WIRE-32].
"""

from __future__ import annotations

import math
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from studiobridge.core.errors import PreconditionError, ProtocolError

if TYPE_CHECKING:
    from studiobridge.wire.envelope import RequestEnvelope, ResponseEnvelope

# Maximum capacity for idempotency response cache per [WIRE-20]
MAX_IDEMPOTENCY_CACHE_SIZE: int = 64

# Maximum 14-bit session ID value (0..16383)
MAX_SID_VALUE: int = 0x3FFF

# Maximum 21-bit message ID value (0..2097151)
MAX_MID_VALUE: int = 0x1FFFFF

# Operations known to mutate FL Studio state
MUTATING_OPERATIONS: frozenset[str] = frozenset({"call", "batch", "txn", "panic", "exec"})


def is_mutating_operation(op: str) -> bool:
    """Check if an operation name modifies state by default."""
    return op in MUTATING_OPERATIONS


def evaluate_precondition(expect: dict[str, Any] | None, current_value: Any) -> None:
    """Evaluate opts.expect precondition guard with V1-A2.

    Supported comparison modes in expect dictionary:
    - 'eq': Expected target value.
    - 'tol': Numeric tolerance float when comparing numbers (abs(actual - expected) <= tol).
    - 'ne': Must not equal this value.

    Args:
        expect: Precondition specification dictionary, e.g. {"fn": "...", "eq": 0.8, "tol": 0.005}.
        current_value: The freshly re-read value from FL Studio state.

    Raises:
        PreconditionError: If current_value fails the precondition guard (code E_PRECONDITION).
    """
    if not expect:
        return

    fn = expect.get("fn", "<unknown>")

    # Check 'eq' expectation
    if "eq" in expect:
        expected = expect["eq"]
        tol = expect.get("tol")
        if tol is not None:
            try:
                curr_f = float(current_value)
                exp_f = float(expected)
                tol_f = float(tol)
                if not math.isclose(curr_f, exp_f, abs_tol=tol_f):
                    raise PreconditionError(
                        f"Precondition guard failed for {fn}: expected {expected} (+/- {tol}), "
                        f"current value is {current_value}",
                        code="E_PRECONDITION",
                        details={
                            "fn": fn,
                            "expected": expected,
                            "actual": current_value,
                            "tol": tol,
                        },
                    )
            except (ValueError, TypeError) as exc:
                if not isinstance(exc, PreconditionError):
                    msg = (
                        f"Precondition guard failed for {fn}: "
                        f"type error comparing {current_value!r} with {expected!r} (tol={tol})"
                    )
                    raise PreconditionError(
                        msg,
                        code="E_PRECONDITION",
                        details={"fn": fn, "expected": expected, "actual": current_value},
                    ) from exc
                raise
        else:
            if current_value != expected:
                raise PreconditionError(
                    f"Precondition guard failed for {fn}: expected {expected!r}, "
                    f"current value is {current_value!r}",
                    code="E_PRECONDITION",
                    details={"fn": fn, "expected": expected, "actual": current_value},
                )

    # Check 'ne' / 'neq' expectation
    ne_key = "ne" if "ne" in expect else ("neq" if "neq" in expect else None)
    if ne_key is not None:
        forbidden = expect[ne_key]
        if current_value == forbidden:
            raise PreconditionError(
                f"Precondition guard failed for {fn}: value must not equal {forbidden!r}",
                code="E_PRECONDITION",
                details={"fn": fn, "forbidden": forbidden, "actual": current_value},
            )


@dataclass(slots=True)
class Session:
    """Manages active session lifecycle, sequence validation, and idempotency cache.

    Tracks SID allocation, session fingerprint (fp) rotation across project reloads,
    strictly increasing mutating MID sequence enforcement, and the 64-entry idempotency
    cache per [WIRE-20], [WIRE-31], [WIRE-32].
    """

    sid: int
    nonce: str
    fp: str
    last_mutating_mid: int = 0
    idempotency_cache: OrderedDict[str, ResponseEnvelope] = field(default_factory=OrderedDict)
    _client_mid: int = 0
    is_active: bool = True

    @classmethod
    def allocate(cls, sid: int | None = None) -> Session:
        """Allocate a fresh session state with random SID, nonce, and fingerprint."""
        allocated_sid = (
            secrets.randbelow(MAX_SID_VALUE) + 1 if sid is None else (sid & MAX_SID_VALUE)
        )
        nonce = secrets.token_hex(4)
        fp = secrets.token_hex(8)
        return cls(sid=allocated_sid, nonce=nonce, fp=fp)

    def rotate_fingerprint(self, reason: str = "project_load") -> str:
        """Rotate session fingerprint per [WIRE-32] (V1-A1).

        Called whenever a new project is loaded or script reloads in FL Studio.
        Any subsequent mutation request sent with a previous fingerprint will fail
        with E_STALE.
        """
        self.fp = secrets.token_hex(8)
        return self.fp

    def reset(self, new_sid: int | None = None) -> None:
        """Reset session for a new connection or script reload per [WIRE-31]."""
        self.sid = (
            secrets.randbelow(MAX_SID_VALUE) + 1 if new_sid is None else (new_sid & MAX_SID_VALUE)
        )
        self.nonce = secrets.token_hex(4)
        self.fp = secrets.token_hex(8)
        self.last_mutating_mid = 0
        self.idempotency_cache.clear()
        self.is_active = True

    def validate_sid(self, incoming_sid: int) -> None:
        """Validate that incoming frame SID matches this active session.

        Frames with SID=0 are allowed during initial handshake before hello completes.
        Mismatched SID raises ProtocolError with code E_STALE per [WIRE-31].
        """
        if self.sid != 0 and incoming_sid != 0 and incoming_sid != self.sid:
            msg = (
                f"Stale or mismatched session ID: received {incoming_sid}, "
                f"active session is {self.sid}"
            )
            raise ProtocolError(
                msg,
                code="E_STALE",
                details={"received_sid": incoming_sid, "active_sid": self.sid},
            )

    def validate_fingerprint(self, request_fp: str | None) -> None:
        """Validate request fingerprint against current session fingerprint.

        If request carries opts.fp and it does not match current fp, raises
        ProtocolError with code E_STALE per [WIRE-32].
        """
        if request_fp is not None and request_fp != self.fp:
            raise ProtocolError(
                f"Session fingerprint mismatch: request had '{request_fp}', "
                f"current session fingerprint is '{self.fp}'",
                code="E_STALE",
                details={"request_fp": request_fp, "session_fp": self.fp},
            )

    def check_idempotency(self, idem: str | None) -> ResponseEnvelope | None:
        """Check if request idempotency key exists in cache.

        Returns cached ResponseEnvelope if present and marks it as recently used,
        or None if not found.
        """
        if not idem:
            return None
        if idem in self.idempotency_cache:
            # Move to end for LRU tracking
            self.idempotency_cache.move_to_end(idem)
            return self.idempotency_cache[idem]
        return None

    def store_idempotent_result(self, idem: str, response: ResponseEnvelope) -> None:
        """Store response in idempotency cache, maintaining max capacity of 64 items."""
        if not idem:
            return
        self.idempotency_cache[idem] = response
        self.idempotency_cache.move_to_end(idem)
        while len(self.idempotency_cache) > MAX_IDEMPOTENCY_CACHE_SIZE:
            self.idempotency_cache.popitem(last=False)

    def validate_incoming_request(
        self,
        envelope: RequestEnvelope,
        mid: int,
        is_mutating: bool | None = None,
    ) -> ResponseEnvelope | None:
        """Validate request preconditions, session fingerprint, and MID sequence.

            Args:
                envelope: Incoming request envelope.
                mid: Wire frame message identifier.
                is_mutating: Optional override indicating whether op mutates state.

        Returns:
            Cached ResponseEnvelope if idempotency hit, or None if validation passed
            and execution should proceed.

            Raises:
                ProtocolError: On stale fingerprint (E_STALE) or replayed MID (E_AUTH).
        """
        # 1. Fingerprint validation per [WIRE-32]
        self.validate_fingerprint(envelope.opts.fp)

        mutating = is_mutating if is_mutating is not None else is_mutating_operation(envelope.op)

        if mutating:
            # 2. Idempotency cache lookup per [WIRE-20]
            cached = self.check_idempotency(envelope.idem)
            if cached is not None:
                return cached

            # 3. Monotonic MID validation per [SEC-01]
            if mid <= self.last_mutating_mid:
                msg = (
                    f"Replayed or non-monotonic MID {mid} <= {self.last_mutating_mid} "
                    "on mutating op"
                )
                raise ProtocolError(
                    msg,
                    code="E_AUTH",
                    details={"mid": mid, "last_mutating_mid": self.last_mutating_mid},
                )

        return None

    def record_completion(
        self,
        envelope: RequestEnvelope,
        mid: int,
        response: ResponseEnvelope,
        is_mutating: bool | None = None,
    ) -> None:
        """Record completed operation, updating last_mutating_mid and caching result."""
        mutating = is_mutating if is_mutating is not None else is_mutating_operation(envelope.op)
        if mutating:
            if mid > self.last_mutating_mid:
                self.last_mutating_mid = mid
            if envelope.idem:
                self.store_idempotent_result(envelope.idem, response)

    def next_mid(self) -> int:
        """Generate next sequential 21-bit client MID (1..2097151)."""
        self._client_mid = (self._client_mid % MAX_MID_VALUE) + 1
        return self._client_mid
