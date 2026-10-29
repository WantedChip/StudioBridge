"""Playlist management namespace for StudioBridge Python SDK.

Provides high-level typed playlist controllers (AsyncPlaylist and SyncPlaylist)
mounted on AsyncStudio.playlist and Studio.playlist.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import (
    AmbiguousRefError,
    BadRefError,
    DisconnectedError,
    PreconditionError,
)
from studiobridge.sdk.capabilities import gate_capability
from studiobridge.sdk.refs import Pattern, PlaylistTrack
from studiobridge.sdk.types import UntrustedString, Verified
from studiobridge.sdk.units import Color
from studiobridge.sdk.verification import build_expect_guard, verify_mutation

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


def _resolve_track_number(track: int | PlaylistTrack) -> int:
    num = track.number if isinstance(track, PlaylistTrack) else int(track)
    if num < 1:
        raise ValueError(f"Playlist track number must be >= 1 (1-based), got {num}")
    return num


class AsyncPlaylist:
    """Asynchronous FL Studio playlist management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def count(self) -> int:
        """Retrieve total count of tracks in playlist."""
        res = await self._session.call("playlist.trackCount", {})
        return int(res) if res is not None else 0

    async def get_name(self, index: int | PlaylistTrack) -> UntrustedString:
        """Retrieve playlist track name tagged with untrusted metadata."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.getTrackName", {"index": num})
        return UntrustedString(res) if res is not None else UntrustedString("")

    async def set_name(
        self,
        index: int | PlaylistTrack,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set playlist track name with read-back verification."""
        num = _resolve_track_number(index)
        str_val = str(name)
        before = await self.get_name(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = str(expect)
                guard = build_expect_guard(
                    "playlist.setTrackName", "playlist.getTrackName", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for playlist.setTrackName: "
                        f"expected {exp_val!r}, current value is {before!r}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "playlist.setTrackName",
            {"index": num, "name": str_val},
            opts=call_opts,
        )
        after = await self.get_name(num)
        return verify_mutation(
            "playlist.setTrackName",
            str_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"playlist_track": num},
            journal=self._session.safety.journal,
            remedy="Ensure track index exists and name is non-empty.",
        )

    async def get_color(self, index: int | PlaylistTrack) -> int:
        """Retrieve playlist track color integer."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.getTrackColor", {"index": num})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | PlaylistTrack,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set playlist track RGB color with read-back verification."""
        num = _resolve_track_number(index)
        col_val = int(Color(color)) if not isinstance(color, int) else int(color)
        before = await self.get_color(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(Color(expect)) if not isinstance(expect, int) else int(expect)
                guard = build_expect_guard(
                    "playlist.setTrackColor", "playlist.getTrackColor", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for playlist.setTrackColor: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "playlist.setTrackColor",
            {"index": num, "color": col_val},
            opts=call_opts,
        )
        after = await self.get_color(num)
        return verify_mutation(
            "playlist.setTrackColor",
            col_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": num},
            journal=self._session.safety.journal,
            remedy="Ensure track index exists and color integer is valid.",
        )

    async def is_muted(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is muted."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.isTrackMuted", {"index": num})
        return bool(res)

    async def mute(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track mute state with read-back verification."""
        num = _resolve_track_number(index)
        target = bool(value)
        before = await self.is_muted(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "playlist.muteTrack", "playlist.isTrackMuted", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for playlist.muteTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "playlist.muteTrack",
            {"index": num, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.is_muted(num)
        return verify_mutation(
            "playlist.muteTrack",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": num},
            journal=self._session.safety.journal,
            remedy="Check whether track index exists or is muted by parent group.",
        )

    async def is_solo(self, index: int | PlaylistTrack) -> bool:
        """Query whether playlist track is soloed."""
        num = _resolve_track_number(index)
        res = await self._session.call("playlist.isTrackSolo", {"index": num})
        return bool(res)

    async def solo(
        self,
        index: int | PlaylistTrack,
        value: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track solo state with read-back verification."""
        num = _resolve_track_number(index)
        target = bool(value)
        before = await self.is_solo(num)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "playlist.soloTrack", "playlist.isTrackSolo", [num], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for playlist.soloTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "playlist.soloTrack",
            {"index": num, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.is_solo(num)
        return verify_mutation(
            "playlist.soloTrack",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": num},
            journal=self._session.safety.journal,
            remedy="Check whether other tracks prevent solo changes.",
        )

    async def get_track(self, index: int | PlaylistTrack) -> PlaylistTrack:
        """Retrieve structured PlaylistTrack reference object."""
        num = _resolve_track_number(index)
        name = await self.get_name(num)
        color = await self.get_color(num)
        muted = await self.is_muted(num)
        solo = await self.is_solo(num)
        return PlaylistTrack(number=num, name=name, color=color, muted=muted, solo=solo)

    async def list(self, limit: int = 32) -> list[PlaylistTrack]:
        """List active playlist tracks up to limit."""
        tot = await self.count()
        n = min(tot, limit) if tot > 0 else limit
        tracks: list[PlaylistTrack] = []
        for i in range(1, n + 1):
            tracks.append(await self.get_track(i))
        return tracks

    async def find(self, name: str, *, limit: int = 32) -> PlaylistTrack:
        """Find playlist track by name.

        Args:
            name: Track name to look up.
            limit: Maximum scan depth (default 32).

        Returns:
            Resolved PlaylistTrack handle.

        Raises:
            AmbiguousRefError: When multiple tracks match name.
            BadRefError: When no track matches name.
        """
        tot = await self.count()
        scan_count = min(tot, limit) if limit > 0 else tot
        exact_matches: list[int] = []
        ci_matches: list[int] = []
        query_ci = name.strip().lower()
        names: dict[int, str] = {}

        for i in range(1, scan_count + 1):
            nm = await self.get_name(i)
            names[i] = nm
            if nm == name:
                exact_matches.append(i)
            elif nm.strip().lower() == query_ci:
                ci_matches.append(i)

        if len(exact_matches) == 1:
            return await self.get_track(exact_matches[0])
        if len(exact_matches) > 1:
            raise AmbiguousRefError(
                f"Multiple playlist tracks matched {name!r}: {[names[i] for i in exact_matches]}",
                candidates=[PlaylistTrack(number=i, name=names[i]) for i in exact_matches],
                query=name,
            )
        if len(ci_matches) == 1:
            return await self.get_track(ci_matches[0])
        if len(ci_matches) > 1:
            raise AmbiguousRefError(
                f"Multiple playlist tracks matched {name!r} (case-insensitive): "
                f"{[names[i] for i in ci_matches]}",
                candidates=[PlaylistTrack(number=i, name=names[i]) for i in ci_matches],
                query=name,
            )
        raise BadRefError(
            f"No playlist track found matching {name!r}.",
            target=name,
            remedy="Verify playlist track name exists or list available playlist tracks.",
        )

    async def place_pattern(
        self,
        pattern: int | Pattern,
        track: int | PlaylistTrack,
        time: float = 0.0,
        *,
        expect: Any = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Place pattern clip onto playlist track at target time (experimental).

        Gated behind capability 'experimental.playlist_place' [CAP-02].
        Calling when disabled raises UnavailableError (ExperimentalDisabledError).
        """
        # 1. Gate capability per [CAP-02]
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

    def find(self, name: str, *, limit: int = 32) -> PlaylistTrack:
        """Find playlist track by name."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.find, name, limit=limit))

    def get_name(self, index: int | PlaylistTrack) -> UntrustedString | str:
        """Retrieve playlist track name tagged with untrusted metadata."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | PlaylistTrack,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set playlist track name with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, expect=expect, strict=strict)
        )

    def get_color(self, index: int | PlaylistTrack) -> int:
        """Retrieve playlist track color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | PlaylistTrack,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set playlist track RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, expect=expect, strict=strict)
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
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track mute state with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.mute, index, value=value, expect=expect, strict=strict)
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
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Set playlist track solo state with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.solo, index, value=value, expect=expect, strict=strict)
        )

    def place_pattern(
        self,
        pattern: int | Pattern,
        track: int | PlaylistTrack,
        time: float = 0.0,
        *,
        expect: Any = None,
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
                expect=expect,
                strict=strict,
            )
        )


__all__ = [
    "AsyncPlaylist",
    "SyncPlaylist",
]
