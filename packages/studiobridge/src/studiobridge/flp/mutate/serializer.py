"""FLP project re-serialization with partial re-serialization and untouched preservation.

Implements clean-room re-serialization per 07_l0e_flp_engine.md §3.3, §3.4,
[FLP-05], and [FLP-21] (lossless byte preservation for untouched elements).
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from studiobridge.flp.codec.events import Event
from studiobridge.flp.codec.reader import (
    EventChunk,
    FlpFile,
    FlpHeader,
    HeaderChunk,
)
from studiobridge.flp.schema.resolver import resolve_profile
from studiobridge.flp.schema.text import encode_text

if TYPE_CHECKING:
    from studiobridge.flp.model.elements import Note
    from studiobridge.flp.model.project import Project
    from studiobridge.flp.mutate.mutator import ProjectMutator


def _encode_notes(notes: list[Note]) -> bytes:
    """Encode notes list into standard 20-byte FL Studio piano roll note records."""
    buf = bytearray()
    for n in notes:
        rec = bytearray(20)
        vel_b = int(round(n.velocity * 127)) if n.velocity <= 1.0 else int(round(n.velocity))
        vel_b = max(0, min(127, vel_b))
        pan_b = int(round(n.pan * 64 + 64))
        pan_b = max(0, min(127, pan_b))
        rel_b = max(0, min(127, int(n.release)))
        key_num = max(0, min(127, int(n.key)))
        struct.pack_into("<II", rec, 0, int(n.pos), int(n.len))
        struct.pack_into("<HH", rec, 8, key_num, 0)
        struct.pack_into("<BBBB", rec, 12, pan_b, vel_b, rel_b, int(n.group))
        buf.extend(rec)
    return bytes(buf)


def serialize_project(
    project: Project,
    mutator: ProjectMutator | None = None,
) -> FlpFile:
    """Serialize Project to an FlpFile, preserving exact untouched bytes [FLP-21].

    Args:
        project: Project object model instance.
        mutator: Optional ProjectMutator tracking touched elements.

    Returns:
        FlpFile container ready for binary serialization.
    """
    profile = project.profile
    if profile is None:
        profile = resolve_profile(project.version).profile

    encoding = profile.text_encoding.default_encoding

    # -------------------------------------------------------------------------
    # Case 1: Fresh project constructed programmatically (no source_file)
    # -------------------------------------------------------------------------
    if project.source_file is None:
        events: list[Event] = []

        # Version string (199)
        v_bytes = project.version.encode("ascii") + b"\x00"
        events.append(Event(id=199, raw=v_bytes))

        # Main tempo (68) and fine tempo (156)
        events.append(Event(id=68, raw=struct.pack("<H", int(project.tempo))))
        events.append(Event(id=156, raw=struct.pack("<I", int(project.fine_tempo * 1000))))

        # Metadata text
        if project.title:
            events.append(Event(id=201, raw=encode_text(project.title, encoding=encoding)))
        if project.author:
            events.append(Event(id=212, raw=encode_text(project.author, encoding=encoding)))
        if project.comments:
            events.append(Event(id=202, raw=encode_text(project.comments, encoding=encoding)))

        # Channels
        for ch in project.channels:
            events.append(Event(id=64, raw=struct.pack("<H", ch.index)))
            events.append(Event(id=200, raw=encode_text(ch.name, encoding=encoding)))
            if ch.plugin is not None:
                events.append(Event(id=213, raw=ch.plugin.data))
            events.append(Event(id=215, raw=b"\x00" * 32))

        # Patterns
        for pat in project.patterns:
            events.append(Event(id=65, raw=struct.pack("<H", pat.number)))
            events.append(Event(id=200, raw=encode_text(pat.name, encoding=encoding)))
            all_pat_notes = pat.all_notes
            if all_pat_notes:
                events.append(Event(id=226, raw=_encode_notes(all_pat_notes)))

        # Playlist items
        if project.arrangement.items:
            item_size = profile.struct_layouts.playlist_item_size
            payload = bytearray(len(project.arrangement.items) * item_size)
            for idx, it in enumerate(project.arrangement.items):
                offset = idx * item_size
                if it.raw and len(it.raw) == item_size:
                    payload[offset : offset + item_size] = it.raw
                    struct.pack_into("<II", payload, offset, int(it.start), int(it.length))
                    struct.pack_into("<I", payload, offset + 8, int(it.track))
                else:
                    struct.pack_into(
                        "<IIII",
                        payload,
                        offset,
                        int(it.start),
                        int(it.length),
                        int(it.track),
                        int(it.pattern_index or 1),
                    )
            events.append(Event(id=224, raw=bytes(payload)))

        header = FlpHeader(format=0, channels=len(project.channels), ppq=project.ppq)
        return FlpFile(
            header=header,
            events=events,
            chunks=[HeaderChunk(header=header), EventChunk(events=events)],
        )

    # -------------------------------------------------------------------------
    # Case 2: Project loaded from source file (preserve untouched events) [FLP-21]
    # -------------------------------------------------------------------------
    orig_events = project.source_file.events

    # Collect touched element sets
    touched_meta = mutator.touched_metadata if mutator is not None else set()
    touched_ch = mutator.touched_channels if mutator is not None else set()
    touched_pat = mutator.touched_patterns if mutator is not None else set()
    touched_playlist = mutator.touched_playlist if mutator is not None else False

    # Build event mapping: index -> Event | None (None indicates dropped)
    event_map: dict[int, Event | None] = {}
    for i, ev in enumerate(orig_events):
        event_map[i] = ev

    # 1. Metadata updates
    for i, ev in enumerate(orig_events):
        if ev.id == 68 and ("tempo" in touched_meta or mutator is None):
            event_map[i] = Event(id=68, raw=struct.pack("<H", int(project.tempo)))
        elif ev.id == 156 and ("tempo" in touched_meta or mutator is None):
            event_map[i] = Event(id=156, raw=struct.pack("<I", int(project.fine_tempo * 1000)))
        elif ev.id == 201 and ("title" in touched_meta or mutator is None):
            event_map[i] = Event(id=201, raw=encode_text(project.title, encoding=encoding))
        elif ev.id in (203, 212) and ("author" in touched_meta or mutator is None):
            event_map[i] = Event(id=ev.id, raw=encode_text(project.author, encoding=encoding))
        elif ev.id == 202 and ("comments" in touched_meta or mutator is None):
            event_map[i] = Event(id=202, raw=encode_text(project.comments, encoding=encoding))

    # 2. Channel updates (only touched channels)
    for ch in project.channels:
        if ch.index in touched_ch:
            for ev_idx in ch.source_events:
                if 0 <= ev_idx < len(orig_events):
                    ev = orig_events[ev_idx]
                    if ev.id == 200:  # Channel name
                        event_map[ev_idx] = Event(
                            id=200,
                            raw=encode_text(ch.name, encoding=encoding),
                        )

    # 3. Pattern updates (only touched patterns)
    for pat in project.patterns:
        if pat.number in touched_pat:
            note_events_for_pat = [
                idx
                for idx in pat.source_events
                if 0 <= idx < len(orig_events) and orig_events[idx].id in (225, 226, 227, 240)
            ]
            # Replace first note event with updated notes; drop remainder
            all_pat_notes = pat.all_notes
            new_note_bytes = _encode_notes(all_pat_notes) if all_pat_notes else b""

            if note_events_for_pat:
                first_idx = note_events_for_pat[0]
                if new_note_bytes:
                    event_map[first_idx] = Event(id=226, raw=new_note_bytes)
                else:
                    event_map[first_idx] = None  # Notes cleared
                for drop_idx in note_events_for_pat[1:]:
                    event_map[drop_idx] = None

            # Check pattern name update
            for ev_idx in pat.source_events:
                if 0 <= ev_idx < len(orig_events):
                    ev = orig_events[ev_idx]
                    if ev.id in (200, 204):
                        event_map[ev_idx] = Event(
                            id=ev.id,
                            raw=encode_text(pat.name, encoding=encoding),
                        )

    # 4. Playlist updates (only if touched)
    if touched_playlist:
        item_size = profile.struct_layouts.playlist_item_size
        payload = bytearray(len(project.arrangement.items) * item_size)
        for idx, it in enumerate(project.arrangement.items):
            offset = idx * item_size
            if it.raw and len(it.raw) == item_size:
                payload[offset : offset + item_size] = it.raw
                struct.pack_into("<II", payload, offset, int(it.start), int(it.length))
                struct.pack_into("<I", payload, offset + 8, int(it.track))
            else:
                struct.pack_into(
                    "<IIII",
                    payload,
                    offset,
                    int(it.start),
                    int(it.length),
                    int(it.track),
                    int(it.pattern_index or 1),
                )

        for ev_idx in project.arrangement.source_events:
            if 0 <= ev_idx < len(orig_events) and orig_events[ev_idx].id == 224:
                event_map[ev_idx] = Event(id=224, raw=bytes(payload))

    # Assemble output events list from event_map
    out_events: list[Event] = []
    for i in range(len(orig_events)):
        ev_item = event_map.get(i)
        if ev_item is not None:
            out_events.append(ev_item)

    # Handle newly added channels that do not exist in orig_events
    for ch in project.channels:
        if not ch.source_events or all(ev_idx >= len(orig_events) for ev_idx in ch.source_events):
            if getattr(ch, "_fragment_events", None):
                out_events.extend(ch._fragment_events)
            else:
                out_events.append(Event(id=64, raw=struct.pack("<H", ch.index)))
                out_events.append(Event(id=200, raw=encode_text(ch.name, encoding=encoding)))
                if ch.plugin is not None:
                    out_events.append(Event(id=213, raw=ch.plugin.data))
                out_events.append(Event(id=215, raw=b"\x00" * 32))

    # Handle newly added patterns that do not exist in source_events
    for pat in project.patterns:
        if not pat.source_events:
            out_events.append(Event(id=65, raw=struct.pack("<H", pat.number)))
            out_events.append(Event(id=200, raw=encode_text(pat.name, encoding=encoding)))
            if pat.total_notes > 0:
                out_events.append(Event(id=226, raw=_encode_notes(pat.all_notes)))

    # Update header channel count ([FLP-05])
    header = project.source_file.header
    header.channels = len(project.channels)
    header.ppq = project.ppq

    # Update chunks
    new_chunks = []
    for chunk in project.source_file.chunks:
        if isinstance(chunk, HeaderChunk):
            new_chunks.append(HeaderChunk(header=header, padding=chunk.padding))
        elif isinstance(chunk, EventChunk):
            new_chunks.append(EventChunk(events=out_events, padding=chunk.padding))
        else:
            new_chunks.append(chunk)

    return FlpFile(
        header=header,
        events=out_events,
        chunks=new_chunks,
        trailing_bytes=project.source_file.trailing_bytes,
    )
