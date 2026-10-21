"""Typed event subscriptions, event dispatching, and bounded queue management.

Implements typed event models, async iterators, callback listeners, bounded queues,
and backpressure handling (drop-oldest for high frequency events, guaranteed delivery
for critical events) per spec 09_l1_sdk.md §9 and [v0.2.9].
"""

from __future__ import annotations

import collections
import contextlib
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import anyio
from anyio.from_thread import BlockingPortal

from studiobridge.core.logging import get_logger

if TYPE_CHECKING:
    from studiobridge.sdk.cache import CacheManager
    from studiobridge.sdk.session import Session

logger = get_logger("sdk.events")

CRITICAL_TOPICS: frozenset[str] = frozenset({"project_load", "shutdown", "panic", "error"})


# -----------------------------------------------------------------------------
# Event Dataclasses
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class StudioEvent:
    """Base dataclass for all StudioBridge typed events."""

    topic: str
    timestamp: float = field(default_factory=time.time)
    seq: int = 0
    raw: dict[str, Any] = field(default_factory=dict)
    is_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert event to serializable dictionary."""
        return {
            "topic": self.topic,
            "timestamp": self.timestamp,
            "seq": self.seq,
            "is_critical": self.is_critical,
            "raw": self.raw,
        }


@dataclass(slots=True)
class TransportEvent(StudioEvent):
    """Transport playback, tempo, and song position update event."""

    is_playing: bool | None = None
    song_pos: float | None = None
    tempo: float | None = None
    mode: str | None = None
    loop_mode: str | None = None
    time_signature: tuple[int, int] | None = None


@dataclass(slots=True)
class RefreshEvent(StudioEvent):
    """FL Studio OnRefresh callback event."""

    flags: int = 0
    target: str | None = None


@dataclass(slots=True)
class ProjectLoadEvent(StudioEvent):
    """FL Studio project load event with guaranteed delivery."""

    path: str | None = None
    title: str | None = None
    flags: int = 0
    is_critical: bool = True


@dataclass(slots=True)
class DirtyEvent(StudioEvent):
    """FL Studio entity dirty mutation event."""

    target: str = "project"
    is_dirty: bool = True


@dataclass(slots=True)
class BeatEvent(StudioEvent):
    """High-frequency musical beat tick indicator event."""

    beat: int = 0
    bar: int = 0
    tick: int = 0
    tempo: float | None = None


@dataclass(slots=True)
class LogEvent(StudioEvent):
    """Device or broker log diagnostic event."""

    message: str = ""
    level: str = "info"


@dataclass(slots=True)
class ShutdownEvent(StudioEvent):
    """Session or device shutdown event with guaranteed delivery."""

    reason: str = "shutdown"
    is_critical: bool = True


def create_event(
    topic: str,
    data: Any = None,
    seq: int = 0,
    timestamp: float | None = None,
) -> StudioEvent:
    """Construct strongly typed StudioEvent subclass from topic and raw payload."""
    ts = timestamp if timestamp is not None else time.time()
    raw_dict = data if isinstance(data, dict) else ({"data": data} if data is not None else {})

    if topic == "transport" or topic.startswith("transport."):
        is_playing = raw_dict.get("is_playing")
        song_pos = raw_dict.get("song_pos")
        if song_pos is None:
            song_pos = raw_dict.get("pos")
        tempo = raw_dict.get("tempo")
        mode = raw_dict.get("mode")
        loop_mode = raw_dict.get("loop_mode")
        time_sig = raw_dict.get("time_signature")
        return TransportEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=False,
            is_playing=is_playing,
            song_pos=float(song_pos) if song_pos is not None else None,
            tempo=float(tempo) if tempo is not None else None,
            mode=str(mode) if mode is not None else None,
            loop_mode=str(loop_mode) if loop_mode is not None else None,
            time_signature=tuple(time_sig) if time_sig and len(time_sig) == 2 else None,  # type: ignore[arg-type]
        )

    if topic == "refresh" or topic.startswith("refresh."):
        flags_val = 0
        target_val = topic.split(".", 1)[1] if "." in topic else None
        if isinstance(data, dict):
            flags_val = raw_dict.get("flags", 0)
            if "target" in raw_dict:
                target_val = raw_dict["target"]
        elif isinstance(data, int):
            flags_val = data

        return RefreshEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=False,
            flags=int(flags_val),
            target=str(target_val) if target_val is not None else None,
        )

    if topic == "project_load" or topic.startswith("project_load."):
        flags_val = (
            raw_dict.get("flags", 0)
            if isinstance(data, dict)
            else (int(data) if isinstance(data, int) else 0)
        )
        return ProjectLoadEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=True,
            path=raw_dict.get("path"),
            title=raw_dict.get("title"),
            flags=int(flags_val),
        )

    if topic == "dirty" or topic.startswith("dirty."):
        target = raw_dict.get("target")
        if not target and "." in topic:
            target = topic.split(".", 1)[1]
        target = target or "project"
        is_dirty = raw_dict.get("is_dirty", True)
        return DirtyEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=False,
            target=str(target),
            is_dirty=bool(is_dirty),
        )

    if topic == "beat" or topic.startswith("beat."):
        beat_val = (
            raw_dict.get("beat")
            if isinstance(data, dict)
            else (int(data) if isinstance(data, int) else 0)
        )
        return BeatEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=False,
            beat=int(beat_val or 0),
            bar=int(raw_dict.get("bar", 0)),
            tick=int(raw_dict.get("tick", 0)),
            tempo=float(raw_dict["tempo"]) if raw_dict.get("tempo") is not None else None,
        )

    if topic == "log" or topic.startswith("log."):
        msg = raw_dict.get("message") if isinstance(data, dict) else str(data)
        level = raw_dict.get("level", "info") if isinstance(data, dict) else "info"
        return LogEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=False,
            message=str(msg or ""),
            level=str(level),
        )

    if topic == "shutdown":
        reason = raw_dict.get("reason", "shutdown")
        return ShutdownEvent(
            topic=topic,
            timestamp=ts,
            seq=seq,
            raw=raw_dict,
            is_critical=True,
            reason=str(reason),
        )

    # Generic StudioEvent fallback
    is_crit = topic in CRITICAL_TOPICS
    return StudioEvent(
        topic=topic,
        timestamp=ts,
        seq=seq,
        raw=raw_dict,
        is_critical=is_crit,
    )


def topic_matches(pattern: str, topic: str) -> bool:
    """Check if event topic matches subscription pattern.

    Supports:
    - Wildcard '*': matches all topics.
    - Exact match: 'transport' matches 'transport'.
    - Wildcard suffix: 'dirty.*' matches 'dirty.mixer', 'dirty.channels', and 'dirty'.
    - Topic prefix: 'dirty' matches 'dirty.mixer' and 'dirty.channels'.
    """
    if pattern == "*":
        return True
    if pattern == topic:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return topic == prefix or topic.startswith(prefix + ".")
    return bool(topic.startswith(pattern + "."))


# -----------------------------------------------------------------------------
# Bounded Event Queue (Backpressure & Guaranteed Delivery)
# -----------------------------------------------------------------------------


class BoundedEventQueue:
    """Thread-safe and async-friendly bounded queue enforcing slow consumer limits.

    Features:
    - Bounded capacity (e.g. 256 entries).
    - Drop-oldest for high frequency events (beat, transport).
    - Guaranteed delivery for critical events (project_load, shutdown), dropping
      oldest non-critical events to maintain bound.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self.maxsize: int = max(1, maxsize)
        self._queue: collections.deque[StudioEvent] = collections.deque()
        self._event = anyio.Event()
        self._closed: bool = False
        self._dropped_count: int = 0

    @property
    def dropped_count(self) -> int:
        """Total number of events dropped due to buffer capacity."""
        return self._dropped_count

    def push(self, event: StudioEvent) -> bool:
        """Push an event into the queue respecting backpressure policy."""
        if self._closed:
            return False

        if len(self._queue) >= self.maxsize:
            if event.is_critical:
                # Guaranteed delivery: drop oldest non-critical event if possible
                dropped_non_crit = False
                for idx, queued in enumerate(self._queue):
                    if not queued.is_critical:
                        del self._queue[idx]
                        self._dropped_count += 1
                        dropped_non_crit = True
                        break
                if not dropped_non_crit:
                    # All items currently in queue are critical; append without dropping critical
                    pass
                self._queue.append(event)
            else:
                # High-frequency event: drop oldest item in queue
                self._queue.popleft()
                self._dropped_count += 1
                self._queue.append(event)
        else:
            self._queue.append(event)

        self._event.set()
        return True

    async def pop(self) -> StudioEvent:
        """Pop the next event asynchronously. Raises StopAsyncIteration when closed and empty."""
        while True:
            if self._queue:
                val = self._queue.popleft()
                if not self._queue and not self._closed:
                    self._event = anyio.Event()
                return val

            if self._closed:
                raise StopAsyncIteration

            await self._event.wait()

    def pop_sync(self, timeout: float | None = 1.0) -> StudioEvent | None:
        """Pop the next event synchronously for sync callers or test polling."""
        deadline = time.monotonic() + (timeout if timeout is not None else 0.0)
        while True:
            if self._queue:
                val = self._queue.popleft()
                if not self._queue and not self._closed:
                    self._event = anyio.Event()
                return val

            if self._closed:
                return None

            if timeout is not None and time.monotonic() >= deadline:
                return None

            time.sleep(0.01)

    def close(self) -> None:
        """Close the queue, releasing all waiting consumers."""
        self._closed = True
        self._event.set()

    def __len__(self) -> int:
        return len(self._queue)


# -----------------------------------------------------------------------------
# Subscriptions
# -----------------------------------------------------------------------------


class AsyncEventSubscription:
    """Asynchronous event subscription context manager and iterator."""

    def __init__(
        self,
        manager: AsyncEventManager,
        topics: list[str],
        maxsize: int = 256,
    ) -> None:
        self.manager: AsyncEventManager = manager
        self.topics: list[str] = list(topics) if topics else ["*"]
        self.queue: BoundedEventQueue = BoundedEventQueue(maxsize=maxsize)
        self._is_active: bool = True

    @property
    def dropped_count(self) -> int:
        """Number of dropped events for this subscription."""
        return self.queue.dropped_count

    def matches(self, topic: str) -> bool:
        """Check if incoming topic matches this subscription."""
        return any(topic_matches(p, topic) for p in self.topics)

    def push(self, event: StudioEvent) -> bool:
        """Deliver event to subscription queue if topic matches."""
        if not self._is_active:
            return False
        if self.matches(event.topic):
            return self.queue.push(event)
        return False

    def __aiter__(self) -> AsyncEventSubscription:
        return self

    async def __anext__(self) -> StudioEvent:
        return await self.queue.pop()

    async def close(self) -> None:
        """Close subscription and release queue."""
        if not self._is_active:
            return
        self._is_active = False
        self.queue.close()
        self.manager.unsubscribe_subscription(self)

    async def __aenter__(self) -> AsyncEventSubscription:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


class SyncEventSubscription:
    """Synchronous event subscription wrapper over AsyncEventSubscription."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_sub: AsyncEventSubscription,
    ) -> None:
        self._portal: BlockingPortal = portal
        self._async_sub: AsyncEventSubscription = async_sub

    @property
    def dropped_count(self) -> int:
        """Number of dropped events for this subscription."""
        return self._async_sub.dropped_count

    def __iter__(self) -> SyncEventSubscription:
        return self

    def __next__(self) -> StudioEvent:
        try:
            return self._portal.call(self._async_sub.queue.pop)
        except StopAsyncIteration:
            raise StopIteration from None

    def poll(self, timeout: float = 1.0) -> StudioEvent | None:
        """Poll for next event with timeout."""
        return self._async_sub.queue.pop_sync(timeout=timeout)

    def close(self) -> None:
        """Close subscription."""
        self._portal.call(self._async_sub.close)

    def __enter__(self) -> SyncEventSubscription:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# -----------------------------------------------------------------------------
# Event Managers
# -----------------------------------------------------------------------------


class AsyncEventManager:
    """Asynchronous event manager for subscribing, dispatching, and buffering events."""

    def __init__(self, session: Session, cache: CacheManager | None = None) -> None:
        self.session: Session = session
        self.cache: CacheManager | None = cache
        self._subscriptions: list[AsyncEventSubscription] = []
        self._callbacks: dict[str, list[Callable[[StudioEvent], Any]]] = collections.defaultdict(
            list
        )

    def __call__(
        self,
        *topics: str | list[str],
        maxsize: int = 256,
    ) -> AsyncEventSubscription:
        """Convenience invocation: async for evt in fl.events("transport", "project_load")."""
        return self.subscribe(*topics, maxsize=maxsize)

    def subscribe(
        self,
        *topics: str | list[str],
        maxsize: int = 256,
    ) -> AsyncEventSubscription:
        """Create a new event subscription iterator for the given topics."""
        flat_topics: list[str] = []
        for t in topics:
            if isinstance(t, list):
                flat_topics.extend(t)
            elif isinstance(t, str):
                flat_topics.append(t)

        sub = AsyncEventSubscription(self, flat_topics, maxsize=maxsize)
        self._subscriptions.append(sub)
        return sub

    def unsubscribe_subscription(self, sub: AsyncEventSubscription) -> None:
        """Remove an active subscription."""
        if sub in self._subscriptions:
            self._subscriptions.remove(sub)

    def on(self, topic: str, callback: Callable[[StudioEvent], Any]) -> None:
        """Register callback listener for a topic pattern."""
        self._callbacks[topic].append(callback)

    def off(self, topic: str, callback: Callable[[StudioEvent], Any]) -> None:
        """Deregister callback listener for a topic pattern."""
        if topic in self._callbacks:
            with contextlib.suppress(ValueError):
                self._callbacks[topic].remove(callback)
            if not self._callbacks[topic]:
                self._callbacks.pop(topic, None)

    def dispatch(
        self,
        topic: str,
        data: Any = None,
        seq: int = 0,
        timestamp: float | None = None,
    ) -> StudioEvent:
        """Dispatch an event to all subscribers, callbacks, and cache invalidators."""
        event = create_event(topic, data=data, seq=seq, timestamp=timestamp)

        # 1. Event-driven cache invalidation per [v0.2.9] & 09 §9
        if self.cache is not None:
            self.cache.on_event(event)

        # 2. Push to matching subscriptions
        for sub in list(self._subscriptions):
            sub.push(event)

        # 3. Invoke matching callbacks
        for pattern, cbs in list(self._callbacks.items()):
            if topic_matches(pattern, topic):
                for cb in list(cbs):
                    try:
                        res = cb(event)
                        if inspect.iscoroutine(res):
                            # Close unawaited coroutine if returned by sync callback
                            res.close()
                    except Exception as exc:
                        logger.warning(
                            "event_callback_failed",
                            f"Callback failed for topic {topic}: {exc}",
                        )

        return event

    def close(self) -> None:
        """Close event manager and all active subscriptions."""
        for sub in list(self._subscriptions):
            sub.queue.close()
        self._subscriptions.clear()
        self._callbacks.clear()


class SyncEventManager:
    """Synchronous event manager wrapping AsyncEventManager via BlockingPortal."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_manager: AsyncEventManager,
        session: Session | None = None,
    ) -> None:
        self._portal: BlockingPortal = portal
        self._async: AsyncEventManager = async_manager
        self.session: Session | None = session

    def __call__(
        self,
        *topics: str | list[str],
        maxsize: int = 256,
    ) -> SyncEventSubscription:
        """Convenience invocation: for evt in fl.events("transport", "project_load")."""
        return self.subscribe(*topics, maxsize=maxsize)

    def subscribe(
        self,
        *topics: str | list[str],
        maxsize: int = 256,
    ) -> SyncEventSubscription:
        """Subscribe to events synchronously."""
        async_sub = self._portal.call(functools_partial_sub, self._async, topics, maxsize)
        return SyncEventSubscription(self._portal, async_sub)

    def on(self, topic: str, callback: Callable[[StudioEvent], Any]) -> None:
        """Register synchronous callback listener."""
        self._portal.call(self._async.on, topic, callback)

    def off(self, topic: str, callback: Callable[[StudioEvent], Any]) -> None:
        """Deregister synchronous callback listener."""
        self._portal.call(self._async.off, topic, callback)

    def dispatch(
        self,
        topic: str,
        data: Any = None,
        seq: int = 0,
        timestamp: float | None = None,
    ) -> StudioEvent:
        """Dispatch event synchronously."""
        return self._portal.call(self._async.dispatch, topic, data, seq, timestamp)

    def close(self) -> None:
        """Close event manager."""
        self._portal.call(self._async.close)


def functools_partial_sub(
    manager: AsyncEventManager,
    topics: tuple[str | list[str], ...],
    maxsize: int,
) -> AsyncEventSubscription:
    """Helper for portal subscription invocation."""
    return manager.subscribe(*topics, maxsize=maxsize)


# Exported alias per naming conventions
EventManager = AsyncEventManager

__all__ = [
    "CRITICAL_TOPICS",
    "AsyncEventManager",
    "AsyncEventSubscription",
    "BeatEvent",
    "BoundedEventQueue",
    "DirtyEvent",
    "EventManager",
    "LogEvent",
    "ProjectLoadEvent",
    "RefreshEvent",
    "ShutdownEvent",
    "StudioEvent",
    "SyncEventManager",
    "SyncEventSubscription",
    "TransportEvent",
    "create_event",
    "topic_matches",
]
