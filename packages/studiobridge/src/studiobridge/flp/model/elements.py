"""High-level FLP object model element classes.

Implements typed representations of Channel, Plugin, Pattern, Note, MixerTrack,
Slot, PlaylistItem, Arrangement, Marker, and AutomationClip per
07_l0e_flp_engine.md §3.3, [FLP-20], and [FLP-21].
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from studiobridge.flp.codec.events import Event


@runtime_checkable
class Plugin(Protocol):
    """Protocol for FLP synthesizer and effect plugin models [FLP-20]."""

    data: bytes
    wrapper_kind: str
    name_hint: str
    source_events: list[int]

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin state to serializable dictionary."""
        ...


@dataclass
class OpaquePlugin:
    """Opaque plugin wrapper blob preserved without structured parameter decoding [FLP-20].

    Attributes:
        data: Raw binary plugin state wrapper blob.
        wrapper_kind: Kind of plugin wrapper
            (e.g. 'fruity_wrapper', 'vst2', 'vst3', 'clap', 'opaque').
        name_hint: Inferred or detected plugin display name.
        source_events: Indices of source FLP events contributing to this plugin state ([FLP-21]).
    """

    data: bytes = b""
    wrapper_kind: str = "opaque"
    name_hint: str = ""
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin to dictionary representation."""
        return {
            "wrapper_kind": self.wrapper_kind,
            "name_hint": self.name_hint,
            "data_len": len(self.data),
            "data_b64": (
                base64.b64encode(self.data[:256]).decode("ascii") + "..."
                if len(self.data) > 256
                else base64.b64encode(self.data).decode("ascii")
            ),
            "source_events": list(self.source_events),
        }


@dataclass
class Slot:
    """Mixer insert effect slot representation [FLP-20].

    Each mixer track in modern FL Studio contains 10 effect slots.

    Attributes:
        index: Zero-based slot index (0..9).
        plugin: Plugin loaded into this slot, or None if empty.
        enabled: True if slot effect is active / not bypassed.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    index: int
    plugin: Plugin | None = None
    enabled: bool = True
    source_events: list[int] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True if no plugin is loaded in this effect slot."""
        return self.plugin is None

    def to_dict(self) -> dict[str, Any]:
        """Convert slot to dictionary representation."""
        return {
            "index": self.index,
            "enabled": self.enabled,
            "plugin": self.plugin.to_dict() if self.plugin else None,
            "source_events": list(self.source_events),
        }


@dataclass
class Channel:
    """Channel rack generator or instrument channel representation [FLP-20].

    Attributes:
        index: Zero-based channel rack index.
        name: Channel display name.
        channel_type: Type of channel ('sampler', 'plugin', 'audio_clip', 'layer', 'automation').
        color: Optional RGB integer or hex color string.
        target_mixer_track: Output mixer insert track (0 = Master).
        volume: Normalized channel volume level (default 1.0 or 0.78).
        pan: Panning value (-1.0 to 1.0, 0.0 center).
        pitch: Pitch offset in cents.
        step_bits: Step sequencer grid bits (16 or 32 steps).
        plugin: Optional opaque plugin state wrapper reference.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    index: int
    name: str = ""
    channel_type: str = "sampler"
    color: int | str | None = None
    target_mixer_track: int = 0
    volume: float = 1.0
    pan: float = 0.0
    pitch: int = 0
    step_bits: list[int] = field(default_factory=list)
    plugin: Plugin | None = None
    source_events: list[int] = field(default_factory=list)

    @property
    def mixer_track(self) -> int:
        """Alias for target_mixer_track."""
        return self.target_mixer_track

    @mixer_track.setter
    def mixer_track(self, value: int) -> None:
        self.target_mixer_track = value

    def to_dict(self) -> dict[str, Any]:
        """Convert channel to dictionary representation."""
        return {
            "index": self.index,
            "name": self.name,
            "type": self.channel_type,
            "color": self.color,
            "target_mixer_track": self.target_mixer_track,
            "volume": round(self.volume, 4),
            "pan": round(self.pan, 4),
            "pitch": self.pitch,
            "step_bits": list(self.step_bits),
            "has_plugin": self.plugin is not None,
            "plugin": self.plugin.to_dict() if self.plugin else None,
            "source_events": list(self.source_events),
        }


@dataclass
class Note:
    """Musical note inside a pattern piano roll [FLP-20].

    Attributes:
        pos: Start position in PPQ ticks.
        len: Note duration in PPQ ticks.
        key: MIDI note key number (0–127, e.g. 60 = C5).
        velocity: Normalized velocity (0.0 to 1.0 or 0–127).
        pan: Panning (-1.0 left to 1.0 right, 0.0 center).
        release: Release velocity / time.
        fcut: Filter cutoff modifier.
        fres: Filter resonance modifier.
        group: Note group index.
        color: Note color index (0–15).
        slide: True if note is a portamento / slide note.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    pos: int = 0
    len: int = 96
    key: int = 60
    velocity: float = 0.78
    pan: float = 0.0
    release: int = 64
    fcut: float = 0.0
    fres: float = 0.0
    group: int = 0
    color: int | None = None
    slide: bool = False
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert note to dictionary representation."""
        return {
            "pos": self.pos,
            "len": self.len,
            "key": self.key,
            "velocity": round(self.velocity, 4),
            "pan": round(self.pan, 4),
            "release": self.release,
            "fcut": round(self.fcut, 4),
            "fres": round(self.fres, 4),
            "group": self.group,
            "color": self.color,
            "slide": self.slide,
            "source_events": list(self.source_events),
        }


@dataclass
class Pattern:
    """Arrangement pattern containing piano roll notes and step sequences [FLP-20].

    Attributes:
        number: 1-based pattern number.
        name: Pattern display name.
        color: Optional RGB integer or hex color.
        notes: Mapping of channel index -> list of Note instances.
        step_grid: Step sequencer data per channel index.
        length: Pattern length in ticks.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    number: int = 1
    name: str = ""
    color: int | str | None = None
    notes: dict[int, list[Note]] = field(default_factory=dict)
    step_grid: dict[int, list[int]] = field(default_factory=dict)
    length: int = 0
    source_events: list[int] = field(default_factory=list)

    @property
    def all_notes(self) -> list[Note]:
        """Return flattened list of all notes in this pattern across all channels."""
        res: list[Note] = []
        for n_list in self.notes.values():
            res.extend(n_list)
        res.sort(key=lambda n: n.pos)
        return res

    @property
    def total_notes(self) -> int:
        """Return total count of notes in this pattern."""
        return sum(len(nl) for nl in self.notes.values())

    def get_notes(self, channel_index: int) -> list[Note]:
        """Retrieve notes for a specific channel index."""
        return self.notes.get(channel_index, [])

    def set_notes(self, channel_index: int, notes: list[Note]) -> None:
        """Replace notes for a specific channel index."""
        self.notes[channel_index] = list(notes)

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern to dictionary representation."""
        return {
            "number": self.number,
            "name": self.name,
            "color": self.color,
            "length": self.length,
            "total_notes": self.total_notes,
            "channels_with_notes": list(self.notes.keys()),
            "notes": {ch: [n.to_dict() for n in n_list] for ch, n_list in self.notes.items()},
            "source_events": list(self.source_events),
        }


@dataclass
class MixerTrack:
    """Mixer insert track parameter state and effect slots [FLP-20].

    Attributes:
        index: Track index (0 = Master, 1..125 = Inserts).
        name: Track display name.
        color: Optional RGB integer or hex color.
        volume: Track fader volume level (0.0 to 1.0 or normalized).
        pan: Track stereo panning (-1.0 to 1.0).
        stereo_sep: Stereo separation parameter (-1.0 to 1.0).
        mute: True if track is muted.
        solo: True if track is soloed.
        routing: List of destination track indices this track sends audio to.
        slots: 10 effect insert slots.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    index: int = 0
    name: str = ""
    color: int | str | None = None
    volume: float = 1.0
    pan: float = 0.0
    stereo_sep: float = 0.0
    mute: bool = False
    solo: bool = False
    routing: list[int] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=lambda: [Slot(index=i) for i in range(10)])
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert mixer track to dictionary representation."""
        return {
            "index": self.index,
            "name": self.name,
            "color": self.color,
            "volume": round(self.volume, 4),
            "pan": round(self.pan, 4),
            "stereo_sep": round(self.stereo_sep, 4),
            "mute": self.mute,
            "solo": self.solo,
            "routing": list(self.routing),
            "slots": [s.to_dict() for s in self.slots if not s.is_empty],
            "total_slots": len(self.slots),
            "source_events": list(self.source_events),
        }


@dataclass
class PlaylistItem:
    """Timeline placement of a pattern, audio clip, or automation clip [FLP-20].

    Attributes:
        track: 1-based playlist lane track index.
        start: Start position in PPQ ticks.
        length: Item duration in PPQ ticks.
        pattern_index: Pattern index placed on timeline, if pattern item.
        clip_ref: Channel rack index if audio clip or automation clip item.
        flags: Raw bit flags (mute, stretch, offset).
        mute: True if item is muted on timeline.
        raw: Full binary record bytes as decoded by version profile layout.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    track: int = 1
    start: int = 0
    length: int = 0
    pattern_index: int | None = None
    clip_ref: int | None = None
    flags: int = 0
    mute: bool = False
    raw: bytes = b""
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert playlist item to dictionary representation."""
        return {
            "track": self.track,
            "start": self.start,
            "length": self.length,
            "pattern_index": self.pattern_index,
            "clip_ref": self.clip_ref,
            "flags": self.flags,
            "mute": self.mute,
            "raw_len": len(self.raw),
            "source_events": list(self.source_events),
        }


@dataclass
class Marker:
    """Timeline cue marker or time signature marker [FLP-20].

    Attributes:
        name: Marker name or label.
        position_ticks: Position in PPQ ticks.
        time_signature: Optional (numerator, denominator) tuple.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    name: str = ""
    position_ticks: int = 0
    time_signature: tuple[int, int] | None = None
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert marker to dictionary representation."""
        return {
            "name": self.name,
            "position_ticks": self.position_ticks,
            "time_signature": list(self.time_signature) if self.time_signature else None,
            "source_events": list(self.source_events),
        }


@dataclass
class AutomationClip:
    """Automation envelope clip parameter representation [FLP-20].

    Attributes:
        name: Clip name.
        channel_index: Target channel rack index.
        points: Envelope curve points (position_ticks, normalized_value).
        link_target: Target parameter name or description (best-effort).
        source_events: Indices of source FLP events ([FLP-21]).
    """

    name: str = ""
    channel_index: int | None = None
    points: list[tuple[int, float]] = field(default_factory=list)
    link_target: str | None = None
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert automation clip to dictionary representation."""
        return {
            "name": self.name,
            "channel_index": self.channel_index,
            "point_count": len(self.points),
            "points": [(pos, round(val, 4)) for pos, val in self.points],
            "link_target": self.link_target,
            "source_events": list(self.source_events),
        }


@dataclass
class Arrangement:
    """Playlist arrangement containing tracks, placed clips, and markers [FLP-20].

    Attributes:
        name: Arrangement name ('Default', etc.).
        tracks: Metadata for playlist track lanes.
        items: List of PlaylistItem placement records.
        markers: Timeline position markers.
        time_signatures: Time signature change markers.
        source_events: Indices of source FLP events ([FLP-21]).
    """

    name: str = "Default"
    tracks: list[dict[str, Any]] = field(default_factory=list)
    items: list[PlaylistItem] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    time_signatures: list[Marker] = field(default_factory=list)
    source_events: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert arrangement to dictionary representation."""
        return {
            "name": self.name,
            "item_count": len(self.items),
            "items": [it.to_dict() for it in self.items],
            "marker_count": len(self.markers),
            "markers": [m.to_dict() for m in self.markers],
            "time_signatures": [m.to_dict() for m in self.time_signatures],
            "source_events": list(self.source_events),
        }


@dataclass(frozen=True, slots=True)
class UnmodeledEvent:
    """An event retained in the opaque tail list with byte position [FLP-20].

    Preserves lossless round-trip and non-modeled vendor parameters without loss.

    Attributes:
        event_index: Index in the source EventChunk.events stream.
        byte_position: Approximate or exact byte position in the container.
        event: The underlying Event instance.
    """

    event_index: int
    byte_position: int | None
    event: Event

    def to_dict(self) -> dict[str, Any]:
        """Convert unmodeled event to dictionary representation."""
        return {
            "event_index": self.event_index,
            "byte_position": self.byte_position,
            "event_id": self.event.id,
            "kind": self.event.kind.value,
            "raw_len": len(self.event.raw),
        }
