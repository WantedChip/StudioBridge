"""FLP Project root model and typed deserialization loader.

Implements Project per 07_l0e_flp_engine.md §3.3, 09_l1_sdk.md §1–§2,
[FLP-20] (opaque tail list for unmodeled events), and [FLP-21] (source event handles).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from studiobridge.flp.codec.events import EventKind, encode_varint
from studiobridge.flp.codec.reader import FlpFile, parse
from studiobridge.flp.model.elements import (
    Arrangement,
    AutomationClip,
    Channel,
    MixerTrack,
    Note,
    OpaquePlugin,
    Pattern,
    PlaylistItem,
    UnmodeledEvent,
)
from studiobridge.flp.schema.profile import (
    VersionProfile,
    decode_playlist_items,
    decode_track_data,
)
from studiobridge.flp.schema.resolver import resolve_profile
from studiobridge.flp.schema.text import decode_text, decode_version_string

if TYPE_CHECKING:
    from studiobridge.flp.diff import ProjectDiff


@dataclass
class Project:
    """High-level typed representation of an FL Studio project (.flp) [FLP-20].

    Maintains lossless event handles ([FLP-21]) and retains unmodeled events
    in an opaque tail list with byte positions ([FLP-20]).
    """

    title: str = ""
    author: str = ""
    comments: str = ""
    tempo: float = 120.0
    fine_tempo: float = 120.0
    ppq: int = 96
    version: str = "26.1.0"
    licensed: bool = False
    channels: list[Channel] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    mixer: list[MixerTrack] = field(default_factory=list)
    arrangement: Arrangement = field(default_factory=Arrangement)
    automation_clips: list[AutomationClip] = field(default_factory=list)
    unmodeled_events: list[UnmodeledEvent] = field(default_factory=list)
    source_file: FlpFile | None = None
    profile: VersionProfile | None = None

    @classmethod
    def load(cls, path_or_bytes: Path | str | bytes) -> Project:
        """Load and hydrate a Project object model from an FLP file or raw bytes [FLP-20]."""
        if isinstance(path_or_bytes, bytes):
            flp_file = parse(path_or_bytes)
        else:
            flp_file = parse(Path(path_or_bytes))

        return cls._hydrate(flp_file)

    @classmethod
    def _hydrate(cls, flp_file: FlpFile) -> Project:
        """Construct typed object model from parsed FlpFile event stream [FLP-20, FLP-21]."""
        res = resolve_profile(flp_file.events)
        profile = res.profile
        version = res.version

        # Compute exact event byte offsets within FLdt payload for unmodeled events ([FLP-20])
        event_offsets: dict[int, int] = {}
        curr_offset = 0
        for i, ev in enumerate(flp_file.events):
            event_offsets[i] = curr_offset
            id_size = 1
            if ev.kind == EventKind.VARIABLE:
                varint_len = len(ev.enc.raw) if ev.enc else len(encode_varint(len(ev.raw)))
            else:
                varint_len = 0
            payload_len = len(ev.raw)
            curr_offset += id_size + varint_len + payload_len

        # Metadata
        title: str = ""
        author: str = ""
        comments: str = ""
        main_tempo: float = 120.0
        fine_tempo_val: float = 120.0
        has_fine_tempo: bool = False
        ppq: int = flp_file.header.ppq if flp_file.header else 96
        licensed: bool = False

        channels: list[Channel] = []
        patterns: dict[int, Pattern] = {}
        mixer: list[MixerTrack] = [
            MixerTrack(index=i, name="Master" if i == 0 else f"Insert {i}") for i in range(126)
        ]
        arrangement = Arrangement()
        automation_clips: list[AutomationClip] = []
        consumed_indices: set[int] = set()

        current_channel: Channel | None = None
        current_pattern: Pattern | None = None

        text_encoding = profile.text_encoding.default_encoding

        for i, ev in enumerate(flp_file.events):
            # 1. Version string (199)
            if ev.id == 199:
                consumed_indices.add(i)
                v_str = decode_version_string(ev.raw)
                if v_str:
                    version = v_str

            # 2. Main tempo (68)
            elif ev.id == 68 and len(ev.raw) >= 2:
                consumed_indices.add(i)
                t_val = struct.unpack("<H", ev.raw[:2])[0]
                main_tempo = float(t_val)
                if not has_fine_tempo:
                    fine_tempo_val = main_tempo

            # 3. Fine tempo (156)
            elif ev.id == 156 and len(ev.raw) >= 4:
                consumed_indices.add(i)
                raw_int = struct.unpack("<I", ev.raw[:4])[0]
                fine_tempo_val = raw_int / 1000.0 if raw_int > 1000 else float(raw_int)
                has_fine_tempo = True

            # 4. Project title (201)
            elif ev.id == 201:
                consumed_indices.add(i)
                title = decode_text(ev.raw, encoding=text_encoding)

            # 5. Comments (202)
            elif ev.id == 202:
                consumed_indices.add(i)
                comments = decode_text(ev.raw, encoding=text_encoding)

            # 6. Author / Registration info (203, 212)
            elif ev.id in (203, 212):
                consumed_indices.add(i)
                author_txt = decode_text(ev.raw, encoding=text_encoding)
                if ev.id == 212 and author_txt:
                    author = author_txt
                    licensed = True
                elif not author:
                    author = author_txt

            # 7. Channel rack creation (64 - NewChan)
            elif ev.id == 64:
                consumed_indices.add(i)
                ch_idx = len(channels)
                current_channel = Channel(
                    index=ch_idx,
                    name=f"Channel {ch_idx + 1}",
                    source_events=[i],
                )
                channels.append(current_channel)

            # 8. Channel name (200 - Text/ChannelName)
            elif ev.id == 200:
                if current_channel is not None:
                    consumed_indices.add(i)
                    current_channel.name = decode_text(ev.raw, encoding=text_encoding)
                    current_channel.source_events.append(i)

            # 9. Plugin wrapper data (213)
            elif ev.id == 213:
                if current_channel is not None:
                    consumed_indices.add(i)
                    plugin = OpaquePlugin(
                        data=ev.raw,
                        wrapper_kind="fruity_wrapper",
                        name_hint=current_channel.name,
                        source_events=[i],
                    )
                    current_channel.plugin = plugin
                    current_channel.channel_type = "plugin"
                    current_channel.source_events.append(i)

            # 10. Channel parameters (215)
            elif ev.id == 215:
                if current_channel is not None:
                    consumed_indices.add(i)
                    current_channel.source_events.append(i)

            # 11. Pattern selector (65 - NewPat)
            elif ev.id == 65:
                consumed_indices.add(i)
                pat_num = ev.as_int()
                if pat_num <= 0:
                    pat_num = len(patterns) + 1
                if pat_num not in patterns:
                    patterns[pat_num] = Pattern(
                        number=pat_num,
                        name=f"Pattern {pat_num}",
                        source_events=[i],
                    )
                else:
                    patterns[pat_num].source_events.append(i)
                current_pattern = patterns[pat_num]

            # 12. Playlist timeline items (224)
            elif ev.id == 224:
                consumed_indices.add(i)
                arrangement.source_events.append(i)
                item_records = decode_playlist_items(ev.raw, profile)
                for rec in item_records:
                    p_item = PlaylistItem(
                        track=rec.track_index if rec.track_index is not None else 1,
                        start=rec.start_time if rec.start_time is not None else 0,
                        length=rec.length if rec.length is not None else 0,
                        pattern_index=rec.pattern_index,
                        flags=rec.flags if rec.flags is not None else 0,
                        raw=rec.raw,
                        source_events=[i],
                    )
                    arrangement.items.append(p_item)

            # 13. Mixer track parameters (238)
            elif ev.id == 238:
                consumed_indices.add(i)
                t_rec = decode_track_data(ev.raw, profile)
                t_idx = t_rec.track_index if t_rec.track_index is not None else 0
                if 0 <= t_idx < len(mixer):
                    mixer[t_idx].source_events.append(i)

            # 14. Pattern note events (225, 226, 227, 240)
            elif ev.id in (225, 226, 227, 240) and current_pattern is not None:
                # Unpack fixed-record note sequences if payload matches standard layout
                note_rec_size = None
                if len(ev.raw) >= 20 and len(ev.raw) % 20 == 0:
                    note_rec_size = 20
                elif len(ev.raw) >= 24 and len(ev.raw) % 24 == 0:
                    note_rec_size = 24

                if note_rec_size is not None:
                    consumed_indices.add(i)
                    current_pattern.source_events.append(i)
                    ch_key = current_channel.index if current_channel else 0
                    if ch_key not in current_pattern.notes:
                        current_pattern.notes[ch_key] = []

                    count = len(ev.raw) // note_rec_size
                    for k in range(count):
                        n_chunk = ev.raw[k * note_rec_size : (k + 1) * note_rec_size]
                        pos, n_len = struct.unpack_from("<II", n_chunk, 0)
                        key = struct.unpack_from("<H", n_chunk, 8)[0] % 128
                        pan_b = n_chunk[12] if len(n_chunk) > 12 else 64
                        vel_b = n_chunk[13] if len(n_chunk) > 13 else 100
                        rel_b = n_chunk[14] if len(n_chunk) > 14 else 64

                        note_obj = Note(
                            pos=pos,
                            len=n_len,
                            key=key,
                            velocity=round(vel_b / 127.0, 4),
                            pan=round((pan_b - 64) / 64.0, 4),
                            release=rel_b,
                            source_events=[i],
                        )
                        current_pattern.notes[ch_key].append(note_obj)

        # Reconcile channel rack count from FLhd header chunk
        header_channels = flp_file.header.channels if flp_file.header else 0
        if header_channels > len(channels):
            for extra_idx in range(len(channels), header_channels):
                channels.append(Channel(index=extra_idx, name=f"Channel {extra_idx + 1}"))

        # Default pattern if none defined
        if not patterns:
            patterns[1] = Pattern(number=1, name="Pattern 1")

        sorted_patterns = [patterns[k] for k in sorted(patterns.keys())]

        # Retain unmodeled events in an opaque tail list with byte positions ([FLP-20])
        unmodeled: list[UnmodeledEvent] = []
        for i, ev in enumerate(flp_file.events):
            if i not in consumed_indices:
                unmodeled.append(
                    UnmodeledEvent(
                        event_index=i,
                        byte_position=event_offsets.get(i),
                        event=ev,
                    )
                )

        final_tempo = fine_tempo_val if has_fine_tempo else main_tempo

        return cls(
            title=title,
            author=author,
            comments=comments,
            tempo=final_tempo,
            fine_tempo=fine_tempo_val,
            ppq=ppq,
            version=version,
            licensed=licensed,
            channels=channels,
            patterns=sorted_patterns,
            mixer=mixer,
            arrangement=arrangement,
            automation_clips=automation_clips,
            unmodeled_events=unmodeled,
            source_file=flp_file,
            profile=profile,
        )

    def channel(self, index: int) -> Channel:
        """Retrieve channel by rack index."""
        if 0 <= index < len(self.channels):
            return self.channels[index]
        raise IndexError(f"Channel index {index} out of range (0..{len(self.channels) - 1})")

    def pattern(self, number: int) -> Pattern:
        """Retrieve pattern by 1-based number."""
        for pat in self.patterns:
            if pat.number == number:
                return pat
        raise KeyError(f"Pattern number {number} not found in project")

    def mixer_track(self, index: int) -> MixerTrack:
        """Retrieve mixer track by index (0 = Master, 1..125 = Inserts)."""
        if 0 <= index < len(self.mixer):
            return self.mixer[index]
        raise IndexError(f"Mixer track index {index} out of range (0..{len(self.mixer) - 1})")

    def info(self) -> dict[str, Any]:
        """Return standardized project inspection summary dictionary per 07 §8."""
        return {
            "version": self.version,
            "title": self.title,
            "author": self.author,
            "comments": self.comments,
            "tempo": round(self.tempo, 4),
            "fine_tempo": round(self.fine_tempo, 4),
            "ppq": self.ppq,
            "licensed": self.licensed,
            "channel_count": len(self.channels),
            "channels": [c.name for c in self.channels],
            "pattern_count": len(self.patterns),
            "patterns": [p.name for p in self.patterns],
            "mixer_track_count": len(self.mixer),
            "playlist_item_count": len(self.arrangement.items),
            "unmodeled_event_count": len(self.unmodeled_events),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return full serializable dictionary representation of the project."""
        return {
            "metadata": {
                "version": self.version,
                "title": self.title,
                "author": self.author,
                "comments": self.comments,
                "tempo": round(self.tempo, 4),
                "fine_tempo": round(self.fine_tempo, 4),
                "ppq": self.ppq,
                "licensed": self.licensed,
            },
            "channels": [c.to_dict() for c in self.channels],
            "patterns": [p.to_dict() for p in self.patterns],
            "mixer": [
                m.to_dict()
                for m in self.mixer
                if m.name != f"Insert {m.index}" or m.index == 0 or m.slots or m.source_events
            ],
            "arrangement": self.arrangement.to_dict(),
            "automation_clips": [ac.to_dict() for ac in self.automation_clips],
            "unmodeled_events_count": len(self.unmodeled_events),
        }

    @classmethod
    def diff(cls, a: str | Path | Project, b: str | Path | Project) -> ProjectDiff:
        """Compare two projects and return a ProjectDiff report per 07 §8."""
        from studiobridge.flp.diff import diff_projects

        proj_a = a if isinstance(a, Project) else cls.load(a)
        proj_b = b if isinstance(b, Project) else cls.load(b)
        return diff_projects(proj_a, proj_b)
