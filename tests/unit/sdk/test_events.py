"""Unit tests for typed event subscriptions, dispatching, and bounded queues.

Tests typed event dataclasses, subscription filtering, backpressure handling
(drop-oldest for high frequency events, guaranteed delivery for critical events),
and async iterator / callback registration per spec 09_l1_sdk.md §9 and [v0.2.9].
"""

from __future__ import annotations

import pytest

from studiobridge.sdk.client import Studio
from studiobridge.sdk.events import (
    AsyncEventManager,
    BeatEvent,
    BoundedEventQueue,
    DirtyEvent,
    LogEvent,
    ProjectLoadEvent,
    RefreshEvent,
    ShutdownEvent,
    StudioEvent,
    TransportEvent,
    create_event,
    topic_matches,
)
from studiobridge.sdk.session import Session


class TestEventDataclasses:
    """Verify strongly typed StudioEvent subclasses and factory constructor."""

    def test_create_transport_event(self) -> None:
        data = {
            "is_playing": True,
            "song_pos": 16.5,
            "tempo": 130.0,
            "mode": "song",
            "loop_mode": "all",
            "time_signature": [4, 4],
        }
        evt = create_event("transport", data, seq=1)
        assert isinstance(evt, TransportEvent)
        assert evt.topic == "transport"
        assert evt.seq == 1
        assert evt.is_playing is True
        assert evt.song_pos == 16.5
        assert evt.tempo == 130.0
        assert evt.mode == "song"
        assert evt.loop_mode == "all"
        assert evt.time_signature == (4, 4)
        assert evt.is_critical is False

    def test_create_refresh_event(self) -> None:
        evt = create_event("refresh", {"flags": 7, "target": "mixer"}, seq=2)
        assert isinstance(evt, RefreshEvent)
        assert evt.topic == "refresh"
        assert evt.flags == 7
        assert evt.target == "mixer"
        assert evt.is_critical is False

        # Primitive integer flags
        evt2 = create_event("refresh.channels", 3, seq=3)
        assert isinstance(evt2, RefreshEvent)
        assert evt2.flags == 3
        assert evt2.target == "channels"

    def test_create_project_load_event(self) -> None:
        data = {"path": "C:/Projects/demo.flp", "title": "Demo Song", "flags": 1}
        evt = create_event("project_load", data, seq=4)
        assert isinstance(evt, ProjectLoadEvent)
        assert evt.topic == "project_load"
        assert evt.path == "C:/Projects/demo.flp"
        assert evt.title == "Demo Song"
        assert evt.flags == 1
        assert evt.is_critical is True  # Guaranteed delivery!

    def test_create_dirty_event(self) -> None:
        evt = create_event("dirty.mixer", {"is_dirty": True}, seq=5)
        assert isinstance(evt, DirtyEvent)
        assert evt.topic == "dirty.mixer"
        assert evt.target == "mixer"
        assert evt.is_dirty is True
        assert evt.is_critical is False

        # Generic dirty with explicit target
        evt2 = create_event("dirty", {"target": "playlist", "is_dirty": False})
        assert isinstance(evt2, DirtyEvent)
        assert evt2.target == "playlist"
        assert evt2.is_dirty is False

    def test_create_beat_event(self) -> None:
        evt = create_event("beat", {"beat": 3, "bar": 2, "tick": 48, "tempo": 120.0}, seq=6)
        assert isinstance(evt, BeatEvent)
        assert evt.topic == "beat"
        assert evt.beat == 3
        assert evt.bar == 2
        assert evt.tick == 48
        assert evt.tempo == 120.0
        assert evt.is_critical is False

    def test_create_log_event(self) -> None:
        evt = create_event("log", {"message": "Buffer overrun", "level": "warning"}, seq=7)
        assert isinstance(evt, LogEvent)
        assert evt.topic == "log"
        assert evt.message == "Buffer overrun"
        assert evt.level == "warning"
        assert evt.is_critical is False

    def test_create_shutdown_event(self) -> None:
        evt = create_event("shutdown", {"reason": "normal_exit"}, seq=8)
        assert isinstance(evt, ShutdownEvent)
        assert evt.topic == "shutdown"
        assert evt.reason == "normal_exit"
        assert evt.is_critical is True

    def test_create_generic_event(self) -> None:
        evt = create_event("custom.telemetry", {"val": 42}, seq=9)
        assert isinstance(evt, StudioEvent)
        assert evt.topic == "custom.telemetry"
        assert evt.raw == {"val": 42}
        assert evt.is_critical is False

        # Serialization to dictionary
        d = evt.to_dict()
        assert d["topic"] == "custom.telemetry"
        assert d["seq"] == 9


class TestTopicMatching:
    """Verify subscription topic matching patterns."""

    def test_wildcard_all(self) -> None:
        assert topic_matches("*", "transport") is True
        assert topic_matches("*", "project_load") is True
        assert topic_matches("*", "dirty.mixer") is True

    def test_exact_match(self) -> None:
        assert topic_matches("transport", "transport") is True
        assert topic_matches("transport", "beat") is False

    def test_prefix_matching(self) -> None:
        assert topic_matches("dirty", "dirty.mixer") is True
        assert topic_matches("dirty", "dirty.channels") is True
        assert topic_matches("dirty.*", "dirty.mixer") is True
        assert topic_matches("dirty.*", "dirty") is True
        assert topic_matches("dirty.*", "transport") is False


class TestBoundedEventQueue:
    """Verify queue capacity limits and backpressure guarantees."""

    def test_slow_consumer_drop_oldest_high_frequency(self) -> None:
        """High-frequency events (beat, transport) drop the oldest items when queue is full."""
        q = BoundedEventQueue(maxsize=5)

        for i in range(10):
            beat = BeatEvent(topic="beat", seq=i, beat=i)
            q.push(beat)

        assert len(q) == 5
        assert q.dropped_count == 5

        # Oldest items (0..4) should have been dropped; 5..9 remain
        for expected_seq in range(5, 10):
            item = q.pop_sync(timeout=0.1)
            assert item is not None
            assert item.seq == expected_seq

    def test_guaranteed_delivery_for_critical_events(self) -> None:
        """Critical events (project_load, shutdown) are never dropped."""
        q = BoundedEventQueue(maxsize=3)

        # Fill queue with non-critical beat events
        q.push(BeatEvent(topic="beat", seq=1, is_critical=False))
        q.push(BeatEvent(topic="beat", seq=2, is_critical=False))
        q.push(BeatEvent(topic="beat", seq=3, is_critical=False))
        assert len(q) == 3

        # Push critical project_load event: oldest non-critical (seq=1) should be dropped
        # to make room
        proj_evt = ProjectLoadEvent(topic="project_load", path="test.flp", is_critical=True)
        q.push(proj_evt)

        assert len(q) == 3
        assert q.dropped_count == 1

        # Retrieve items: beat 2, beat 3, project_load
        i1 = q.pop_sync(timeout=0.1)
        assert i1 is not None and i1.seq == 2

        i2 = q.pop_sync(timeout=0.1)
        assert i2 is not None and i2.seq == 3

        i3 = q.pop_sync(timeout=0.1)
        assert isinstance(i3, ProjectLoadEvent)
        assert i3.path == "test.flp"

    def test_critical_events_not_dropped_even_if_queue_full_of_critical(self) -> None:
        """Even if queue only has critical events, new critical events are not dropped."""
        q = BoundedEventQueue(maxsize=2)

        q.push(ProjectLoadEvent(topic="project_load", seq=1, is_critical=True))
        q.push(ShutdownEvent(topic="shutdown", seq=2, is_critical=True))
        # Push 3rd critical event
        q.push(ProjectLoadEvent(topic="project_load", seq=3, is_critical=True))

        assert len(q) == 3  # Allowed burst to guarantee delivery
        assert q.dropped_count == 0


class TestEventManager:
    """Verify event manager subscription, filtering, and callback dispatch."""

    def test_callback_listener_registration(self) -> None:
        session = Session()
        mgr = AsyncEventManager(session)

        received: list[StudioEvent] = []

        def on_transport(evt: StudioEvent) -> None:
            received.append(evt)

        mgr.on("transport", on_transport)

        # Dispatch transport event -> received
        mgr.dispatch("transport", {"is_playing": True, "tempo": 120.0})
        assert len(received) == 1
        assert isinstance(received[0], TransportEvent)
        assert received[0].tempo == 120.0

        # Dispatch beat event -> ignored by transport listener
        mgr.dispatch("beat", {"beat": 1})
        assert len(received) == 1

        # Deregister callback
        mgr.off("transport", on_transport)
        mgr.dispatch("transport", {"is_playing": False})
        assert len(received) == 1

    @pytest.mark.anyio
    async def test_async_iterator_subscription(self) -> None:
        session = Session()
        mgr = AsyncEventManager(session)

        sub = mgr.subscribe(["transport", "project_load"])

        # Dispatch events
        mgr.dispatch("beat", {"beat": 1})  # ignored
        mgr.dispatch("transport", {"is_playing": True})  # delivered
        mgr.dispatch("project_load", {"title": "Test Song"})  # delivered

        evt1 = await sub.__anext__()
        assert isinstance(evt1, TransportEvent)
        assert evt1.is_playing is True

        evt2 = await sub.__anext__()
        assert isinstance(evt2, ProjectLoadEvent)
        assert evt2.title == "Test Song"

        await sub.close()

    @pytest.mark.anyio
    async def test_fl_events_callable_and_context_manager(self) -> None:
        """Verify fl.events("transport", "dirty") calling convention."""
        session = Session()
        mgr = AsyncEventManager(session)

        async with mgr("transport", "dirty") as sub:
            mgr.dispatch("dirty.mixer", {"is_dirty": True})
            mgr.dispatch("beat", {"beat": 4})

            evt = await sub.__anext__()
            assert isinstance(evt, DirtyEvent)
            assert evt.target == "mixer"


class TestStudioEventsIntegration:
    """Verify fl.events integration on synchronous Studio client."""

    def test_sync_events_on_callback(self, studio: Studio) -> None:
        received: list[StudioEvent] = []

        def handle_event(evt: StudioEvent) -> None:
            received.append(evt)

        studio.events.on("transport", handle_event)

        # Dispatch an event on session
        studio.session.events.dispatch("transport", {"is_playing": True, "tempo": 125.0})

        assert len(received) == 1
        assert isinstance(received[0], TransportEvent)
        assert received[0].tempo == 125.0

        studio.events.off("transport", handle_event)
        studio.session.events.dispatch("transport", {"is_playing": False})
        assert len(received) == 1
