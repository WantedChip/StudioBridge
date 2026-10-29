"""Unit tests for HMAC-SHA256, SipHash-2-4 fallback, and request authentication.

Validates canonical JSON encoding, 16-hex signature truncation, timing attack resistance,
tamper rejection, and unauthenticated operation bypass [SEC-01], [SEC-03].
"""

from __future__ import annotations

import secrets

import pytest

from studiobridge.core.errors import ProtocolError
from studiobridge.wire.auth import (
    ALG_SIPHASH24,
    AUTH_SEPARATOR,
    canonical_json,
    compute_auth,
    format_auth_payload,
    sign_request,
    siphash24,
    verify_auth,
    verify_request,
)
from studiobridge.wire.envelope import RequestEnvelope


class TestCanonicalJson:
    """Test deterministic canonical JSON encoding."""

    def test_key_sorting(self) -> None:
        """Keys are sorted lexicographically regardless of insertion order."""
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"a": 2, "m": 3, "z": 1}
        assert canonical_json(d1) == '{"a":2,"m":3,"z":1}'
        assert canonical_json(d1) == canonical_json(d2)

    def test_compact_separators(self) -> None:
        """No whitespace after colons or commas."""
        d = {"list": [1, 2, 3], "nested": {"k": "v"}}
        out = canonical_json(d)
        assert " " not in out
        assert out == '{"list":[1,2,3],"nested":{"k":"v"}}'

    def test_unicode_escaping(self) -> None:
        """Unicode characters are escaped as ASCII."""
        d = {"note": "♩"}
        out = canonical_json(d)
        assert out == '{"note":"\\u2669"}'
        assert all(ord(c) < 128 for c in out)


class TestFormatAuthPayload:
    """Test format_auth_payload conforming to [SEC-01]."""

    def test_separator_byte(self) -> None:
        """Separator is ASCII 0x1F."""
        assert AUTH_SEPARATOR == b"\x1f"

    def test_payload_structure(self) -> None:
        """op || 0x1F || idem || 0x1F || canonical_json(args)."""
        payload = format_auth_payload("call", "c-123", {"fn": "test", "a": [1]})
        parts = payload.split(b"\x1f")
        assert len(parts) == 3
        assert parts[0] == b"call"
        assert parts[1] == b"c-123"
        assert parts[2] == b'{"a":[1],"fn":"test"}'

    def test_none_idem_becomes_empty(self) -> None:
        """None idem produces empty bytes between separators."""
        payload = format_auth_payload("ping", None, {})
        parts = payload.split(b"\x1f")
        assert len(parts) == 3
        assert parts[0] == b"ping"
        assert parts[1] == b""
        assert parts[2] == b"{}"


class TestHmacSha256Auth:
    """Test HMAC-SHA256 signature generation and constant-time verification."""

    @pytest.fixture
    def test_secret(self) -> bytes:
        return secrets.token_bytes(32)

    def test_signature_is_16_hex_chars(self, test_secret: bytes) -> None:
        """Signature is truncated to 16 hex characters per [SEC-01]."""
        sig = compute_auth(test_secret, "call", "idem-1", {"fn": "setVolume", "a": [1, 0.5]})
        assert len(sig) == 16
        assert all(c in "0123456789abcdef" for c in sig)

    def test_signature_verification_success(self, test_secret: bytes) -> None:
        """Authentic request verifies successfully."""
        args = {"fn": "mixer.setTrackVolume", "a": [1, 0.8]}
        sig = compute_auth(test_secret, "call", "idem-abc", args)
        assert verify_auth(test_secret, sig, "call", "idem-abc", args) is True

    def test_tamper_rejection_op(self, test_secret: bytes) -> None:
        """Tampering with op causes verification failure."""
        sig = compute_auth(test_secret, "call", "idem-1", {"fn": "foo"})
        assert verify_auth(test_secret, sig, "batch", "idem-1", {"fn": "foo"}) is False

    def test_tamper_rejection_idem(self, test_secret: bytes) -> None:
        """Tampering with idem causes verification failure."""
        sig = compute_auth(test_secret, "call", "idem-1", {"fn": "foo"})
        assert verify_auth(test_secret, sig, "call", "idem-2", {"fn": "foo"}) is False

    def test_tamper_rejection_args(self, test_secret: bytes) -> None:
        """Tampering with args causes verification failure."""
        sig = compute_auth(test_secret, "call", "idem-1", {"fn": "foo", "vol": 0.5})
        assert verify_auth(test_secret, sig, "call", "idem-1", {"fn": "foo", "vol": 0.6}) is False

    def test_tamper_rejection_signature(self, test_secret: bytes) -> None:
        """Corrupted signature causes verification failure."""
        sig = compute_auth(test_secret, "call", "idem-1", {"fn": "foo"})
        corrupted = ("0" if sig[0] != "0" else "1") + sig[1:]
        assert verify_auth(test_secret, corrupted, "call", "idem-1", {"fn": "foo"}) is False

    def test_wrong_secret_fails(self, test_secret: bytes) -> None:
        """Wrong secret fails verification."""
        other_secret = secrets.token_bytes(32)
        sig = compute_auth(test_secret, "call", "idem-1", {})
        assert verify_auth(other_secret, sig, "call", "idem-1", {}) is False

    def test_hex_string_secret(self) -> None:
        """Secret passed as 64-char hex string is accepted and decoded properly."""
        raw_secret = b"\x01" * 32
        hex_secret = raw_secret.hex()
        sig_raw = compute_auth(raw_secret, "call", "idem", {"fn": "test"})
        sig_hex = compute_auth(hex_secret, "call", "idem", {"fn": "test"})
        assert sig_raw == sig_hex


class TestSipHash24:
    """Test pure-Python SipHash-2-4 fallback implementation per [SEC-03]."""

    def test_siphash24_output_format(self) -> None:
        """SipHash-2-4 returns 16-hex characters."""
        key = b"\x00" * 16
        data = b"hello world"
        h = siphash24(key, data)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_siphash24_determinism(self) -> None:
        """Same key and data produce identical digests."""
        key = secrets.token_bytes(16)
        data = b"deterministic test"
        assert siphash24(key, data) == siphash24(key, data)

    def test_siphash24_differential(self) -> None:
        """Altered data produces different digest."""
        key = secrets.token_bytes(16)
        h1 = siphash24(key, b"data 1")
        h2 = siphash24(key, b"data 2")
        assert h1 != h2

    def test_compute_auth_siphash24_alg(self) -> None:
        """compute_auth supports alg='siphash24'."""
        key = secrets.token_bytes(32)
        sig = compute_auth(key, "call", "idem-1", {"fn": "test"}, alg=ALG_SIPHASH24)
        assert len(sig) == 16
        assert verify_auth(key, sig, "call", "idem-1", {"fn": "test"}, alg=ALG_SIPHASH24) is True
        assert (
            verify_auth(key, sig, "call", "idem-1", {"fn": "tampered"}, alg=ALG_SIPHASH24) is False
        )

    def test_unsupported_alg_raises_error(self) -> None:
        """Unsupported algorithm name raises ProtocolError."""
        with pytest.raises(ProtocolError) as exc_info:
            compute_auth(b"secret", "call", alg="md5")
        assert exc_info.value.code == "E_AUTH"


class TestEnvelopeSigningAndVerification:
    """Test sign_request and verify_request with RequestEnvelope."""

    def test_sign_and_verify_request(self) -> None:
        """sign_request populates envelope.auth which verifies successfully."""
        secret = secrets.token_bytes(32)
        req = RequestEnvelope(
            op="call",
            idem="c-100",
            args={"fn": "mixer.setTrackVolume", "a": [1, 0.75]},
        )
        assert req.auth is None

        sign_request(secret, req)
        assert req.auth is not None
        assert len(req.auth) == 16
        assert verify_request(secret, req) is True

    def test_unauthenticated_ops_bypass_verification(self) -> None:
        """'hello' and 'ping' operations bypass auth verification."""
        secret = secrets.token_bytes(32)
        hello_req = RequestEnvelope(op="hello", args={"client": {"name": "test"}})
        assert verify_request(secret, hello_req) is True

        ping_req = RequestEnvelope(op="ping")
        assert verify_request(secret, ping_req) is True

    def test_missing_auth_on_mutating_op_fails(self) -> None:
        """Mutating or protected op with missing auth fails verification."""
        secret = secrets.token_bytes(32)
        req = RequestEnvelope(op="call", idem="c-1", args={"fn": "test"})
        assert verify_request(secret, req) is False
