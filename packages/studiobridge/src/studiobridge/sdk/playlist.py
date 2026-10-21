"""Playlist arrangement namespace for StudioBridge Python SDK.

Provides high-level typed playlist controllers (AsyncPlaylist and SyncPlaylist)
mounted on AsyncStudio.playlist and Studio.playlist per spec 09_l1_sdk.md §4, §8.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.capabilities import gate_capability
from studiobridge.sdk.types import Pattern, PlaylistTrack, Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


def _resolve_track_number(track: int | PlaylistTrack) -> int:
    num = track.number if isinstance(track, PlaylistTrack) else int(track)
    if num < 1:
        raise ValueError(f"Playlist track number must be >= 1 (1-based), got {num}")
    return num


class AsyncPlaylist:
    """Asynchronous FL Studio playlist track inspection and management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def count(self) -> int:
        """Retrieve total count of tracks in playlist."""
        res = await self._session.call("playlist.trackCount", {})
        return int(res) if res is not None else 0

    async def get_name(self, index: int | PlaylistTrack) -> str:
        """Retrieve playlist track name."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.getTrackName", {"index": num})
        return str(res) if res is not None else ""

    async def set_name(
        self,
        index: int | PlaylistTrack,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set playlist track name with read-back verification."""
        num = _resolve_track_number(index)
        str_val = str(name)
        before = await self.get_name(num)
        await self._session.call("playlist.setTrackName", {"index": num, "name": str_val})
        after = await self.get_name(num)
        verified = after == str_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify playlist track {num} name: requested {str_val!r}, got {after!r}",
                target_value=str_val,
                actual_value=after,
                details={"track": num, "before": before, "after": after},
                remedy="Ensure track index exists and name is non-empty.",
            )

        return Verified(
            value=after,
            requested=str_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": num, "before": before, "after": after},
        )

    async def get_color(self, index: int | PlaylistTrack) -> int:
        """Retrieve playlist track color integer."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.getTrackColor", {"index": num})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | PlaylistTrack,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set playlist track RGB color with read-back verification."""
        num = _resolve_track_number(index)
        col_val = int(color)
        before = await self.get_color(num)
        await self._session.call("playlist.setTrackColor", {"index": num, "color": col_val})
        after = await self.get_color(num)
        verified = after == col_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify playlist track {num} color: requested {col_val}, got {after}",
                target_value=col_val,
                actual_value=after,
                details={"track": num, "before": before, "after": after},
                remedy="Ensure track index exists and color integer is valid.",
            )

        return Verified(
            value=after,
            requested=col_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": num, "before": before, "after": after},
        )

    async def is_muted(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is muted."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.isTrackMuted", {"index": num})
        return bool(res) if res is not None else False

    async def mute(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track mute state with read-back verification."""
        num = _resolve_track_number(index)
        target_val = bool(value)
        before = await self.is_muted(num)
        await self._session.call(
            "playlist.muteTrack",
            {"index": num, "value": 1 if target_val else 0},
        )
        after = await self.is_muted(num)
        verified = after == target_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify playlist track {num} mute state: "
                f"requested {target_val}, got {after}",
                target_value=target_val,
                actual_value=after,
                details={"track": num, "before": before, "after": after},
                remedy="Ensure track index exists and verify mute state.",
            )

        return Verified(
            value=after,
            requested=target_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": num, "before": before, "after": after},
        )

    async def is_solo(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is soloed."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.isTrackSolo", {"index": num})
        return bool(res) if res is not None else False

    async def solo(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track solo state with read-back verification."""
        num = _resolve_track_number(index)
        target_val = bool(value)
        before = await self.is_solo(num)
        await self._session.call(
            "playlist.soloTrack",
            {"index": num, "value": 1 if target_val else 0},
        )
        after = await self.is_solo(num)
        verified = after == target_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify playlist track {num} solo state: "
                f"requested {target_val}, got {after}",
                target_value=target_val,
                actual_value=after,
                details={"track": num, "before": before, "after": after},
                remedy="Ensure track index exists and verify solo state.",
            )

        return Verified(
            value=after,
            requested=target_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": num, "before": before, "after": after},
        )

    async def get_track(self, index: int | PlaylistTrack) -> PlaylistTrack:
        """Retrieve structured PlaylistTrack reference object."""
        num = _resolve_track_number(index)
        name = await self.get_name(num)
        color = await self.get_color(num)
        muted = await self.is_muted(num)
        solo = await self.is_solo(num)
        return PlaylistTrack(
            number=num,
            name=name,
            color=color,
            muted=muted,
            solo=solo,
        )

    async def list(self, limit: int = 32) -> list[PlaylistTrack]:
        """List active playlist tracks up to limit."""
        tot = await self.count()
        n = min(tot, limit) if tot > 0 else limit
        tracks: list[PlaylistTrack] = []
        for i in range(1, n + 1):
            tracks.append(await self.get_track(i))
        return tracks

    async def place_pattern(
        self,
        pattern: int | Pattern,
        track: int | PlaylistTrack,
        time: float = 0.0,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Place pattern clip onto playlist track at target time (experimental).

        Gated behind capability 'experimental.playlist_place' per 09_l1_sdk.md §8.
        Calling when disabled raises UnavailableError (ExperimentalDisabledError).
        """
        # 1. Gate capability per [CAP-02] and spec 09_l1_sdk.md §8
        gate_capability(self._session.caps, "experimental.playlist_place")

        pat_num = pattern.number if isinstance(pattern, Pattern) else int(pattern)
        trk_num = _resolve_track_number(track)
        t_val = float(time)

        await self._session.call(
            "playlist.placePattern",
            {"pattern": pat_num, "track": trk_num, "time": t_val},
        )

        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="display_only",
            fp=self._session.fp,
            evidence={"pattern": pat_num, "track": trk_num, "time": t_val},
        )


class SyncPlaylist:
    """Synchronous FL Studio playlist interface wrapping AsyncPlaylist."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_playlist: AsyncPlaylist,
        *,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_playlist
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue playlist operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before invoking playlist methods.",
            )

    def count(self) -> int:
        """Retrieve total count of tracks in playlist."""
        self._check_connection()
        return self._portal.call(self._async.count)

    def get_track(self, index: int | PlaylistTrack) -> PlaylistTrack:
        """Retrieve structured PlaylistTrack reference object."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_track, index))

    def list(self, limit: int = 32) -> list[PlaylistTrack]:
        """List active playlist tracks up to limit."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.list, limit=limit))

    def get_name(self, index: int | PlaylistTrack) -> str:
        """Retrieve playlist track name."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | PlaylistTrack,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set playlist track name with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, strict=strict)
        )

    def get_color(self, index: int | PlaylistTrack) -> int:
        """Retrieve playlist track color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | PlaylistTrack,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set playlist track RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, strict=strict)
        )

    def is_muted(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is muted."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_muted, index))

    def mute(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track mute state with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.mute, index, value=value, strict=strict)
        )

    def is_solo(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is soloed."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_solo, index))

    def solo(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track solo state with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.solo, index, value=value, strict=strict)
        )

    def place_pattern(
        self,
        pattern: int | Pattern,
        track: int | PlaylistTrack,
        time: float = 0.0,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Place pattern clip onto playlist track at target time (experimental)."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.place_pattern,
                pattern,
                track,
                time=time,
                strict=strict,
            )
        )


__all__ = [
    "AsyncPlaylist",
    "SyncPlaylist",
]
