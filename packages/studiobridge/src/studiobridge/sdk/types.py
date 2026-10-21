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


class UntrustedString(str):
    """String subclass tagging user-controlled project strings from FL Studio.

    Carries untrusted=True metadata per 12_crosscutting.md §1 to defend against
    downstream prompt injection in LLM agents and tools.
    """

    untrusted: bool = True

    def __new__(cls, value: Any = "", untrusted: bool = True) -> UntrustedString:
        instance = super().__new__(cls, str(value))
        object.__setattr__(instance, "untrusted", untrusted)
        return instance

    def to_dict(self) -> dict[str, Any]:
        """Serialize text along with untrusted metadata flag."""
        return {"text": str(self), "value": str(self), "untrusted": bool(self.untrusted)}

    def __repr__(self) -> str:
        return f"UntrustedString({str(self)!r})"


@dataclass
class PluginInfo:
    """Information about a plugin loaded in a mixer slot or channel."""

    track: int
    slot: int
    name: str | UntrustedString = ""
    param_count: int = 0
    is_valid: bool = True
    color: int = 0
    preset_count: int = 0
    untrusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize plugin info with prompt-injection defense metadata."""
        return {
            "track": self.track,
            "slot": self.slot,
            "name": str(self.name),
            "param_count": self.param_count,
            "is_valid": self.is_valid,
            "color": self.color,
            "preset_count": self.preset_count,
            "untrusted": True,
        }


@dataclass
class PluginParam:
    """Plugin parameter metadata and value."""

    track: int
    slot: int
    param_id: int
    name: str | UntrustedString = ""
    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 1.0
    text: str | UntrustedString = ""
    untrusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize plugin parameter with prompt-injection defense metadata."""
        return {
            "track": self.track,
            "slot": self.slot,
            "param_id": self.param_id,
            "name": str(self.name),
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "text": str(self.text),
            "untrusted": True,
        }


@dataclass
class ProjectInfo:
    """Project metadata and modification state snapshot."""

    title: str | UntrustedString = ""
    author: str | UntrustedString = ""
    comment: str | UntrustedString = ""
    is_dirty: bool = False
    untrusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize project info with prompt-injection defense metadata."""
        return {
            "title": str(self.title),
            "author": str(self.author),
            "comment": str(self.comment),
            "is_dirty": self.is_dirty,
            "untrusted": True,
        }


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
    "UntrustedString",
    "Verified",
    "WriteReport",
    "resolve_reference",
]
