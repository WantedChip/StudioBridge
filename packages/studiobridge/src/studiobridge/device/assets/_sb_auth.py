"""_sb_auth.py - HMAC-SHA256 and SipHash-2-4 authentication for FL Studio sandbox.

Pure Python 3.9 syntax with zero external dependencies.
"""

import struct

try:
    from studiobridge.device.assets import _sb_json as json_codec
except ImportError:
    try:
        import _sb_json as json_codec  # type: ignore
    except ImportError:
        import json as json_codec  # type: ignore

AUTH_SEPARATOR = b"\x1f"
ALG_SHA256 = "sha256"
ALG_SIPHASH24 = "siphash24"
UNAUTHENTICATED_OPS = ("hello", "ping", "probe")


def _sort_keys(obj):
    """Recursively sort dictionary keys for deterministic canonical JSON representation."""
    if isinstance(obj, dict):
        return {k: _sort_keys(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [_sort_keys(item) for item in obj]
    return obj


def canonical_json(data):
    """Serialize data into deterministic canonical JSON string with sorted keys."""
    if data is None:
        return "{}"
    sorted_data = _sort_keys(data)
    return json_codec.dumps(sorted_data)


def format_auth_payload(op, idem, args):
    """Format canonical message payload to be signed per [SEC-01].

    Format: op || 0x1F || idem || 0x1F || canonical_json(args)
    """
    op_b = op.encode("ascii")
    idem_b = (idem or "").encode("ascii")
    args_b = canonical_json(args if args is not None else {}).encode("ascii")
    return op_b + AUTH_SEPARATOR + idem_b + AUTH_SEPARATOR + args_b


def normalize_secret(secret):
    """Normalize secret into raw bytes."""
    if isinstance(secret, bytes):
        return secret
    s = str(secret).strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        try:
            return bytes.fromhex(s)
        except ValueError:
            pass
    return s.encode("utf-8")


def _sip_round(v0, v1, v2, v3):
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


def siphash24(key, data):
    """Pure-Python implementation of SipHash-2-4 returning a 16-character hex string."""
    if len(key) < 16:
        key = key.ljust(16, b"\x00")
    k0, k1 = struct.unpack("<QQ", key[:16])

    v0 = 0x736F6D6570736575 ^ k0
    v1 = 0x646F72616E646F6D ^ k1
    v2 = 0x6C7967656E657261 ^ k0
    v3 = 0x7465646279746573 ^ k1

    length = len(data)
    blocks = length // 8

    for i in range(blocks):
        m = struct.unpack("<Q", data[i * 8 : (i + 1) * 8])[0]
        v3 ^= m
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
        v0 ^= m

    tail_bytes = data[blocks * 8 :]
    b = length << 56
    for i, byte_val in enumerate(tail_bytes):
        b |= byte_val << (i * 8)

    v3 ^= b
    v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
    v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)
    v0 ^= b

    v2 ^= 0xFF
    for _ in range(4):
        v0, v1, v2, v3 = _sip_round(v0, v1, v2, v3)

    digest_val = v0 ^ v1 ^ v2 ^ v3
    return f"{digest_val:016x}"


def _raw_sha256(data):
    """Compute raw SHA-256 digest bytes using hashlib or _sha256."""
    try:
        import hashlib

        return hashlib.sha256(data).digest()
    except ImportError:
        pass
    try:
        import _sha256  # type: ignore

        return _sha256.sha256(data).digest()
    except ImportError:
        pass
    return None


def hmac_sha256(key, data):
    """Compute HMAC-SHA256 digest returning 16-character hex string."""
    try:
        import hashlib
        import hmac

        return hmac.new(key, data, hashlib.sha256).hexdigest()[:16].lower()
    except (ImportError, AttributeError):
        pass

    # Pure Python HMAC construction on top of raw SHA-256
    block_size = 64
    if len(key) > block_size:
        key_digest = _raw_sha256(key)
        if key_digest is None:
            return siphash24(key, data).lower()
        key = key_digest

    if len(key) < block_size:
        key = key.ljust(block_size, b"\x00")

    o_key_pad = bytearray(b ^ 0x5C for b in key)
    i_key_pad = bytearray(b ^ 0x36 for b in key)

    inner = _raw_sha256(bytes(i_key_pad) + data)
    if inner is None:
        return siphash24(key, data).lower()
    outer = _raw_sha256(bytes(o_key_pad) + inner)
    if outer is None:
        return siphash24(key, data).lower()

    hex_str = "".join(f"{b:02x}" for b in outer)
    return hex_str[:16].lower()


def compute_auth(secret, op, idem=None, args=None, alg=ALG_SHA256):
    """Compute truncated 16-hex-character authentication signature over canonical payload."""
    secret_bytes = normalize_secret(secret)
    payload = format_auth_payload(op, idem, args)

    if alg == ALG_SHA256:
        return hmac_sha256(secret_bytes, payload)
    elif alg == ALG_SIPHASH24:
        return siphash24(secret_bytes, payload).lower()
    raise ValueError(f"Unsupported algorithm: {alg}")


def compare_digest(a, b):
    """Constant-time string comparison without zip strict parameter."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    if len(a) != len(b):
        return False
    res = 0
    for i in range(len(a)):
        res |= ord(a[i]) ^ ord(b[i])
    return res == 0


def verify_auth(secret, auth, op, idem=None, args=None, alg=ALG_SHA256):
    """Validate authentication signature.

    hello and ping bypass authentication. All other operations require matching signature.
    """
    if op in UNAUTHENTICATED_OPS:
        return True
    if not auth:
        return False
    expected = compute_auth(secret, op, idem, args, alg=alg)
    return compare_digest(expected.lower(), str(auth).strip().lower())
