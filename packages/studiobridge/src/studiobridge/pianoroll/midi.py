"""Pure-Python Standard MIDI File (SMF Format 0) encoder and parser.

Provides zero-dependency MIDI export fallback per spec 06_l0d_pianoroll_actuation_render.md §7.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from pathlib import Path

from studiobridge.pianoroll.types import DEFAULT_PPQ, Note


def encode_vlq(value: int) -> bytes:
    """Encode an integer as a MIDI Variable-Length Quantity (VLQ)."""
    if value < 0:
        raise ValueError(f"VLQ value must be non-negative, got {value}")
    buf = [value & 0x7F]
    value >>= 7
    while value > 0:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.reverse()
    return bytes(buf)


def decode_vlq(data: bytes, offset: int) -> tuple[int, int]:
    """Decode a MIDI Variable-Length Quantity from bytes starting at offset.

    Returns:
        tuple of (decoded_value, new_offset)
    """
    value = 0
    while True:
        if offset >= len(data):
            raise ValueError("Truncated VLQ data in MIDI stream")
        b = data[offset]
        offset += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return value, offset


def encode_midi_bytes(
    notes: Sequence[Note],
    ppq: int = DEFAULT_PPQ,
    tempo_bpm: float = 120.0,
) -> bytes:
    """Encode a sequence of Note objects into SMF Format 0 binary bytes."""
    if ppq <= 0 or ppq > 0x7FFF:
        raise ValueError(f"PPQ must be between 1 and 32767, got {ppq}")
    if tempo_bpm <= 0:
        raise ValueError(f"tempo_bpm must be positive, got {tempo_bpm}")

    # 1. SMF 0 Header: MThd, length=6, format=0, ntracks=1, division=ppq
    header = struct.pack(">4sIHHH", b"MThd", 6, 0, 1, ppq)

    # 2. Track Events
    # Collect all note events: (time, priority, event_bytes)
    # priority 0 for note-off, 1 for note-on so note-offs precede note-ons at same tick
    events: list[tuple[int, int, bytes]] = []

    for n in notes:
        ch = max(0, min(15, n.color))
        key = max(0, min(127, n.key))
        vel = max(1, min(127, int(round(n.velocity * 127.0))))
        rel = max(0, min(127, int(round(n.release * 127.0))))

        # Note-On event: 0x90 | ch, key, vel
        note_on_bytes = bytes([0x90 | ch, key, vel])
        events.append((n.pos, 1, note_on_bytes))

        # Note-Off event: 0x80 | ch, key, rel
        note_off_bytes = bytes([0x80 | ch, key, rel])
        events.append((n.pos + n.length, 0, note_off_bytes))

    # Sort events chronologically
    events.sort(key=lambda e: (e[0], e[1]))

    # 3. Assemble Track Data
    track_body = bytearray()

    # Initial tempo meta-event at delta 0: FF 51 03 tt tt tt (microseconds per beat)
    mpqn = max(1, min(0xFFFFFF, int(round(60_000_000.0 / tempo_bpm))))
    track_body.extend(b"\x00\xff\x51\x03")
    track_body.extend(mpqn.to_bytes(3, "big"))

    last_time = 0
    for event_time, _, event_bytes in events:
        delta = max(0, event_time - last_time)
        track_body.extend(encode_vlq(delta))
        track_body.extend(event_bytes)
        last_time = event_time

    # End of Track meta-event: delta 0, FF 2F 00
    track_body.extend(b"\x00\xff\x2f\x00")

    # Track chunk: MTrk + length + track_body
    track_chunk = struct.pack(">4sI", b"MTrk", len(track_body)) + bytes(track_body)
    return header + track_chunk


def write_midi_file(
    notes: Sequence[Note],
    path: Path | str,
    ppq: int = DEFAULT_PPQ,
    tempo_bpm: float = 120.0,
) -> Path:
    """Export notes to a standard MIDI file (.mid) at the specified path."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    midi_data = encode_midi_bytes(notes=notes, ppq=ppq, tempo_bpm=tempo_bpm)
    dest.write_bytes(midi_data)
    return dest


def read_midi_notes(path: Path | str) -> tuple[int, list[Note]]:
    """Parse notes from an SMF Format 0 or Format 1 MIDI file.

    Returns:
        tuple of (ppq, list_of_Note_objects)
    """
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("Invalid MIDI file: missing MThd header")

    _, header_len, fmt, ntracks, ppq = struct.unpack(">4sIHHH", data[:14])
    offset = 8 + header_len

    notes: list[Note] = []
    # Key: (channel, pitch) -> list of (start_pos, velocity)
    active_notes: dict[tuple[int, int], list[tuple[int, float]]] = {}

    for _ in range(ntracks):
        if offset + 8 > len(data):
            break
        chunk_id, chunk_len = struct.unpack(">4sI", data[offset : offset + 8])
        offset += 8
        track_end = offset + chunk_len

        if chunk_id != b"MTrk":
            offset = track_end
            continue

        current_time = 0
        running_status: int | None = None

        while offset < track_end and offset < len(data):
            delta, offset = decode_vlq(data, offset)
            current_time += delta

            if offset >= len(data):
                break

            status_byte = data[offset]
            if status_byte & 0x80:
                running_status = status_byte
                offset += 1
            elif running_status is not None:
                status_byte = running_status
            else:
                raise ValueError(f"Corrupt MIDI data at offset {offset}")

            # Meta events
            if status_byte == 0xFF:
                if offset >= len(data):
                    break
                # meta_type = data[offset]
                offset += 1
                length, offset = decode_vlq(data, offset)
                offset += length
                continue

            # SysEx events
            if status_byte in (0xF0, 0xF7):
                length, offset = decode_vlq(data, offset)
                offset += length
                continue

            event_type = status_byte & 0xF0
            channel = status_byte & 0x0F

            if event_type == 0x90:  # Note-On
                pitch = data[offset]
                vel_byte = data[offset + 1]
                offset += 2
                vel = round(vel_byte / 127.0, 6)
                if vel_byte > 0:
                    active_notes.setdefault((channel, pitch), []).append((current_time, vel))
                else:
                    # Note-On with velocity 0 is Note-Off
                    pending = active_notes.get((channel, pitch), [])
                    if pending:
                        start_time, on_vel = pending.pop(0)
                        duration = max(1, current_time - start_time)
                        notes.append(
                            Note(
                                pos=start_time,
                                length=duration,
                                key=pitch,
                                velocity=on_vel,
                                color=channel,
                            )
                        )

            elif event_type == 0x80:  # Note-Off
                pitch = data[offset]
                rel_byte = data[offset + 1]
                offset += 2
                rel = round(rel_byte / 127.0, 6)
                pending = active_notes.get((channel, pitch), [])
                if pending:
                    start_time, on_vel = pending.pop(0)
                    duration = max(1, current_time - start_time)
                    notes.append(
                        Note(
                            pos=start_time,
                            length=duration,
                            key=pitch,
                            velocity=on_vel,
                            release=rel,
                            color=channel,
                        )
                    )

            elif event_type in (0xA0, 0xB0, 0xE0):
                offset += 2
            elif event_type in (0xC0, 0xD0):
                offset += 1

    notes.sort(key=lambda n: (n.pos, n.key))
    return ppq, notes
