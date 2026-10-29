"""Local entity read-through cache with event-driven invalidation and TTL.

Implements read-through caching for slow-changing entities (names, colors, routing,
counts, metadata) with 2-second default TTL, fast-changing parameter bypass
(volume, peaks, positions), and automatic event-driven
invalidation on project_load, refresh, and dirty.* events.
"""

from __future__ import annotations

import collections
import contextvars
import json
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

from studiobridge.core.logging import get_logger
from studiobridge.sdk.events import DirtyEvent, ProjectLoadEvent, RefreshEvent, StudioEvent

logger = get_logger("sdk.cache")

T = TypeVar("T")

# Default TTL for slow-changing reads
DEFAULT_CACHE_TTL: float = 2.0

# Context variable for scoped TTL overrides: with fl.cache(ttl=...):
scoped_cache_ttl: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "scoped_cache_ttl", default=None
)

# Operations or suffixes that change rapidly and bypass cache by default
FAST_CHANGING_PATTERNS: tuple[str, ...] = (
    "volume",
    "peak",
    "peaks",
    "pos",
    "position",
    "time",
    "song_pos",
    "songpos",
    "is_playing",
    "isplaying",
    "meter",
    "vu",
)

# Operations that change slowly (names, colors, routing, counts, metadata)
SLOW_CHANGING_PATTERNS: tuple[str, ...] = (
    "name",
    "color",
    "route",
    "routing",
    "target",
    "count",
    "number",
    "title",
    "author",
    "comment",
    "info",
    "version",
    "plugins",
    "tracks",
    "param",
)


def is_fast_changing(op: str) -> bool:
    """Return True if the operation represents a fast-changing parameter."""
    op_lower = op.lower()
    return any(p in op_lower for p in FAST_CHANGING_PATTERNS)


def is_slow_changing(op: str) -> bool:
    """Return True if the operation represents a slow-changing parameter."""
    op_lower = op.lower()
    return any(p in op_lower for p in SLOW_CHANGING_PATTERNS)


def make_cache_key(op: str, args: Any = None) -> str:
    """Generate deterministic string key for an operation and arguments."""
    if not args:
        return op

    if isinstance(args, dict):
        try:
            serialized = json.dumps(args, sort_keys=True, separators=(",", ":"))
        except Exception:
            serialized = str(sorted(args.items()))
        return f"{op}:{serialized}"

    if isinstance(args, (list, tuple)):
        return f"{op}:{':'.join(str(a) for a in args)}"

    return f"{op}:{args}"


def derive_tags(op: str, args: Any = None) -> set[str]:
    """Derive entity tags for cache invalidation."""
    tags: set[str] = set()

    # Domain prefix (mixer, channels, patterns, playlist, project, transport, plugins)
    domain = op.split(".", 1)[0] if "." in op else op
    tags.add(domain)

    # Index or identifier tag if present in args
    idx: Any = None
    if isinstance(args, dict):
        idx = args.get("index", args.get("track", args.get("pattern", args.get("channel"))))
    elif isinstance(args, (list, tuple)) and args:
        idx = args[0]

    if idx is not None:
        tags.add(f"{domain}.{idx}")

    return tags


@dataclass(slots=True)
class CacheEntry:
    """Cached entity entry with TTL and invalidation tags."""

    key: str
    value: Any
    created_at: float
    ttl: float
    tags: set[str] = field(default_factory=set)

    @property
    def is_expired(self) -> bool:
        """Whether this entry has exceeded its time-to-live."""
        return time.monotonic() >= self.created_at + self.ttl


class ScopedCacheContext:
    """Context manager setting temporary cache TTL (e.g. with fl.cache(ttl=5.0):)."""

    def __init__(self, ttl: float | None = None) -> None:
        self.ttl: float | None = ttl
        self._token: contextvars.Token[float | None] | None = None

    def __enter__(self) -> ScopedCacheContext:
        self._token = scoped_cache_ttl.set(self.ttl)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            scoped_cache_ttl.reset(self._token)
            self._token = None

    async def __aenter__(self) -> ScopedCacheContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


class CacheManager:
    """Read-through entity cache with TTL and event-driven invalidation."""

    def __init__(self, default_ttl: float = DEFAULT_CACHE_TTL) -> None:
        self.default_ttl: float = default_ttl
        self._entries: dict[str, CacheEntry] = {}
        self._tag_index: dict[str, set[str]] = collections.defaultdict(set)
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        """Whether caching is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)
        if not self._enabled:
            self.clear()

    def __call__(self, ttl: float | None = None) -> ScopedCacheContext:
        """Invoke as context manager to set temporary TTL: with fl.cache(ttl=...):."""
        return ScopedCacheContext(ttl=ttl)

    def get(self, key: str) -> Any | None:
        """Retrieve value by key if present and not expired."""
        if not self._enabled:
            return None

        entry = self._entries.get(key)
        if entry is None:
            return None

        if entry.is_expired:
            self._delete_entry(key)
            return None

        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        tags: set[str] | list[str] | None = None,
    ) -> None:
        """Store value with specified or default TTL and invalidation tags."""
        if not self._enabled:
            return

        effective_ttl = ttl if ttl is not None else self.default_ttl
        if effective_ttl <= 0:
            return

        tag_set = set(tags) if tags else set()
        now = time.monotonic()

        # Remove existing if present to keep index clean
        if key in self._entries:
            self._delete_entry(key)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            ttl=effective_ttl,
            tags=tag_set,
        )
        self._entries[key] = entry
        for t in tag_set:
            self._tag_index[t].add(key)

    def _delete_entry(self, key: str) -> None:
        """Internal helper to remove entry and remove from tag index."""
        entry = self._entries.pop(key, None)
        if entry is not None:
            for t in entry.tags:
                keys = self._tag_index.get(t)
                if keys:
                    keys.discard(key)
                    if not keys:
                        self._tag_index.pop(t, None)

    def invalidate(self, target: str) -> int:
        """Invalidate entries matching target exact key, tag, or prefix.

        Returns number of entries invalidated.
        """
        if target in ("*", "all"):
            count = len(self._entries)
            self.clear()
            return count

        # Strip 'dirty.' prefix if passed as an event target
        normalized = target
        if normalized.startswith("dirty."):
            normalized = normalized[6:]

        matched_keys: set[str] = set()

        # 1. Match by exact tag
        if normalized in self._tag_index:
            matched_keys.update(self._tag_index[normalized])

        # 2. Match by exact key
        if normalized in self._entries:
            matched_keys.add(normalized)

        # 3. Match by key prefix or tag prefix (e.g. 'mixer' matches 'mixer.getTrackName:0')
        prefix = f"{normalized}."
        colon_prefix = f"{normalized}:"
        for key in list(self._entries):
            if key.startswith(prefix) or key.startswith(colon_prefix) or key == normalized:
                matched_keys.add(key)

        for key in matched_keys:
            self._delete_entry(key)

        return len(matched_keys)

    def clear(self) -> None:
        """Invalidate all cached entities."""
        self._entries.clear()
        self._tag_index.clear()

    def on_event(self, event: StudioEvent) -> None:
        """Handle event-driven cache invalidation.

        - project_load: clears entire cache immediately.
        - refresh: clears entire cache or invalidates specified target subsystem.
        - dirty.*: invalidates target domain (e.g. dirty.mixer -> mixer).
        """
        if isinstance(event, ProjectLoadEvent) or event.topic == "project_load":
            self.clear()
            logger.debug("cache_invalidated", "Cache cleared on project_load event")
            return

        if isinstance(event, RefreshEvent) or event.topic.startswith("refresh"):
            target = getattr(event, "target", None)
            if target:
                self.invalidate(target)
            else:
                self.clear()
            logger.debug("cache_invalidated", f"Cache invalidated on refresh: {event.topic}")
            return

        if isinstance(event, DirtyEvent) or event.topic.startswith("dirty"):
            target_attr = getattr(event, "target", None)
            target_str = target_attr or (
                "project" if event.topic == "dirty" else event.topic.split(".", 1)[1]
            )
            self.invalidate(target_str)
            logger.debug(
                "cache_invalidated",
                f"Cache invalidated on dirty event for target '{target_str}'",
            )
            return

    def invalidate_operation(self, op: str, args: Any = None) -> int:
        """Invalidate cache entries affected by a mutating operation."""
        tags = derive_tags(op, args)
        count = 0
        for t in tags:
            count += self.invalidate(t)
        return count

    def get_call(self, op: str, args: Any = None) -> Any | None:
        """Check read-through cache for an operation call."""
        if not self._enabled:
            return None

        scoped_ttl = scoped_cache_ttl.get()
        # Fast-changing values bypass cache by default unless explicit scoped TTL is active
        if scoped_ttl is None and is_fast_changing(op):
            return None

        key = make_cache_key(op, args)
        return self.get(key)

    def set_call(
        self,
        op: str,
        args: Any = None,
        value: Any = None,
        ttl: float | None = None,
    ) -> None:
        """Store operation result in cache if eligible."""
        if not self._enabled:
            return

        scoped_ttl = scoped_cache_ttl.get()
        effective_ttl = ttl if ttl is not None else scoped_ttl

        # Fast-changing parameters bypass cache unless explicitly given a TTL
        if effective_ttl is None and is_fast_changing(op):
            return

        final_ttl = effective_ttl if effective_ttl is not None else self.default_ttl
        key = make_cache_key(op, args)
        tags = derive_tags(op, args)
        self.set(key, value, ttl=final_ttl, tags=tags)

    async def cached_call(
        self,
        op: str,
        args: Any,
        fetcher: Callable[[], Coroutine[Any, Any, T]],
        ttl: float | None = None,
        tags: set[str] | None = None,
    ) -> T:
        """Execute async fetcher with read-through caching."""
        cached_val = self.get_call(op, args)
        if cached_val is not None:
            return cached_val  # type: ignore[no-any-return]

        result = await fetcher()
        self.set_call(op, args, result, ttl=ttl)
        return result

    def cached_call_sync(
        self,
        op: str,
        args: Any,
        fetcher: Callable[[], T],
        ttl: float | None = None,
        tags: set[str] | None = None,
    ) -> T:
        """Execute sync fetcher with read-through caching."""
        cached_val = self.get_call(op, args)
        if cached_val is not None:
            return cached_val  # type: ignore[no-any-return]

        result = fetcher()
        self.set_call(op, args, result, ttl=ttl)
        return result

    def __len__(self) -> int:
        """Count active unexpired entries."""
        # Purge expired before counting
        now = time.monotonic()
        expired = [k for k, e in self._entries.items() if now >= e.created_at + e.ttl]
        for k in expired:
            self._delete_entry(k)
        return len(self._entries)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


class SyncCacheManager:
    """Synchronous interface for CacheManager mounted on Studio client."""

    def __init__(self, cache: CacheManager) -> None:
        self._cache: CacheManager = cache

    @property
    def enabled(self) -> bool:
        return self._cache.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._cache.enabled = value

    def __call__(self, ttl: float | None = None) -> ScopedCacheContext:
        """Context manager setting temporary cache TTL: with fl.cache(ttl=5.0):."""
        return self._cache(ttl=ttl)

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        tags: set[str] | list[str] | None = None,
    ) -> None:
        self._cache.set(key, value, ttl=ttl, tags=tags)

    def invalidate(self, target: str) -> int:
        return self._cache.invalidate(target)

    def invalidate_operation(self, op: str, args: Any = None) -> int:
        return self._cache.invalidate_operation(op, args)

    def clear(self) -> None:
        self._cache.clear()

    def get_call(self, op: str, args: Any = None) -> Any | None:
        return self._cache.get_call(op, args)

    def set_call(
        self,
        op: str,
        args: Any = None,
        value: Any = None,
        ttl: float | None = None,
    ) -> None:
        self._cache.set_call(op, args, value, ttl=ttl)

    def cached_call(
        self,
        op: str,
        args: Any,
        fetcher: Callable[[], T],
        ttl: float | None = None,
        tags: set[str] | None = None,
    ) -> T:
        return self._cache.cached_call_sync(op, args, fetcher, ttl=ttl, tags=tags)

    def on_event(self, event: StudioEvent) -> None:
        self._cache.on_event(event)

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache


# Exported alias per naming conventions
EntityCache = CacheManager

__all__ = [
    "DEFAULT_CACHE_TTL",
    "FAST_CHANGING_PATTERNS",
    "SLOW_CHANGING_PATTERNS",
    "CacheEntry",
    "CacheManager",
    "EntityCache",
    "ScopedCacheContext",
    "SyncCacheManager",
    "derive_tags",
    "is_fast_changing",
    "is_slow_changing",
    "make_cache_key",
    "scoped_cache_ttl",
]
