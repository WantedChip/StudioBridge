"""Unit tests for Session state machine, fingerprint validation, and idempotency cache.

Validates SID allocation, fingerprint rotation on project reload (V1-A1), precondition
guards (V1-A2), monotonic mutating MID sequence, and the 64-item idempotency cache
[WIRE-20], [WIRE-31], [WIRE-32].
"""

from __future__ import annotations

import pytest

from studiobridge.core.errors import PreconditionError, ProtocolError
from studiobridge.wire.envelope import RequestEnvelope, RequestOpts, ResponseEnvelope
from studiobridge.wire.session import (
    MAX_IDEMPOTENCY_CACHE_SIZE,
    MAX_MID_VALUE,
    MAX_SID_VALUE,
    Session,
    evaluate_precondition,
    is_mutating_operation,
)


class TestSessionLifecycle:
    """Test session allocation, reset, and validation."""

    def test_allocate_session(self) -> None:
        """Session allocation produces valid 14-bit SID, nonce, and fingerprint."""
        sess = Session.allocate()
        assert 1 <= sess.sid <= MAX_SID_VALUE
        assert len(sess.nonce) == 8
        assert len(sess.fp) == 16
        assert sess.last_mutating_mid == 0
        assert len(sess.idempotency_cache) == 0

    def test_allocate_custom_sid(self) -> None:
        """Custom SID is clamped to 14 bits."""
        sess = Session.allocate(sid=0x1234)
        assert sess.sid == 0x1234

    def test_validate_sid(self) -> None:
        """Matching SID passes, mismatched SID raises E_STALE per [WIRE-31]."""
        sess = Session.allocate(sid=100)
        sess.validate_sid(100)
        sess.validate_sid(0)  # SID=0 allowed during handshake

        with pytest.raises(ProtocolError) as exc_info:
            sess.validate_sid(101)
        assert exc_info.value.code == "E_STALE"

    def test_reset_session(self) -> None:
        """Reset clears idempotency cache, advances MID, and assigns new tokens."""
        sess = Session.allocate(sid=10)
        old_fp = sess.fp
        sess.last_mutating_mid = 5
        sess.store_idempotent_result("idem-1", ResponseEnvelope.success())
        assert len(sess.idempotency_cache) == 1

        sess.reset(new_sid=20)
        assert sess.sid == 20
        assert sess.fp != old_fp
        assert sess.last_mutating_mid == 0
        assert len(sess.idempotency_cache) == 0


class TestFingerprintGuards:
    """Stale fingerprint triggers E_STALE error before mutation."""

    def test_fingerprint_matching(self) -> None:
        """Matching fingerprint passes validation."""
        sess = Session.allocate()
        sess.validate_fingerprint(sess.fp)
        sess.validate_fingerprint(None)  # No fp specified passes

    def test_stale_fingerprint_rejected_with_e_stale(self) -> None:
        """Mismatched or stale fingerprint raises ProtocolError with E_STALE."""
        sess = Session.allocate()
        old_fp = sess.fp

        # Rotate fingerprint (simulating project load in FL Studio per [WIRE-32])
        new_fp = sess.rotate_fingerprint(reason="project_load")
        assert new_fp != old_fp

        # Sending request with old_fp raises E_STALE
        with pytest.raises(ProtocolError) as exc_info:
            sess.validate_fingerprint(old_fp)
        assert exc_info.value.code == "E_STALE"

    def test_validate_incoming_request_rejects_stale_fp(self) -> None:
        """validate_incoming_request rejects stale fingerprint before executing op."""
        sess = Session.allocate()
        stale_req = RequestEnvelope(
            op="call",
            idem="c-1",
            args={"fn": "mixer.setTrackVolume"},
            opts=RequestOpts(fp="stale-fp-token"),
        )
        with pytest.raises(ProtocolError) as exc_info:
            sess.validate_incoming_request(stale_req, mid=1)
        assert exc_info.value.code == "E_STALE"


class TestPreconditionEvaluation:
    """Test opts.expect precondition guard per V1-A2."""

    def test_exact_equality(self) -> None:
        """Expect 'eq' check passes on match, raises E_PRECONDITION on mismatch."""
        expect = {"fn": "mixer.getTrackVolume", "a": [3], "eq": 0.8}
        evaluate_precondition(expect, 0.8)

        with pytest.raises(PreconditionError) as exc_info:
            evaluate_precondition(expect, 0.5)
        assert exc_info.value.code == "E_PRECONDITION"

    def test_numeric_tolerance(self) -> None:
        """Expect with 'tol' checks float tolerance abs(actual - eq) <= tol."""
        expect = {"fn": "mixer.getTrackVolume", "a": [3], "eq": 0.8, "tol": 0.005}

        # 0.803 is within 0.005 of 0.8
        evaluate_precondition(expect, 0.803)
        # 0.797 is within 0.005 of 0.8
        evaluate_precondition(expect, 0.797)

        # 0.810 exceeds tolerance 0.005
        with pytest.raises(PreconditionError) as exc_info:
            evaluate_precondition(expect, 0.810)
        assert exc_info.value.code == "E_PRECONDITION"

    def test_not_equal_guard(self) -> None:
        """Expect with 'ne' fails if value matches forbidden value."""
        expect = {"fn": "transport.isPlaying", "ne": True}
        evaluate_precondition(expect, False)

        with pytest.raises(PreconditionError) as exc_info:
            evaluate_precondition(expect, True)
        assert exc_info.value.code == "E_PRECONDITION"

    def test_none_expect_noop(self) -> None:
        """None or empty expect is a no-op."""
        evaluate_precondition(None, 123)
        evaluate_precondition({}, 123)


class TestIdempotencyAndMonotonicMid:
    """Test 64-item idempotency cache and monotonic MID validation per [WIRE-20], [SEC-01]."""

    def test_mutating_op_caching_and_replay(self) -> None:
        """Cached result returned on retry with same idem key without re-execution."""
        sess = Session.allocate()
        req = RequestEnvelope(
            op="call",
            idem="idem-first",
            args={"fn": "mixer.setTrackVolume", "a": [1, 0.5]},
        )

        # First request passes validation
        cached = sess.validate_incoming_request(req, mid=1)
        assert cached is None

        # Operation completes
        response = ResponseEnvelope.success(r=True)
        sess.record_completion(req, mid=1, response=response)
        assert sess.last_mutating_mid == 1

        # Client retries with same idem and same MID
        cached_res = sess.validate_incoming_request(req, mid=1)
        assert cached_res is not None
        assert cached_res.ok is True
        assert cached_res.r is True

        # Client retries with same idem and a different MID (network resend)
        cached_res2 = sess.validate_incoming_request(req, mid=2)
        assert cached_res2 is not None

    def test_replayed_mid_without_idem_rejected(self) -> None:
        """Mutating op with MID <= last_mutating_mid and without matching idem is rejected."""
        sess = Session.allocate()
        req1 = RequestEnvelope(op="call", idem="c-1", args={"fn": "a"})
        sess.validate_incoming_request(req1, mid=5)
        sess.record_completion(req1, mid=5, response=ResponseEnvelope.success())

        # Second mutating op arrives with mid=4 (replayed / stale MID)
        req2 = RequestEnvelope(op="call", idem="c-2", args={"fn": "b"})
        with pytest.raises(ProtocolError) as exc_info:
            sess.validate_incoming_request(req2, mid=4)
        assert exc_info.value.code == "E_AUTH"

        # Mutating op arrives with mid=5 (same as last_mutating_mid, different idem)
        with pytest.raises(ProtocolError) as exc_info2:
            sess.validate_incoming_request(req2, mid=5)
        assert exc_info2.value.code == "E_AUTH"

    def test_non_mutating_op_allows_any_mid(self) -> None:
        """Non-mutating ops (e.g. ping, probe) do not enforce mutating MID sequence."""
        sess = Session.allocate()
        sess.last_mutating_mid = 100

        ping_req = RequestEnvelope(op="ping")
        # Ping with mid=1 (less than last_mutating_mid=100) is accepted
        assert sess.validate_incoming_request(ping_req, mid=1) is None

    def test_idempotency_cache_eviction_at_64(self) -> None:
        """Cache stores at most 64 entries, evicting the oldest on the 65th."""
        sess = Session.allocate()
        for i in range(MAX_IDEMPOTENCY_CACHE_SIZE + 10):
            idem = f"idem-{i}"
            res = ResponseEnvelope.success(r=i)
            sess.store_idempotent_result(idem, res)

        assert len(sess.idempotency_cache) == MAX_IDEMPOTENCY_CACHE_SIZE

        # First 10 items (0..9) must have been evicted
        for i in range(10):
            assert sess.check_idempotency(f"idem-{i}") is None

        # Last 64 items (10..73) must still be in cache
        for i in range(10, MAX_IDEMPOTENCY_CACHE_SIZE + 10):
            hit = sess.check_idempotency(f"idem-{i}")
            assert hit is not None
            assert hit.r == i

    def test_client_next_mid_generation(self) -> None:
        """next_mid generates strictly sequential 21-bit values."""
        sess = Session.allocate()
        assert sess.next_mid() == 1
        assert sess.next_mid() == 2
        assert sess.next_mid() == 3

        # Test rollover
        sess._client_mid = MAX_MID_VALUE
        assert sess.next_mid() == 1

    def test_is_mutating_operation_helper(self) -> None:
        """Verify mutating op categorization."""
        assert is_mutating_operation("call") is True
        assert is_mutating_operation("batch") is True
        assert is_mutating_operation("txn") is True
        assert is_mutating_operation("panic") is True
        assert is_mutating_operation("exec") is True
        assert is_mutating_operation("hello") is False
        assert is_mutating_operation("ping") is False
        assert is_mutating_operation("probe") is False
        assert is_mutating_operation("introspect") is False
