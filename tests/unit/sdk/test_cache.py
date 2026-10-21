"""Unit tests for SDK entity read-through cache and event-driven invalidation.

Tests cache hits, TTL expiration, fast-changing parameter bypass, scoped TTL overrides
(with fl.cache(ttl=...):), and event-driven invalidation on project_load, refresh,
and dirty.* events per spec 09_l1_sdk.md §9 and [v0.2.9].
"""

from __future__ import annotations

import time

from studiobridge.sdk.cache import (
    DEFAULT_CACHE_TTL,
    CacheManager,
    is_fast_changing,
    is_slow_changing,
)
from studiobridge.sdk.client import Studio
from studiobridge.sdk.events import DirtyEvent, ProjectLoadEvent, RefreshEvent


class TestCacheBasics:
    """Verify basic CacheManager get, set, TTL, and manual invalidation."""

    def test_cache_hit_and_ttl_expiration(self) -> None:
        cache = CacheManager(default_ttl=2.0)

        # Set with 0.1s TTL
        cache.set("track:0:name", "Master", ttl=0.1)
        assert cache.get("track:0:name") == "Master"
        assert len(cache) == 1

        # Wait for expiration
        time.sleep(0.12)
        assert cache.get("track:0:name") is None
        assert len(cache) == 0

    def test_default_ttl_is_two_seconds(self) -> None:
        assert DEFAULT_CACHE_TTL == 2.0
        cache = CacheManager()
        cache.set("test_key", 123)
        assert cache.get("test_key") == 123

    def test_invalidate_by_key_tag_and_prefix(self) -> None:
        cache = CacheManager()
        cache.set("mixer.getTrackName:0", "Master", tags={"mixer", "mixer.0"})
        cache.set("mixer.getTrackName:1", "Kick", tags={"mixer", "mixer.1"})
        cache.set("channels.getChannelName:0", "Sampler", tags={"channels", "channels.0"})

        assert len(cache) == 3

        # Invalidate specific track tag
        count = cache.invalidate("mixer.1")
        assert count == 1
        assert cache.get("mixer.getTrackName:1") is None
        assert cache.get("mixer.getTrackName:0") == "Master"
        assert cache.get("channels.getChannelName:0") == "Sampler"

        # Invalidate entire mixer domain
        count2 = cache.invalidate("mixer")
        assert count2 >= 1
        assert cache.get("mixer.getTrackName:0") is None
        assert cache.get("channels.getChannelName:0") == "Sampler"

        # Clear remaining
        cache.clear()
        assert len(cache) == 0

    def test_fast_vs_slow_changing_classification(self) -> None:
        # Fast-changing (bypass cache by default)
        assert is_fast_changing("mixer.getTrackVolume") is True
        assert is_fast_changing("mixer.getTrackPeaks") is True
        assert is_fast_changing("transport.getSongPos") is True
        assert is_fast_changing("transport.isPlaying") is True

        # Slow-changing (cached with 2s TTL by default)
        assert is_slow_changing("mixer.getTrackName") is True
        assert is_slow_changing("mixer.getTrackColor") is True
        assert is_slow_changing("mixer.getRouteTo") is True
        assert is_slow_changing("channels.channelCount") is True
        assert is_slow_changing("project.getTitle") is True


class TestEventDrivenInvalidation:
    """Verify automatic cache invalidation driven by events per [v0.2.9]."""

    def test_project_load_clears_entire_cache(self) -> None:
        cache = CacheManager()
        cache.set("mixer.name:0", "Master", tags={"mixer"})
        cache.set("channels.name:0", "Kick", tags={"channels"})
        cache.set("project.title", "Old Track", tags={"project"})
        assert len(cache) == 3

        # Dispatch ProjectLoadEvent
        cache.on_event(ProjectLoadEvent(topic="project_load", path="new.flp"))

        # Everything must be invalidated
        assert len(cache) == 0
        assert cache.get("mixer.name:0") is None
        assert cache.get("project.title") is None

    def test_dirty_event_invalidates_target_domain(self) -> None:
        cache = CacheManager()
        cache.set("mixer.getTrackName:0", "Master", tags={"mixer"})
        cache.set("channels.getChannelName:0", "Kick", tags={"channels"})

        # Dispatch dirty.mixer event
        cache.on_event(DirtyEvent(topic="dirty.mixer", target="mixer"))

        assert cache.get("mixer.getTrackName:0") is None
        assert cache.get("channels.getChannelName:0") == "Kick"

    def test_refresh_event_clears_or_invalidates_target(self) -> None:
        cache = CacheManager()
        cache.set("mixer.0", "Master", tags={"mixer"})
        cache.set("channels.0", "Kick", tags={"channels"})

        # Specific target refresh
        cache.on_event(RefreshEvent(topic="refresh", target="mixer"))
        assert cache.get("mixer.0") is None
        assert cache.get("channels.0") == "Kick"

        # General refresh clears all
        cache.on_event(RefreshEvent(topic="refresh", flags=0))
        assert len(cache) == 0


class TestStudioCacheIntegration:
    """Verify live read-through caching on Studio client."""

    def test_slow_changing_read_utilizes_cache(self, studio: Studio) -> None:
        """Slow-changing read (mixer track name) is cached for 2 seconds."""
        # Initial read populates cache
        name1 = studio.mixer.get_name(0)
        assert name1 == "Master"

        # Ensure key is in cache
        cached_val = studio.cache.get('mixer.getTrackName:{"index":0}')
        assert cached_val == "Master"

        # Second read returns immediately from cache
        name2 = studio.mixer.get_name(0)
        assert name2 == "Master"

    def test_fast_changing_parameter_bypasses_cache_by_default(self, studio: Studio) -> None:
        """Fast-changing reads (volume, peaks) bypass cache by default."""
        vol1 = studio.mixer.get_volume(0)
        assert vol1 is not None

        # Key should NOT be in cache
        assert studio.cache.get('mixer.getTrackVolume:{"index":0}') is None

    def test_scoped_ttl_caches_fast_changing_parameters(self, studio: Studio) -> None:
        """Inside with fl.cache(ttl=...):, fast-changing parameters are cached."""
        with studio.cache(ttl=5.0):
            vol1 = studio.mixer.get_volume(0)
            assert vol1 is not None

            # In scoped context, it IS cached
            cached = studio.cache.get('mixer.getTrackVolume:{"index":0}')
            assert cached == vol1

            # Second read hits cache
            vol2 = studio.mixer.get_volume(0)
            assert vol2 == vol1

        # Outside scoped context, fast-changing parameters bypass cache again
        assert studio.cache.get_call("mixer.getTrackVolume", {"index": 0}) is None

    def test_event_invalidates_studio_cache(self, studio: Studio) -> None:
        """Receiving project_load event clears the active studio cache."""
        studio.mixer.get_name(0)
        assert len(studio.cache) > 0

        # Dispatch project_load event on session
        studio.session.events.dispatch("project_load", {"title": "New Song"})

        # Cache must be empty
        assert len(studio.cache) == 0

    def test_mutation_invalidates_affected_cache_domain(self, studio: Studio) -> None:
        """Mutating writes invalidate the corresponding subsystem cache."""
        # Prime cache with track name
        studio.mixer.get_name(1)
        assert studio.cache.get('mixer.getTrackName:{"index":1}') is not None

        # Mutate track volume
        studio.mixer.set_volume(1, 0.7)

        # Mixer cache entries should have been invalidated by write
        assert studio.cache.get('mixer.getTrackName:{"index":1}') is None
