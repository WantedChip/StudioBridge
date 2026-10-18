"""HMAC-SHA256 and SipHash-2-4 request signing and authentication per [SEC-01].

Implements canonical payload formatting, deterministic JSON encoding, constant-time
signature verification, and pure-Python SipHash-2-4 fallback per spec
03_l0a_wire_protocol.md §8.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
from typing import TYPE_CHECKING, Any

from studiobridge.core.errors import ProtocolError

if TYPE_CHECKING:
    from studiobridge.wire.envelope import RequestEnvelope

# ASCII Unit Separator byte (0x1F) per [SEC-01]
AUTH_SEPARATOR: bytes = b"\x1f"

# Supported authentication algorithms
ALG_SHA256: str = "sha256"
ALG_SIPHASH24: str = "siphash24"
SUPPORTED_ALGORITHMS: frozenset[str] = frozenset({ALG_SHA256, ALG_SIPHASH24})

# Operations that are exempt from authentication per spec §5.1, §8
UNAUTHENTICATED_OPS: frozenset[str] = frozenset({"hello", "ping"})


def canonical_json(data: Any) -> str:
    """Produce deterministic canonical JSON representation with sorted keys and no whitespace.

    Uses ensure_ascii=True to guarantee 7-bit clean ASCII output.
    """
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def format_auth_payload(op: str, idem: str | None, args: dict[str, Any] | None) -> bytes:
    """Format canonical message payload to be signed per [SEC-01].

    Format: op || 0x1F || idem || 0x1F || canonical_json(args)
    """
    op_b = op.encode("ascii")
    idem_b = (idem or "").encode("ascii")
    args_b = canonical_json(args if args is not None else {}).encode("ascii")
    return op_b + AUTH_SEPARATOR + idem_b + AUTH_SEPARATOR + args_b


def _normalize_secret(secret: bytes | str) -> bytes:
    """Normalize secret into raw bytes.

    If secret is a 64-character hex string (representing a 256-bit secret),
    it is decoded as hexadecimal bytes. Otherwise, UTF-8 encoded bytes are used.
    """
    if isinstance(secret, bytes):
        return secret
    s = secret.strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        try:
            return bytes.fromhex(s)
        except ValueError:
            pass
    return s.encode("utf-8")


def _sip_round(v0: int, v1: int, v2: int, v3: int) -> tuple[int, int, int, int]:
    """Single SipHash compression round operating on 64-bit unsigned integers."""
    v0 = (v0 + v1) & 0xFFFFFFFFFFFFFFFF
    v1 = ((v1 << 13) | (v1 >> (64 - 13))) & 0xFFFFFFFFFFFFFFFF
    v1 ^= v0
    v0 = ((v0 << 32) | (v0 >> 32)) & 0xFFFFFFFFFFFFFFFF

    v2 = (v2 + v3) & 0xFFFFFFFFFFFFFFFF
    v3 = ((v3 << 16) | (v3 >> (64 - 16))) & 0xFFFFFFFFFFFFFFFF
    v3 ^= v2

    v0 = (v0 + v3) & 0xFFFFFFFFFFFFFFFF
    v3 = ((v3 << 21) | (v3 >> (64 - 21))) & 0xFFFFFFFFFFFFFFFF
    v3 ^= v0

    v2 = (v2 + v1) & 0xFFFFFFFFFFFFFFFF
    v1 = ((v1 << 17) | (v1 >> (64 - 17))) & 0xFFFFFFFFFFFFFFFF
    v1 ^= v2
    v2 = ((v2 << 32) | (v2 >> 32)) & 0xFFFFFFFFFFFFFFFF

    return v0, v1, v2, v3


def siphash24(key: bytes, data: bytes) -> str:
    """Pure-Python implementation of SipHash-2-4 returning a 16-character hex string.

    Fallback algorithm for restricted Python environments (e.g. FL Studio controller script
    lacking _sha256 / hashlib) per [SEC-03].
    """
    if len(key) < 16:
        # Pad key with zeroes up to 16 bytes
        key = key.ljust(16, b"\x00")
    k0, k1 = struct.unpack("<QQ", key[:16])

    # Initial state constants
    v0 = 0x736F6D6570736575 ^ k0
    v1 = 0x646F72616E646F6D ^ k1
    v2 = 0x6C7967656E657261 ^ k0
    v3 = 0x7465646279746573 ^ k1

    length = len(data)
    blocks = length // 8

    # Process 8-byte words
    for i in range(blocks):
        m = struct.unpack("<Q", data[i * 8 : (i + 1) * 8])[0]
        v3 ^= m
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
        v0 ^= m

    # Process remaining tail bytes (0..7) and encode length in highest byte
    tail_bytes = data[blocks * 8 :]
    b = length << 56
    for i, byte_val in enumerate(tail_bytes):
        b |= byte_val << (i * 8)

    v3 ^= b
    v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
    v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
    v0 ^= b

    # Finalization
    v2 ^= 0xFF
    for _ in range(4):
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)

    digest_val = v0 ^ v1 ^ v2 ^ v3
    return f"{digest_val:016x}"


def compute_auth(
    secret: bytes | str,
    op: str,
    idem: str | None = None,
    args: dict[str, Any] | None = None,
    alg: str = ALG_SHA256,
) -> str:
    """Compute truncated 16-hex-character authentication signature over canonical payload.

    Args:
        secret: Shared secret (raw bytes or string/hex string).
        op: Operation name (e.g. "call", "batch").
        idem: Optional idempotency key.
        args: Operation arguments dictionary.
        alg: Authentication algorithm ("sha256" or "siphash24").

    Returns:
        16-character hexadecimal signature string in lowercase.
    """
    secret_bytes = _normalize_secret(secret)
    payload = format_auth_payload(op, idem, args)

    if alg == ALG_SHA256:
        full_digest = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
        return full_digest[:16].lower()
    elif alg == ALG_SIPHASH24:
        return siphash24(secret_bytes, payload).lower()
    else:
        algs = sorted(SUPPORTED_ALGORITHMS)
        raise ProtocolError(
            f"Unsupported authentication algorithm '{alg}', expected one of {algs}",
            code="E_AUTH",
        )


def verify_auth(
    secret: bytes | str,
    auth: str | None,
    op: str,
    idem: str | None = None,
    args: dict[str, Any] | None = None,
    alg: str = ALG_SHA256,
) -> bool:
    """Verify request authentication signature using constant-time comparison.

    Args:
        secret: Shared secret.
        auth: The signature string received on the request envelope.
        op: Operation name.
        idem: Optional idempotency key.
        args: Operation arguments dictionary.
        alg: Authentication algorithm ("sha256" or "siphash24").

    Returns:
        True if signature is valid and authentic; False otherwise.
    """
    if not auth:
        return False
    expected = compute_auth(secret, op, idem, args, alg=alg)
    return hmac.compare_digest(expected.lower(), auth.strip().lower())


def sign_request(
    secret: bytes | str,
    envelope: RequestEnvelope,
    alg: str = ALG_SHA256,
) -> RequestEnvelope:
    """Sign a RequestEnvelope in-place by computing and populating its auth field.

    Args:
        secret: Shared secret.
        envelope: RequestEnvelope to sign.
        alg: Authentication algorithm.

    Returns:
        The signed RequestEnvelope with envelope.auth populated.
    """
    envelope.auth = compute_auth(secret, envelope.op, envelope.idem, envelope.args, alg=alg)
    return envelope


def verify_request(
    secret: bytes | str,
    envelope: RequestEnvelope,
    alg: str = ALG_SHA256,
) -> bool:
    """Validate authentication of a RequestEnvelope.

    Per [WIRE §5.1], 'hello' and 'ping' operations are unauthenticated and bypass checks.
    All other operations must carry a valid HMAC signature matching the shared secret.

    Args:
        secret: Shared secret.
        envelope: RequestEnvelope to verify.
        alg: Authentication algorithm.

    Returns:
        True if valid or exempt; False if missing or mismatched signature.
    """
    if envelope.op in UNAUTHENTICATED_OPS:
        return True
    if not envelope.auth:
        return False
    return verify_auth(
        secret=secret,
        auth=envelope.auth,
        op=envelope.op,
        idem=envelope.idem,
        args=envelope.args,
        alg=alg,
    )
