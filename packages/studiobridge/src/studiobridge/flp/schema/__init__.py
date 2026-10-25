"""FLP version profiles, struct schemas, text decoders, and compatibility resolver."""

from __future__ import annotations

from studiobridge.core.errors import FlpVersionUnsupportedError
from studiobridge.flp.schema.loader import load_yaml_file, parse_yaml_dict
from studiobridge.flp.schema.profile import (
    EventMeaning,
    PlaylistItemRecord,
    StructLayouts,
    TextEncodingConfig,
    TrackDataRecord,
    VersionProfile,
    decode_playlist_items,
    decode_track_data,
    get_profile_by_id,
    load_builtin_profiles,
    parse_version_tuple,
)
from studiobridge.flp.schema.resolver import (
    ProfileResolver,
    ResolutionResult,
    get_default_resolver,
    get_profile,
    list_profiles,
    resolve_profile,
    resolve_profile_from_events,
    resolve_profile_from_file,
)
from studiobridge.flp.schema.text import (
    decode_text,
    decode_version_string,
    detect_encoding,
    encode_text,
)

__all__ = [
    "EventMeaning",
    "FlpVersionUnsupportedError",
    "PlaylistItemRecord",
    "ProfileResolver",
    "ResolutionResult",
    "StructLayouts",
    "TextEncodingConfig",
    "TrackDataRecord",
    "VersionProfile",
    "decode_playlist_items",
    "decode_text",
    "decode_track_data",
    "decode_version_string",
    "detect_encoding",
    "encode_text",
    "get_default_resolver",
    "get_profile",
    "get_profile_by_id",
    "list_profiles",
    "load_builtin_profiles",
    "load_yaml_file",
    "parse_version_tuple",
    "parse_yaml_dict",
    "resolve_profile",
    "resolve_profile_from_events",
    "resolve_profile_from_file",
]
