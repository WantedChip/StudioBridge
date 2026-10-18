"""StudioBridge SDK core types, models, and verification dataclasses.

Implements Verified[T] and identity reference objects (MixerTrack, Channel, Pattern)
per spec 09_l1_sdk.md §3.1, §3.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

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
class MixerTrack:
    """Mixer track identity reference object per 09_l1_sdk.md §3.2.

    0-based indexing: 0 = Master track, 1..126 = Insert tracks.
    """

    index: int
    name: str = ""
    volume: float = 0.8
    pan: float = 0.0
    muted: bool = False
    solo: bool = False
    color: int = 0
    armed: bool = False
    peak: float = 0.0

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"MixerTrack index must be non-negative (0-based), got {self.index}")

    def __int__(self) -> int:
        return self.index

    def __index__(self) -> int:
        return self.index


@dataclass
class Channel:
    """Channel rack channel identity reference object per 09_l1_sdk.md §3.2.

    0-based indexing.
    """

    index: int
    name: str = ""
    volume: float = 0.78
    pan: float = 0.0
    muted: bool = False
    solo: bool = False
    color: int = 0
    pitch: float = 0.0
    target_fx: int = 0
    step_grid: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"Channel index must be non-negative (0-based), got {self.index}")

    def __int__(self) -> int:
        return self.index

    def __index__(self) -> int:
        return self.index


@dataclass
class Pattern:
    """Pattern identity reference object per 09_l1_sdk.md §3.2.

    1-based indexing per FL Studio conventions (Pattern 1, Pattern 2, ...).
    """

    number: int
    name: str = ""
    color: int = 0
    length: int = 64

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError(f"Pattern number must be >= 1 (1-based), got {self.number}")

    @property
    def index(self) -> int:
        """Alias for pattern number."""
        return self.number

    def __int__(self) -> int:
        return self.number

    def __index__(self) -> int:
        return self.number


__all__ = [
    "Channel",
    "MixerTrack",
    "Pattern",
    "Verified",
]
