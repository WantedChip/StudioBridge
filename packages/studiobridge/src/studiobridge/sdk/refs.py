"""Entity reference handles and resolvers.

Provides named identity handles with strict index bases:
- MixerTrack(index): 0-based (0 = Master, 1..126 = Inserts)
- Channel(index): 0-based
- Pattern(number): 1-based per FL Studio conventions (Pattern 1, Pattern 2, ...)
- PlaylistTrack(number): 1-based per FL Studio conventions (Track 1, Track 2, ...)
- Slot(track, slot): 0-based (track 0..126, effect slot 0..9)

Resolvers (resolve_reference, fl.mixer.find, fl.channels.find, fl.patterns.find)
return refs or raise AmbiguousRefError with candidates list, or BadRefError.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from studiobridge.core.errors import AmbiguousRefError, BadRefError

T = TypeVar("T")


@dataclass
class MixerTrack:
    """Mixer track identity reference object.

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

    @property
    def is_master(self) -> bool:
        """Whether this mixer track is the Master track (index 0)."""
        return self.index == 0

    def __int__(self) -> int:
        return self.index

    def __index__(self) -> int:
        return self.index


@dataclass
class Channel:
    """Channel rack channel identity reference object.

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
    """Pattern identity reference object.

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


@dataclass
class PlaylistTrack:
    """Playlist track identity reference object.

    1-based indexing per FL Studio conventions (Track 1, Track 2, ...).
    """

    number: int
    name: str = ""
    color: int = 0
    muted: bool = False
    solo: bool = False

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError(f"PlaylistTrack number must be >= 1 (1-based), got {self.number}")

    @property
    def index(self) -> int:
        """Alias for track number."""
        return self.number

    def __int__(self) -> int:
        return self.number

    def __index__(self) -> int:
        return self.number


@dataclass(frozen=True)
class Slot:
    """Effect slot identity reference object.

    0-based indexing: track = mixer track index (0..126), slot = effect slot index (0..9).
    """

    track: int
    slot: int

    def __post_init__(self) -> None:
        if self.track < 0:
            raise ValueError(f"Slot track index must be non-negative (0-based), got {self.track}")
        if self.slot < 0:
            raise ValueError(f"Slot slot index must be non-negative (0-based), got {self.slot}")


def _default_name_accessor(item: Any) -> str:
    """Extract name attribute or string representation from item."""
    if hasattr(item, "name"):
        return str(item.name)
    return str(item)


def resolve_reference(
    candidates: Iterable[T],
    query: str,
    *,
    name_accessor: Callable[[T], str] | None = None,
    entity_type: str = "entity",
) -> T:
    """Resolve an entity by name query from a collection of candidates.

    Performs exact match first, falling back to case-insensitive match.
    - If exactly one candidate matches, returns it.
    - If multiple candidates match, raises AmbiguousRefError with candidates list.
    - If no candidates match, raises BadRefError with target query.

    Args:
        candidates: Iterable collection of candidate objects.
        query: Target name string to match.
        name_accessor: Optional function extracting string name from candidate.
        entity_type: Human-readable noun describing entity category.

    Returns:
        The single resolved matching candidate.

    Raises:
        AmbiguousRefError: When more than one candidate matches query.
        BadRefError: When no candidate matches query.
    """
    accessor = name_accessor or _default_name_accessor
    item_list = list(candidates)

    # 1. Exact match
    exact_matches = [item for item in item_list if accessor(item) == query]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise AmbiguousRefError(
            f"Multiple {entity_type}s matched {query!r}: {[accessor(m) for m in exact_matches]}",
            candidates=exact_matches,
            query=query,
        )

    # 2. Case-insensitive match fallback
    query_lower = query.strip().lower()
    ci_matches = [item for item in item_list if accessor(item).strip().lower() == query_lower]
    if len(ci_matches) == 1:
        return ci_matches[0]
    if len(ci_matches) > 1:
        raise AmbiguousRefError(
            f"Multiple {entity_type}s matched {query!r} (case-insensitive): "
            f"{[accessor(m) for m in ci_matches]}",
            candidates=ci_matches,
            query=query,
        )

    # 3. No match found
    raise BadRefError(
        f"No {entity_type} found matching {query!r}.",
        target=query,
        remedy=f"Verify {entity_type} name exists or list available {entity_type}s.",
    )


__all__ = [
    "Channel",
    "MixerTrack",
    "Pattern",
    "PlaylistTrack",
    "Slot",
    "resolve_reference",
]
