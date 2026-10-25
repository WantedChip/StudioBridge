"""FLP binary parser, event schema, object model, and lossless serialization."""

from __future__ import annotations

from studiobridge.core.errors import FlpParseError
from studiobridge.flp.codec import (
    Chunk,
    Event,
    EventChunk,
    EventKind,
    FlpFile,
    FlpHeader,
    HeaderChunk,
    LenEnc,
    RawChunk,
    decode_varint,
    encode_varint,
    parse,
    serialize,
)

__all__ = [
    "Chunk",
    "Event",
    "EventChunk",
    "EventKind",
    "FlpFile",
    "FlpHeader",
    "FlpParseError",
    "HeaderChunk",
    "LenEnc",
    "RawChunk",
    "decode_varint",
    "encode_varint",
    "parse",
    "serialize",
]
