"""FLP version-specific structural profiles, record layouts, and payload decoders.

Defines schemas and layout models for FL Studio 26 and backward-compatible profiles
for FL 21–25, clean-room provenance, and [FLP-10].
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.flp.schema.loader import load_yaml_file

PROFILES_DIR: Path = Path(__file__).parent / "profiles"


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a version string (e.g. '26.1.0.1234', '21.0.3') into an integer tuple.

    Ignores non-numeric suffixes or build hashes.
    """
    if not version_str:
        return (0,)
    # Extract digit sequences separated by dots
    parts = re.findall(r"\d+", version_str)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def _compare_version(v: tuple[int, ...], target: tuple[int, ...]) -> int:
    """Compare two version tuples of potentially differing lengths."""
    max_len = max(len(v), len(target))
    v_norm = v + (0,) * (max_len - len(v))
    target_norm = target + (0,) * (max_len - len(target))
    if v_norm < target_norm:
        return -1
    if v_norm > target_norm:
        return 1
    return 0


@dataclass(frozen=True, slots=True)
class StructLayouts:
    """Version-specific structural record sizes and event ID mappings [FLP-10]."""

    playlist_item_size: int
    track_data_size: int
    event_ids: dict[str, int] = field(default_factory=dict)
    playlist_item_offsets: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventMeaning:
    """Semantic meaning, payload type, and category of an FLP event [FLP-10]."""

    id: int
    name: str
    category: str
    kind: str
    type: str
    description: str = ""
    record_size: int | None = None
    payload_effective_size: int | None = None


@dataclass(frozen=True, slots=True)
class TextEncodingConfig:
    """Text encoding preferences and fallbacks for a version profile [FLP-06]."""

    default_encoding: str = "utf-16-le"
    fallback_encoding: str = "latin1"
    null_terminated: bool = True


@dataclass(frozen=True, slots=True)
class PlaylistItemRecord:
    """A decoded playlist timeline item (pattern or clip placement) [FLP-10]."""

    record_index: int
    offset: int
    raw: bytes
    start_time: int | None = None
    length: int | None = None
    track_index: int | None = None
    pattern_index: int | None = None
    flags: int | None = None


@dataclass(frozen=True, slots=True)
class TrackDataRecord:
    """A decoded mixer track parameters record [FLP-10]."""

    size: int
    raw: bytes
    track_index: int | None = None
    volume: float | None = None
    pan: float | None = None


@dataclass
class VersionProfile:
    """Complete version profile model for FL Studio project files [FLP-10].

    Stores version range, struct layouts, event meanings, text encoding,
    known quirks, and fixture expectations.
    """

    id: str
    name: str
    min_version: str
    max_version: str
    struct_layouts: StructLayouts
    event_meanings: dict[int, EventMeaning]
    text_encoding: TextEncodingConfig
    known_quirks: dict[str, str] = field(default_factory=dict)
    expectations: dict[str, Any] = field(default_factory=dict)

    min_version_tuple: tuple[int, ...] = field(init=False)
    max_version_tuple: tuple[int, ...] = field(init=False)

    def __post_init__(self) -> None:
        self.min_version_tuple = parse_version_tuple(self.min_version)
        self.max_version_tuple = parse_version_tuple(self.max_version)

    def matches_version(self, version: str | tuple[int, ...]) -> bool:
        """Check if a project version falls within this profile's supported range."""
        v_tuple = version if isinstance(version, tuple) else parse_version_tuple(version)
        return (
            _compare_version(v_tuple, self.min_version_tuple) >= 0
            and _compare_version(v_tuple, self.max_version_tuple) <= 0
        )

    def get_event_meaning(self, event_id: int) -> EventMeaning | None:
        """Retrieve semantic meaning definition for an event ID."""
        return self.event_meanings.get(event_id)

    @classmethod
    def from_dict(cls, data: dict[str | int, Any]) -> VersionProfile:
        """Construct a VersionProfile instance from parsed dictionary data."""
        p_id = str(data.get("id", "unknown"))
        name = str(data.get("name", p_id))

        v_range = data.get("fl_version_range", {})
        min_v = str(v_range.get("min_version", "0.0.0"))
        max_v = str(v_range.get("max_version", "99.99.99"))

        layouts_data = data.get("struct_layouts", {})
        struct_layouts = StructLayouts(
            playlist_item_size=int(layouts_data.get("playlist_item_size", 88)),
            track_data_size=int(layouts_data.get("track_data_size", 70)),
            event_ids={str(k): int(v) for k, v in layouts_data.get("event_ids", {}).items()},
            playlist_item_offsets={
                str(k): int(v) for k, v in layouts_data.get("playlist_item_offsets", {}).items()
            },
        )

        meanings: dict[int, EventMeaning] = {}
        meanings_raw = data.get("event_meanings", {})
        for k, v in meanings_raw.items():
            try:
                ev_id = int(k)
            except (ValueError, TypeError):
                continue
            if isinstance(v, dict):
                meanings[ev_id] = EventMeaning(
                    id=ev_id,
                    name=str(v.get("name", f"event_{ev_id}")),
                    category=str(v.get("category", "unclassified")),
                    kind=str(v.get("kind", "variable")),
                    type=str(v.get("type", "unknown")),
                    description=str(v.get("description", "")),
                    record_size=int(v["record_size"]) if "record_size" in v else None,
                    payload_effective_size=(
                        int(v["payload_effective_size"]) if "payload_effective_size" in v else None
                    ),
                )

        enc_data = data.get("text_encoding", {})
        text_encoding = TextEncodingConfig(
            default_encoding=str(enc_data.get("default_encoding", "utf-16-le")),
            fallback_encoding=str(enc_data.get("fallback_encoding", "latin1")),
            null_terminated=bool(enc_data.get("null_terminated", True)),
        )

        quirks = {str(k): str(v) for k, v in data.get("known_quirks", {}).items()}
        expectations = dict(data.get("expectations", {}))

        return cls(
            id=p_id,
            name=name,
            min_version=min_v,
            max_version=max_v,
            struct_layouts=struct_layouts,
            event_meanings=meanings,
            text_encoding=text_encoding,
            known_quirks=quirks,
            expectations=expectations,
        )


def decode_playlist_items(
    payload: bytes,
    profile_or_size: VersionProfile | int = 88,
) -> list[PlaylistItemRecord]:
    """Decode an event 224 (playlist items) payload into structured item records [FLP-10].

    Guarantees exact record offsets:
    - 88 bytes for FL Studio 26.x
    - 80 bytes for FL Studio 21–25
    - 60 bytes for FL Studio 12–20
    - 32 bytes for legacy versions
    """
    if isinstance(profile_or_size, VersionProfile):
        record_size = profile_or_size.struct_layouts.playlist_item_size
    else:
        record_size = int(profile_or_size)

    if record_size <= 0:
        raise ValueError(f"Playlist item record size must be positive, got {record_size}")

    records: list[PlaylistItemRecord] = []
    total_len = len(payload)
    count = total_len // record_size

    for i in range(count):
        offset = i * record_size
        chunk = payload[offset : offset + record_size]

        start_time: int | None = None
        length: int | None = None
        track_idx: int | None = None
        pat_idx: int | None = None
        flags: int | None = None

        if len(chunk) >= 8:
            start_time, length = struct.unpack_from("<II", chunk, 0)
        if len(chunk) >= 12:
            track_idx = struct.unpack_from("<I", chunk, 8)[0]
        if len(chunk) >= 16:
            pat_idx = struct.unpack_from("<I", chunk, 12)[0]
        if len(chunk) >= 20:
            flags = struct.unpack_from("<I", chunk, 16)[0]

        records.append(
            PlaylistItemRecord(
                record_index=i,
                offset=offset,
                raw=chunk,
                start_time=start_time,
                length=length,
                track_index=track_idx,
                pattern_index=pat_idx,
                flags=flags,
            )
        )

    return records


def decode_track_data(
    payload: bytes,
    profile_or_size: VersionProfile | int = 70,
) -> TrackDataRecord:
    """Decode an event 238 (track data) mixer insert record [FLP-10].

    Handles version-specific payload lengths:
    - 70 bytes for FL Studio 26.x
    - 66 bytes for FL Studio 24–25
    - 61 bytes for FL Studio 21.x
    """
    size = len(payload)
    track_idx: int | None = None

    if size >= 4:
        track_idx = struct.unpack_from("<I", payload, 0)[0]

    return TrackDataRecord(
        size=size,
        raw=payload,
        track_index=track_idx,
    )


# Catalog of builtin profiles
_BUILTIN_PROFILES: dict[str, VersionProfile] | None = None


def load_builtin_profiles() -> dict[str, VersionProfile]:
    """Load and cache built-in version profiles from yaml files."""
    global _BUILTIN_PROFILES
    if _BUILTIN_PROFILES is not None:
        return _BUILTIN_PROFILES

    profiles: dict[str, VersionProfile] = {}
    if PROFILES_DIR.is_dir():
        for yaml_path in PROFILES_DIR.glob("*.yaml"):
            try:
                data = load_yaml_file(yaml_path)
                profile = VersionProfile.from_dict(data)
                profiles[profile.id] = profile
            except Exception:
                pass

    _BUILTIN_PROFILES = profiles
    return _BUILTIN_PROFILES


def get_profile_by_id(profile_id: str) -> VersionProfile:
    """Retrieve a built-in version profile by its identifier (e.g. 'fl26', 'fl21_25')."""
    profiles = load_builtin_profiles()
    if profile_id not in profiles:
        raise KeyError(
            f"Profile '{profile_id}' not found. Available profiles: {list(profiles.keys())}"
        )
    return profiles[profile_id]
