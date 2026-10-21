"""StudioBridge SDK core types, models, and verification dataclasses.

Implements Verified[T] and identity reference objects (MixerTrack, Channel, Pattern,
PlaylistTrack, Slot) per spec 09_l1_sdk.md §3.1, §3.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

from studiobridge.sdk.batch import Change, WriteReport
from studiobridge.sdk.refs import (
    Channel,
    MixerTrack,
    Pattern,
    PlaylistTrack,
    Slot,
    resolve_reference,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Verified(Generic[T]):
    """Verified write result holding read-back verification evidence per 09_l1_sdk.md §3.1.

    Attributes:
        value: Value actually read back from FL Studio.
        requested: Target value originally requested by caller (or None for parameterless).
        verified: True if read-back matches requested value within tolerance.
        plane: Control plane ("live", "offline", "render", "actuation").
        settled: True if read-back was taken after next idle tick / audio buffer.
        proof: How verification was confirmed ("readback", "display_only", "none").
        fp: Active session fingerprint pinned during the write.
        evidence: Dictionary containing before, after, and tolerance details.
    """

    value: T
    requested: T | None = None
    verified: bool = True
    plane: Literal["live", "offline", "render", "actuation"] = "live"
    settled: bool = True
    proof: Literal["readback", "display_only", "none"] = "readback"
    fp: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Evaluate truthiness based on whether the write was successfully verified."""
        return bool(self.verified)


@dataclass
class PluginInfo:
    """Information about a plugin loaded in a mixer slot or channel."""

    track: int
    slot: int
    name: str = ""
    param_count: int = 0
    is_valid: bool = True
    color: int = 0
    preset_count: int = 0


@dataclass
class PluginParam:
    """Plugin parameter metadata and value."""

    track: int
    slot: int
    param_id: int
    name: str = ""
    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 1.0
    text: str = ""


@dataclass
class ProjectInfo:
    """Project metadata and modification state snapshot."""

    title: str = ""
    author: str = ""
    comment: str = ""
    is_dirty: bool = False


__all__ = [
    "Change",
    "Channel",
    "MixerTrack",
    "Pattern",
    "PlaylistTrack",
    "PluginInfo",
    "PluginParam",
    "ProjectInfo",
    "Slot",
    "Verified",
    "WriteReport",
    "resolve_reference",
]
