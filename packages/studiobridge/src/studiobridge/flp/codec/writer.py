"""Binary FLP chunk writer and lossless event stream serializer.

Implements clean-room binary serialization,
preserving original event order, non-canonical varints, and alignment padding
per [FLP-02], [FLP-03], and [FLP-05].
"""

from __future__ import annotations

import io
import struct
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

from studiobridge.core.errors import FlpInvariantViolationError
from studiobridge.flp.codec.events import (
    Event,
    encode_varint,
)
from studiobridge.flp.codec.reader import (
    EventChunk,
    FlpFile,
    FlpHeader,
    HeaderChunk,
    RawChunk,
)


def write_chunk(
    chunk_id: bytes,
    payload: bytes,
    destination: BinaryIO,
    padding: bytes = b"",
) -> int:
    """Write a binary chunk with 4-byte ID, 4-byte little-endian length, and padding [FLP-03]."""
    if len(chunk_id) != 4:
        raise FlpInvariantViolationError(f"Chunk ID must be exactly 4 bytes, got {chunk_id!r}")
    written = destination.write(chunk_id)
    written += destination.write(struct.pack("<I", len(payload)))
    written += destination.write(payload)
    if padding:
        written += destination.write(padding)
    return written


def serialize_events(
    events: Iterable[Event],
    destination: BinaryIO | None = None,
) -> bytes:
    """Serialize a stream of events to binary payload bytes [FLP-02].

    Maintains exact event order and preserves original non-canonical varint
    encodings via LenEnc when present and unchanged.
    """
    buffer = io.BytesIO() if destination is None else None
    target: BinaryIO = destination if destination is not None else buffer  # type: ignore[assignment]

    for ev in events:
        target.write(bytes([ev.id]))
        raw = ev.raw

        if 0 <= ev.id <= 63:
            if len(raw) != 1:
                raise FlpInvariantViolationError(
                    f"Event ID {ev.id} requires exactly 1 byte payload, got {len(raw)}"
                )
            target.write(raw)
        elif 64 <= ev.id <= 127:
            if len(raw) != 2:
                raise FlpInvariantViolationError(
                    f"Event ID {ev.id} requires exactly 2 bytes payload, got {len(raw)}"
                )
            target.write(raw)
        elif 128 <= ev.id <= 191:
            if len(raw) != 4:
                raise FlpInvariantViolationError(
                    f"Event ID {ev.id} requires exactly 4 bytes payload, got {len(raw)}"
                )
            target.write(raw)
        elif 192 <= ev.id <= 255:
            # Variable-length event: preserve original varint if length unmodified [FLP-01]
            if ev.enc is not None and ev.enc.value == len(raw):
                target.write(ev.enc.raw)
            else:
                target.write(encode_varint(len(raw)))
            target.write(raw)
        else:
            raise FlpInvariantViolationError(
                f"Invalid FLP event ID: {ev.id} (must be in range 0–255)"
            )

    if buffer is not None:
        return buffer.getvalue()
    return b""


def serialize_to_stream(flp: FlpFile, destination: BinaryIO) -> int:
    """Stream-serialize parsed FLP container directly into a binary stream [FLP-02, FLP-04]."""
    total_written = 0

    for chunk in flp.chunks:
        if isinstance(chunk, HeaderChunk):
            payload = chunk.header.to_bytes()
            total_written += write_chunk(chunk.id, payload, destination, chunk.padding)
        elif isinstance(chunk, EventChunk):
            payload = serialize_events(chunk.events)
            total_written += write_chunk(chunk.id, payload, destination, chunk.padding)
        elif isinstance(chunk, RawChunk):
            total_written += write_chunk(chunk.id, chunk.data, destination, chunk.padding)
        else:
            # Generic Chunk fallback
            payload = getattr(chunk, "data", b"")
            total_written += write_chunk(chunk.id, payload, destination, chunk.padding)

    if flp.trailing_bytes:
        total_written += destination.write(flp.trailing_bytes)

    return total_written


def serialize(
    flp: FlpFile | tuple[FlpHeader, list[Event]] | list[Event],
    destination: BinaryIO | Path | str | None = None,
) -> bytes:
    """Serialize parsed FLP project to binary FLP container [FLP-02].

    Args:
        flp: FlpFile instance, or (FlpHeader, list[Event]) tuple, or list of Events.
        destination: Optional binary stream or file path to write to.

    Returns:
        Serialized binary bytes (when destination is None or file path).
    """
    file_obj: FlpFile
    if isinstance(flp, FlpFile):
        file_obj = flp
    elif isinstance(flp, tuple):
        header, events = flp
        file_obj = FlpFile(header=header, events=events)
    elif isinstance(flp, list):
        file_obj = FlpFile(header=FlpHeader(), events=flp)
    else:
        raise TypeError(f"Unsupported FLP object type: {type(flp).__name__}")

    if destination is None:
        buf = io.BytesIO()
        serialize_to_stream(file_obj, buf)
        return buf.getvalue()
    elif isinstance(destination, (str, Path)):
        p = Path(destination)
        buf = io.BytesIO()
        serialize_to_stream(file_obj, buf)
        raw = buf.getvalue()
        p.write_bytes(raw)
        return raw
    elif isinstance(destination, io.IOBase):
        buf = io.BytesIO()
        serialize_to_stream(file_obj, buf)
        raw = buf.getvalue()
        destination.write(raw)
        return raw
    else:
        raise TypeError(f"Unsupported destination type: {type(destination).__name__}")
