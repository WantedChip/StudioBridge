"""FLP high-level object model package."""

from __future__ import annotations

from studiobridge.flp.model.elements import (
    Arrangement,
    AutomationClip,
    Channel,
    Marker,
    MixerTrack,
    Note,
    OpaquePlugin,
    Pattern,
    PlaylistItem,
    Plugin,
    Slot,
    UnmodeledEvent,
)
from studiobridge.flp.model.project import Project

__all__ = [
    "Arrangement",
    "AutomationClip",
    "Channel",
    "Marker",
    "MixerTrack",
    "Note",
    "OpaquePlugin",
    "Pattern",
    "PlaylistItem",
    "Plugin",
    "Project",
    "Slot",
    "UnmodeledEvent",
]
