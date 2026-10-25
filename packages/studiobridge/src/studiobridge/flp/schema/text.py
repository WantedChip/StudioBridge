"""Text encoding and decoding for FLP event strings across FL Studio versions.

Implements clean-room text decoders handling modern UTF-16LE strings and
legacy codepage/ASCII strings per 07_l0e_flp_engine.md §3.1, §3.2 and [FLP-06].
"""

from __future__ import annotations

import re


def detect_encoding(raw: bytes, default: str = "utf-16-le") -> str:
    """Detect whether a raw byte sequence is likely UTF-16LE, UTF-8, or legacy ASCII/cp1252.

    Modern FL Studio (FL 12 through FL 26) primarily uses UTF-16LE for project
    strings, whereas older files (FL 1–11) used single-byte ASCII/Windows-1252 [FLP-06].
    """
    if not raw:
        return default

    # UTF-16LE BOM check
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"

    # Check for UTF-16LE ASCII pattern: even-length bytes where alternate bytes are 0x00
    if len(raw) >= 4 and len(raw) % 2 == 0:
        high_bytes = raw[1::2]
        zero_ratio = high_bytes.count(0) / len(high_bytes)
        if zero_ratio >= 0.7:
            return "utf-16-le"

    # Try UTF-8 if it decodes cleanly and contains no null bytes (except maybe at end)
    trimmed = raw.rstrip(b"\x00")
    if trimmed:
        try:
            trimmed.decode("utf-8")
            # If all ASCII characters, could be either, but single-byte format
            if all(b < 128 for b in trimmed):
                return "ascii"
            return "utf-8"
        except UnicodeDecodeError:
            pass

    return "cp1252"


def decode_text(
    raw: bytes,
    encoding: str = "utf-16-le",
    fallback_encoding: str = "latin1",
) -> str:
    """Decode raw event payload bytes to a Python string [FLP-06].

    Safely handles UTF-16LE strings, null-terminators, odd byte lengths,
    and legacy single-byte codepages without raising unhandled decode errors.
    """
    if not raw:
        return ""

    enc_norm = encoding.lower().replace("-", "").replace("_", "")

    # Handle UTF-16LE specifics
    if enc_norm in ("utf16le", "utf16"):
        # Strip trailing null words (two null bytes) if present
        data = raw
        if len(data) >= 2 and data.endswith(b"\x00\x00"):
            data = data[:-2]
        elif len(data) >= 1 and data.endswith(b"\x00") and len(data) % 2 != 0:
            # Strip trailing single null byte if odd
            data = data[:-1]

        # If data is odd length after stripping, UTF-16LE is invalid; try UTF-8/fallback
        if len(data) % 2 != 0:
            try:
                return raw.rstrip(b"\x00").decode("utf-8")
            except UnicodeDecodeError:
                return raw.rstrip(b"\x00").decode(fallback_encoding, errors="replace")

        # Check if alternate bytes look like UTF-16LE (ASCII interleaved with nulls)
        high_bytes = data[1::2]
        if (
            high_bytes
            and not data.startswith(b"\xff\xfe")
            and (high_bytes.count(0) / len(high_bytes)) < 0.3
        ):
            # Alternate bytes lack null padding; payload is likely ASCII or single-byte text
            try:
                return data.rstrip(b"\x00").decode("utf-8")
            except UnicodeDecodeError:
                return raw.rstrip(b"\x00").decode(fallback_encoding, errors="replace")

        try:
            decoded = data.decode("utf-16-le")
            # Strip any embedded null characters from trailing terminators
            return decoded.rstrip("\x00")
        except UnicodeDecodeError:
            # Fall back to UTF-8 then fallback_encoding
            try:
                return raw.rstrip(b"\x00").decode("utf-8")
            except UnicodeDecodeError:
                return raw.rstrip(b"\x00").decode(fallback_encoding, errors="replace")

    # Single-byte or specified encoding
    data = raw.rstrip(b"\x00")
    try:
        return data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode(fallback_encoding, errors="replace")


def encode_text(
    text: str,
    encoding: str = "utf-16-le",
    null_terminate: bool = True,
) -> bytes:
    """Encode a Python string into binary event payload bytes [FLP-06]."""
    enc_norm = encoding.lower().replace("-", "").replace("_", "")
    encoded = text.encode(encoding)

    if null_terminate:
        if enc_norm in ("utf16le", "utf16"):
            encoded += b"\x00\x00"
        else:
            encoded += b"\x00"

    return encoded


def decode_version_string(raw: bytes) -> str:
    """Decode and normalize the FL Studio version string from event 199 [FLP-06, FLP-10].

    Version strings in FL Studio (event ID 199) are stored either as ASCII/UTF-8
    (e.g., b"21.0.3.3517\\x00" or b"26.1.0\\x00") or as UTF-16LE.
    Returns a cleaned, normalized version string such as "26.1.0.1234" or "21.0.3".
    """
    if not raw:
        return ""

    # Check if raw has UTF-16LE alternating nulls
    is_utf16 = False
    if len(raw) >= 4 and len(raw) % 2 == 0:
        high_bytes = raw[1::2]
        if high_bytes.count(0) / len(high_bytes) >= 0.7:
            is_utf16 = True

    if is_utf16:
        decoded = decode_text(raw, encoding="utf-16-le")
    else:
        decoded = decode_text(raw, encoding="ascii", fallback_encoding="latin1")

    # Clean non-printable characters and trim whitespace
    cleaned = re.sub(r"[^\w\.\-\+]", "", decoded).strip()
    return cleaned
