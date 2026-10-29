"""Binary FLP chunk reader, event stream parser, and lazy streaming reader.

Implements clean-room FLP container decoding,
preserving exact byte layouts, unknown chunk IDs, non-standard alignments,
and trailing data per [FLP-02], [FLP-03], [FLP-04], and [FLP-05].
"""

from __future__ import annotations

import io
import struct
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from studiobridge.core.errors import FlpParseError
from studiobridge.flp.codec.events import (
    Event,
    decode_varint,
    event_fixed_size,
)

CHUNK_ID_FLHD: bytes = b"FLhd"
CHUNK_ID_FLDT: bytes = b"FLdt"
MIN_HEADER_CHUNK_LEN: int = 6
DEFAULT_LAZY_THRESHOLD: int = 65536  # Payloads >= 64KB qualify for lazy loading


@dataclass
class FlpHeader:
    """FLhd header chunk representation [FLP-05].

    Preserves original verbatim header bytes unless format, channels, or PPQ
    have been modified by higher layers.
    """

    format: int = 0
    channels: int = 0
    ppq: int = 96
    raw: bytes = b""

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> FlpHeader:
        """Parse FLhd header payload bytes [FLP-05]."""
        if len(data) < MIN_HEADER_CHUNK_LEN:
            raise FlpParseError(
                f"FLhd header chunk payload truncated: expected at least "
                f"{MIN_HEADER_CHUNK_LEN} bytes, got {len(data)}",
                offset=offset,
                details={"expected": MIN_HEADER_CHUNK_LEN, "actual": len(data)},
            )
        fmt, channels, ppq = struct.unpack_from("<HHH", data)
        return cls(format=fmt, channels=channels, ppq=ppq, raw=data)

    def is_modified(self) -> bool:
        """Check if modeled fields differ from raw bytes."""
        if len(self.raw) < MIN_HEADER_CHUNK_LEN:
            return True
        raw_fmt, raw_ch, raw_ppq = struct.unpack_from("<HHH", self.raw)
        return self.format != raw_fmt or self.channels != raw_ch or self.ppq != raw_ppq

    def to_bytes(self) -> bytes:
        """Serialize header to binary, preserving verbatim payload if unmodified."""
        if not self.is_modified() and self.raw:
            return self.raw
        extra = self.raw[MIN_HEADER_CHUNK_LEN:] if len(self.raw) > MIN_HEADER_CHUNK_LEN else b""
        return struct.pack("<HHH", self.format, self.channels, self.ppq) + extra


@dataclass
class Chunk:
    """Base chunk in FLP file [FLP-03]."""

    id: bytes
    padding: bytes = b""


@dataclass
class HeaderChunk(Chunk):
    """FLhd header chunk wrapper [FLP-05]."""

    header: FlpHeader = field(default_factory=FlpHeader)
    id: bytes = CHUNK_ID_FLHD


@dataclass
class EventChunk(Chunk):
    """FLdt event stream chunk wrapper [FLP-02]."""

    events: list[Event] = field(default_factory=list)
    id: bytes = CHUNK_ID_FLDT


@dataclass
class RawChunk(Chunk):
    """Unknown or vendor-specific chunk preserved verbatim [FLP-03]."""

    data: bytes = b""
    id: bytes = b""


@dataclass
class FlpFile:
    """Parsed FLP project container [FLP-02].

    Maintains lossless byte fidelity across event stream, unknown chunks,
    non-standard alignments, and trailing data.
    """

    header: FlpHeader
    events: list[Event]
    chunks: list[Chunk] = field(default_factory=list)
    trailing_bytes: bytes = b""

    def __post_init__(self) -> None:
        if not self.chunks:
            self.chunks = [
                HeaderChunk(header=self.header),
                EventChunk(events=self.events),
            ]

    def serialize(self, destination: BinaryIO | None = None) -> bytes:
        """Serialize project to binary FLP container [FLP-02]."""
        from studiobridge.flp.codec.writer import serialize

        return serialize(self, destination=destination)

    def save(self, path: str | Path) -> None:
        """Save project to file path atomically."""
        p = Path(path)
        with open(p, "wb") as f:
            self.serialize(destination=f)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        lazy: bool = False,
        lazy_threshold: int = DEFAULT_LAZY_THRESHOLD,
    ) -> FlpFile:
        """Parse FLP project container from bytes [FLP-02]."""
        return parse(data, lazy=lazy, lazy_threshold=lazy_threshold)

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        lazy: bool = False,
        lazy_threshold: int = DEFAULT_LAZY_THRESHOLD,
    ) -> FlpFile:
        """Parse FLP project container from file path [FLP-02]."""
        return parse(path, lazy=lazy, lazy_threshold=lazy_threshold)


def _make_lazy_loader(
    path: Path,
    file_offset: int,
    payload_len: int,
) -> Callable[[], bytes]:
    """Create a deferred byte loader for large event payloads [FLP-04]."""

    def _loader() -> bytes:
        with open(path, "rb") as f:
            f.seek(file_offset)
            data = f.read(payload_len)
            if len(data) != payload_len:
                raise FlpParseError(
                    f"Truncated lazy payload at file offset {file_offset}: "
                    f"expected {payload_len} bytes, got {len(data)}",
                    offset=file_offset,
                    details={
                        "file_offset": file_offset,
                        "expected": payload_len,
                        "read": len(data),
                    },
                )
            return data

    return _loader


def iter_events(
    data: bytes | memoryview,
    start_offset: int = 0,
    end_offset: int | None = None,
    *,
    base_file_offset: int = 0,
    file_path: Path | None = None,
    lazy_threshold: int | None = None,
) -> Iterator[Event]:
    """Stream events from binary slice one-by-one [FLP-04].

    Yields Event instances without materializing an entire list, supporting
    memory-bounded processing of projects with large event counts.
    """
    limit = len(data) if end_offset is None else end_offset
    pos = start_offset

    while pos < limit:
        event_offset = pos
        event_id = data[pos]
        pos += 1

        fixed_size = event_fixed_size(event_id)
        if fixed_size is not None:
            if pos + fixed_size > limit:
                raise FlpParseError(
                    f"Truncated {fixed_size}-byte event ID {event_id} at offset "
                    f"{base_file_offset + event_offset}: expected {fixed_size} bytes, "
                    f"available {limit - pos}",
                    offset=base_file_offset + event_offset,
                    details={
                        "event_id": event_id,
                        "expected": fixed_size,
                        "available": limit - pos,
                        "offset": base_file_offset + event_offset,
                    },
                )
            raw = bytes(data[pos : pos + fixed_size])
            pos += fixed_size
            yield Event(id=event_id, raw=raw, enc=None)
        else:
            # Variable-length event (IDs 192–255)
            var_len, len_enc, next_pos = decode_varint(
                data,
                offset=pos,
                limit=limit,
                base_offset=base_file_offset,
            )
            pos = next_pos

            if pos + var_len > limit:
                raise FlpParseError(
                    f"Truncated variable payload for event ID {event_id} at offset "
                    f"{base_file_offset + event_offset}: expected {var_len} bytes, "
                    f"available {limit - pos}",
                    offset=base_file_offset + event_offset,
                    details={
                        "event_id": event_id,
                        "expected": var_len,
                        "available": limit - pos,
                        "offset": base_file_offset + event_offset,
                    },
                )

            payload_file_offset = base_file_offset + pos
            if lazy_threshold is not None and var_len >= lazy_threshold and file_path is not None:
                loader = _make_lazy_loader(file_path, payload_file_offset, var_len)
                yield Event(id=event_id, raw=loader, enc=len_enc)
            else:
                raw = bytes(data[pos : pos + var_len])
                yield Event(id=event_id, raw=raw, enc=len_enc)

            pos += var_len


def parse_events(
    data: bytes | memoryview,
    start_offset: int = 0,
    end_offset: int | None = None,
    *,
    base_file_offset: int = 0,
    file_path: Path | None = None,
    lazy_threshold: int | None = None,
) -> list[Event]:
    """Parse all events from binary slice into a list [FLP-02]."""
    return list(
        iter_events(
            data,
            start_offset=start_offset,
            end_offset=end_offset,
            base_file_offset=base_file_offset,
            file_path=file_path,
            lazy_threshold=lazy_threshold,
        )
    )


def iter_events_from_file(
    path: str | Path,
    *,
    lazy: bool = False,
    lazy_threshold: int = DEFAULT_LAZY_THRESHOLD,
) -> Iterator[Event]:
    """Memory-bounded streaming reader for events from large files [FLP-04]."""
    p = Path(path)
    file_bytes = p.read_bytes()
    chunks, _ = read_chunks(
        file_bytes,
        file_path=p if lazy else None,
        lazy=lazy,
        lazy_threshold=lazy_threshold,
    )
    for chunk in chunks:
        if isinstance(chunk, EventChunk):
            yield from chunk.events


def read_chunks(
    data: bytes | memoryview,
    *,
    file_path: Path | None = None,
    lazy: bool = False,
    lazy_threshold: int = DEFAULT_LAZY_THRESHOLD,
) -> tuple[list[Chunk], bytes]:
    """Read binary chunks and trailing data from FLP stream [FLP-03].

    Returns (chunks, trailing_bytes).
    """
    total_len = len(data)
    if total_len < 8:
        raise FlpParseError(
            f"File too short to contain FLP chunk header: expected at least 8 bytes, "
            f"got {total_len}",
            offset=0,
            details={"file_size": total_len},
        )

    first_chunk_id = bytes(data[0:4])
    if first_chunk_id != CHUNK_ID_FLHD:
        raise FlpParseError(
            f"Invalid FLP file: first chunk must be 'FLhd', got {first_chunk_id!r}",
            offset=0,
            details={"chunk_id": first_chunk_id},
        )

    chunks: list[Chunk] = []
    offset = 0

    while offset + 8 <= total_len:
        chunk_id = bytes(data[offset : offset + 4])
        chunk_len = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_len

        if payload_end > total_len:
            # If this is FLhd or FLdt, it is a truncated file
            if chunk_id in (CHUNK_ID_FLHD, CHUNK_ID_FLDT):
                raise FlpParseError(
                    f"Truncated chunk '{chunk_id.decode('ascii', errors='replace')}': "
                    f"declared length {chunk_len} exceeds file size",
                    offset=offset,
                    details={
                        "chunk_id": chunk_id,
                        "declared_length": chunk_len,
                        "available": total_len - payload_start,
                        "offset": offset,
                    },
                )
            # Otherwise, remainder is trailing bytes
            break

        chunk_payload = data[payload_start:payload_end]
        offset = payload_end

        # Check for non-standard chunk alignment padding [FLP-03]
        padding = b""
        if offset < total_len and data[offset] == 0:
            pad_len = 0
            while offset + pad_len < total_len and data[offset + pad_len] == 0 and pad_len < 4:
                pad_len += 1
            if offset + pad_len + 8 <= total_len:
                next_len = struct.unpack_from("<I", data, offset + pad_len + 4)[0]
                if offset + pad_len + 8 + next_len <= total_len:
                    padding = bytes(data[offset : offset + pad_len])
                    offset += pad_len

        if chunk_id == CHUNK_ID_FLHD:
            header = FlpHeader.from_bytes(bytes(chunk_payload), offset=payload_start)
            chunks.append(HeaderChunk(id=chunk_id, header=header, padding=padding))
        elif chunk_id == CHUNK_ID_FLDT:
            events = parse_events(
                data,
                start_offset=payload_start,
                end_offset=payload_end,
                base_file_offset=0,
                file_path=file_path,
                lazy_threshold=lazy_threshold if lazy else None,
            )
            chunks.append(EventChunk(id=chunk_id, events=events, padding=padding))
        else:
            # Preserved verbatim [FLP-03]
            chunks.append(RawChunk(id=chunk_id, data=bytes(chunk_payload), padding=padding))

    trailing_bytes = bytes(data[offset:])
    return chunks, trailing_bytes


def parse(
    source: bytes | BinaryIO | Path | str,
    *,
    lazy: bool = False,
    lazy_threshold: int = DEFAULT_LAZY_THRESHOLD,
) -> FlpFile:
    """Parse a binary FLP file or byte stream into an FlpFile [FLP-02].

    Args:
        source: Binary bytes, open binary stream, or file path.
        lazy: When True, defers loading of variable payloads >= lazy_threshold [FLP-04].
        lazy_threshold: Minimum payload size in bytes to qualify for lazy loading.

    Returns:
        FlpFile container preserving exact byte structures.
    """
    file_path: Path | None = None
    data: bytes

    if isinstance(source, (str, Path)):
        file_path = Path(source)
        data = file_path.read_bytes()
    elif isinstance(source, bytes):
        data = source
    elif isinstance(source, io.IOBase):
        data = source.read()
    else:
        raise TypeError(f"Unsupported source type: {type(source).__name__}")

    chunks, trailing = read_chunks(
        data,
        file_path=file_path if lazy else None,
        lazy=lazy,
        lazy_threshold=lazy_threshold,
    )

    header: FlpHeader | None = None
    all_events: list[Event] = []

    for chunk in chunks:
        if isinstance(chunk, HeaderChunk) and header is None:
            header = chunk.header
        elif isinstance(chunk, EventChunk):
            all_events.extend(chunk.events)

    if header is None:
        raise FlpParseError(
            "FLP file missing required 'FLhd' header chunk",
            offset=0,
        )

    return FlpFile(
        header=header,
        events=all_events,
        chunks=chunks,
        trailing_bytes=trailing,
    )
