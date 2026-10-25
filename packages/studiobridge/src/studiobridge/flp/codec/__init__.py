"""Binary FLP codec: event models, chunk parsing, and lossless serialization."""

from __future__ import annotations

from studiobridge.flp.codec.events import (
    Event,
    EventKind,
    LenEnc,
    decode_varint,
    encode_varint,
    event_fixed_size,
    event_kind,
)
from studiobridge.flp.codec.reader import (
    Chunk,
    EventChunk,
    FlpFile,
    FlpHeader,
    HeaderChunk,
    RawChunk,
    iter_events,
    iter_events_from_file,
    parse,
    parse_events,
    read_chunks,
)
from studiobridge.flp.codec.writer import (
    serialize,
    serialize_events,
    serialize_to_stream,
    write_chunk,
)

__all__ = [
    "Chunk",
    "Event",
    "EventChunk",
    "EventKind",
    "FlpFile",
    "FlpHeader",
    "HeaderChunk",
    "LenEnc",
    "RawChunk",
    "decode_varint",
    "encode_varint",
    "event_fixed_size",
    "event_kind",
    "iter_events",
    "iter_events_from_file",
    "parse",
    "parse_events",
    "read_chunks",
    "serialize",
    "serialize_events",
    "serialize_to_stream",
    "write_chunk",
]
