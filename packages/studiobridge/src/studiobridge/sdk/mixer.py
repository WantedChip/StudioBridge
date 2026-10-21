"""Mixer management namespace for StudioBridge Python SDK.

Provides high-level typed mixer controllers (AsyncMixer and SyncMixer)
mounted on AsyncStudio.mixer and Studio.mixer per spec 09_l1_sdk.md §4.
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
from studiobridge.sdk.refs import Channel, MixerTrack
from studiobridge.sdk.types import UntrustedString, Verified
from studiobridge.sdk.units import Color, Db, Pan, Percent, Volume
from studiobridge.sdk.verification import build_expect_guard, tolerance_matches, verify_mutation

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


def _resolve_track_index(track: int | MixerTrack) -> int:
    idx = track.index if isinstance(track, MixerTrack) else int(track)
    if idx < 0:
        raise ValueError(f"Mixer track index must be non-negative (0-based), got {idx}")
    return idx


def _resolve_channel_index(channel: int | Channel) -> int:
    idx = channel.index if isinstance(channel, Channel) else int(channel)
    if idx < 0:
        raise ValueError(f"Channel index must be non-negative (0-based), got {idx}")
    return idx


class AsyncMixer:
    """Asynchronous FL Studio mixer management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def track_count(self) -> int:
        """Retrieve total number of mixer tracks."""
        res = await self._session.call("mixer.trackCount", {})
        return int(res) if res is not None else 127

    async def get_volume(self, index: int | MixerTrack) -> float:
        """Retrieve normalized track volume (0.0 to 1.0)."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackVolume", {"index": idx})
        return float(res) if res is not None else 0.8

    async def set_volume(
        self,
        index: int | MixerTrack,
        val: float | Volume | Db | Percent,
        *,
        expect: float | Volume | Db | Percent | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[float]:
        """Set normalized track volume with read-back verification."""
        idx = _resolve_track_index(index)
        vol_val = float(Volume(val)) if isinstance(val, (Volume, Db, Percent)) else float(val)
        before = await self.get_volume(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
                exp_eq = expect.get("eq", expect.get("value"))
                exp_tol = expect.get("tol", 0.01)
                if exp_eq is not None and not tolerance_matches(exp_eq, before, tol=exp_tol):
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackVolume: "
                        f"expected {exp_eq}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_eq, "actual": before, "tol": exp_tol},
                    )
            else:
                exp_val = (
                    float(Volume(expect))
                    if isinstance(expect, (Volume, Db, Percent))
                    else float(expect)
                )
                guard = build_expect_guard(
                    "mixer.setTrackVolume", "mixer.getTrackVolume", [idx], exp_val, tol=0.01
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.01):
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackVolume: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.01},
                    )

        await self._session.call(
            "mixer.setTrackVolume",
            {"index": idx, "volume": vol_val},
            opts=call_opts,
            allow_protected=allow_protected,
            confirm=confirm,
        )
        after = await self.get_volume(idx)
        return verify_mutation(
            "mixer.setTrackVolume",
            vol_val,
            after,
            before=before,
            tol=0.01,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Check whether mixer track volume is clamped or automated.",
        )

    async def get_pan(self, index: int | MixerTrack) -> float:
        """Retrieve track pan position (-1.0 left to 1.0 right)."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackPan", {"index": idx})
        return float(res) if res is not None else 0.0

    async def set_pan(
        self,
        index: int | MixerTrack,
        val: float | Pan,
        *,
        expect: float | Pan | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[float]:
        """Set track pan position (-1.0 to 1.0) with read-back verification."""
        idx = _resolve_track_index(index)
        pan_val = float(val)
        before = await self.get_pan(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
                exp_eq = expect.get("eq", expect.get("value"))
                exp_tol = expect.get("tol", 0.01)
                if exp_eq is not None and not tolerance_matches(exp_eq, before, tol=exp_tol):
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackPan: "
                        f"expected {exp_eq}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_eq, "actual": before, "tol": exp_tol},
                    )
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "mixer.setTrackPan", "mixer.getTrackPan", [idx], exp_val, tol=0.01
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.01):
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackPan: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.01},
                    )

        await self._session.call(
            "mixer.setTrackPan",
            {"index": idx, "pan": pan_val},
            opts=call_opts,
            allow_protected=allow_protected,
            confirm=confirm,
        )
        after = await self.get_pan(idx)
        return verify_mutation(
            "mixer.setTrackPan",
            pan_val,
            after,
            before=before,
            tol=0.01,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Ensure pan value is within range [-1.0, 1.0].",
        )

    async def is_muted(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is muted."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.isTrackMuted", {"index": idx})
        return bool(res)

    async def mute(
        self,
        index: int | MixerTrack,
        muted: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute mixer track with read-back verification."""
        idx = _resolve_track_index(index)
        target = bool(muted)
        before = await self.is_muted(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("mixer.muteTrack", "mixer.isTrackMuted", [idx], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.muteTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.muteTrack",
            {"index": idx, "value": 1 if target else 0},
            opts=call_opts,
            allow_protected=allow_protected,
            confirm=confirm,
        )
        after = await self.is_muted(idx)
        return verify_mutation(
            "mixer.muteTrack",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Check whether track mute state is locked or overridden by solo.",
        )

    async def is_solo(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is soloed."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.isTrackSolo", {"index": idx})
        return bool(res)

    async def solo(
        self,
        index: int | MixerTrack,
        soloed: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo mixer track with read-back verification."""
        idx = _resolve_track_index(index)
        target = bool(soloed)
        before = await self.is_solo(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("mixer.soloTrack", "mixer.isTrackSolo", [idx], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.soloTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.soloTrack",
            {"index": idx, "value": 1 if target else 0},
            opts=call_opts,
            allow_protected=allow_protected,
            confirm=confirm,
        )
        after = await self.is_solo(idx)
        return verify_mutation(
            "mixer.soloTrack",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Check whether other tracks prevent solo state change.",
        )

    async def is_armed(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is armed for recording."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.isTrackArmed", {"index": idx})
        return bool(res)

    async def arm(
        self,
        index: int | MixerTrack,
        armed: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Arm or disarm mixer track for recording."""
        idx = _resolve_track_index(index)
        target = bool(armed)
        before = await self.is_armed(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("mixer.armTrack", "mixer.isTrackArmed", [idx], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.armTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.armTrack",
            {"index": idx, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.is_armed(idx)
        return verify_mutation(
            "mixer.armTrack",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Ensure recording destination path is valid in FL Studio.",
        )

    async def get_name(self, index: int | MixerTrack) -> UntrustedString:
        """Retrieve mixer track name tagged with untrusted metadata."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackName", {"index": idx})
        return UntrustedString(res) if res is not None else UntrustedString("")

    async def set_name(
        self,
        index: int | MixerTrack,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set mixer track label with read-back verification."""
        idx = _resolve_track_index(index)
        str_val = str(name)
        before = await self.get_name(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = str(expect)
                guard = build_expect_guard(
                    "mixer.setTrackName", "mixer.getTrackName", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackName: "
                        f"expected {exp_val!r}, current value is {before!r}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.setTrackName",
            {"index": idx, "name": str_val},
            opts=call_opts,
        )
        after = await self.get_name(idx)
        return verify_mutation(
            "mixer.setTrackName",
            str_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Check whether track name contains unsupported characters.",
        )

    async def get_color(self, index: int | MixerTrack) -> int:
        """Retrieve mixer track RGB color integer."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackColor", {"index": idx})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | MixerTrack,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set mixer track color with read-back verification."""
        idx = _resolve_track_index(index)
        col_val = int(Color(color)) if not isinstance(color, int) else int(color)
        before = await self.get_color(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(Color(expect)) if not isinstance(expect, int) else int(expect)
                guard = build_expect_guard(
                    "mixer.setTrackColor", "mixer.getTrackColor", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setTrackColor: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.setTrackColor",
            {"index": idx, "color": col_val},
            opts=call_opts,
        )
        after = await self.get_color(idx)
        return verify_mutation(
            "mixer.setTrackColor",
            col_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": idx},
            journal=self._session.safety.journal,
            remedy="Ensure color value is formatted as valid 24-bit RGB integer.",
        )

    async def get_peak(self, index: int | MixerTrack) -> float:
        """Retrieve instantaneous peak level (0.0 to 1.0) for mixer track."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackPeaks", {"index": idx, "mode": 0})
        return float(res) if res is not None else 0.0

    async def route(
        self,
        source: int | MixerTrack,
        dest: int | MixerTrack,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Route audio send from source track to destination track."""
        src = _resolve_track_index(source)
        dst = _resolve_track_index(dest)
        target = bool(enabled)
        before = bool(await self._session.call("mixer.getRouteTo", {"source": src, "dest": dst}))

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "mixer.setRouteTo", "mixer.getRouteTo", [src, dst], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for mixer.setRouteTo: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "mixer.setRouteTo",
            {"source": src, "dest": dst, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = bool(await self._session.call("mixer.getRouteTo", {"source": src, "dest": dst}))
        return verify_mutation(
            "mixer.setRouteTo",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"source": src, "dest": dst},
            journal=self._session.safety.journal,
            remedy="Check whether circular routing is prohibited.",
        )

    async def link_channel(
        self,
        channel: int | Channel,
        track: int | MixerTrack,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Link a channel rack item to route its output into target mixer track."""
        chan = _resolve_channel_index(channel)
        trk = _resolve_track_index(track)
        before = int(await self._session.call("channels.getTargetFxTrack", {"index": chan}))

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(expect)
                guard = build_expect_guard(
                    "channels.setTargetFxTrack", "channels.getTargetFxTrack", [chan], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setTargetFxTrack: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.setTargetFxTrack",
            {"index": chan, "track": trk},
            opts=call_opts,
        )
        after = int(await self._session.call("channels.getTargetFxTrack", {"index": chan}))
        return verify_mutation(
            "channels.setTargetFxTrack",
            trk,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": chan, "track": trk},
            journal=self._session.safety.journal,
            remedy="Ensure channel and track indices are valid.",
        )

    async def get_track(self, index: int | MixerTrack) -> MixerTrack:
        """Retrieve full state snapshot for a mixer track as a MixerTrack object."""
        idx = _resolve_track_index(index)
        name = await self.get_name(idx)
        volume = await self.get_volume(idx)
        pan = await self.get_pan(idx)
        muted = await self.is_muted(idx)
        solo = await self.is_solo(idx)
        color = await self.get_color(idx)
        armed = await self.is_armed(idx)
        peak = await self.get_peak(idx)

        return MixerTrack(
            index=idx,
            name=name,
            volume=volume,
            pan=pan,
            muted=muted,
            solo=solo,
            color=color,
            armed=armed,
            peak=peak,
        )

    async def get_tracks(self, count: int | None = None) -> list[MixerTrack]:
        """Retrieve state snapshots for the first N mixer tracks (default 16 or trackCount)."""
        total = count if count is not None else min(await self.track_count(), 16)
        tracks: list[MixerTrack] = []
        for i in range(total):
            tracks.append(await self.get_track(i))
        return tracks

    async def find(self, name: str, *, limit: int = 64) -> MixerTrack:
        """Find mixer track by exact or case-insensitive name match per 09 §3.2.

        Args:
            name: Track name to look up.
            limit: Maximum track scan depth (default 64).

        Returns:
            Resolved MixerTrack handle.

        Raises:
            AmbiguousRefError: When multiple tracks match name.
            BadRefError: When no track matches name.
        """
        tot = await self.track_count()
        scan_count = min(tot, limit) if limit > 0 else tot
        exact_matches: list[int] = []
        ci_matches: list[int] = []
        query_ci = name.strip().lower()

        names: dict[int, str] = {}
        for i in range(scan_count):
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
                f"Multiple mixer tracks matched {name!r}: {[names[i] for i in exact_matches]}",
                candidates=[MixerTrack(i, name=names[i]) for i in exact_matches],
                query=name,
            )
        if len(ci_matches) == 1:
            return await self.get_track(ci_matches[0])
        if len(ci_matches) > 1:
            raise AmbiguousRefError(
                f"Multiple mixer tracks matched {name!r} (case-insensitive): "
                f"{[names[i] for i in ci_matches]}",
                candidates=[MixerTrack(i, name=names[i]) for i in ci_matches],
                query=name,
            )
        raise BadRefError(
            f"No mixer track found matching {name!r}.",
            target=name,
            remedy="Verify mixer track name exists or list available mixer tracks.",
        )


class SyncMixer:
    """Synchronous FL Studio mixer management interface wrapping AsyncMixer via BlockingPortal."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_mixer: AsyncMixer,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_mixer
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue mixer operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling mixer operations.",
            )

    def track_count(self) -> int:
        """Retrieve total number of mixer tracks."""
        self._check_connection()
        return self._portal.call(self._async.track_count)

    def get_track(self, index: int | MixerTrack) -> MixerTrack:
        """Retrieve full state snapshot for a mixer track as a MixerTrack object."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_track, index))

    def get_tracks(self, count: int | None = None) -> list[MixerTrack]:
        """Retrieve state snapshots for all or the first N mixer tracks."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_tracks, count=count))

    def find(self, name: str, *, limit: int = 64) -> MixerTrack:
        """Find mixer track by name per 09 §3.2."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.find, name, limit=limit))

    def get_volume(self, index: int | MixerTrack) -> float:
        """Retrieve normalized track volume (0.0 to 1.0)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_volume, index))

    def set_volume(
        self,
        index: int | MixerTrack,
        val: float | Volume | Db | Percent,
        *,
        expect: float | Volume | Db | Percent | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[float]:
        """Set normalized track volume with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.set_volume,
                index,
                val,
                expect=expect,
                strict=strict,
                allow_protected=allow_protected,
                confirm=confirm,
            )
        )

    def get_pan(self, index: int | MixerTrack) -> float:
        """Retrieve track pan position (-1.0 left to 1.0 right)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_pan, index))

    def set_pan(
        self,
        index: int | MixerTrack,
        val: float | Pan,
        *,
        expect: float | Pan | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[float]:
        """Set track pan position (-1.0 to 1.0) with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.set_pan,
                index,
                val,
                expect=expect,
                strict=strict,
                allow_protected=allow_protected,
                confirm=confirm,
            )
        )

    def is_muted(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is muted."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_muted, index))

    def mute(
        self,
        index: int | MixerTrack,
        muted: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute mixer track with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.mute,
                index,
                muted=muted,
                expect=expect,
                strict=strict,
                allow_protected=allow_protected,
                confirm=confirm,
            )
        )

    def is_solo(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is soloed."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_solo, index))

    def solo(
        self,
        index: int | MixerTrack,
        soloed: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
        allow_protected: bool = False,
        confirm: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo mixer track with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.solo,
                index,
                soloed=soloed,
                expect=expect,
                strict=strict,
                allow_protected=allow_protected,
                confirm=confirm,
            )
        )

    def is_armed(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is armed for recording."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_armed, index))

    def arm(
        self,
        index: int | MixerTrack,
        armed: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Arm or disarm mixer track for recording."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.arm, index, armed=armed, expect=expect, strict=strict)
        )

    def get_name(self, index: int | MixerTrack) -> UntrustedString | str:
        """Retrieve mixer track name tagged with untrusted metadata."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | MixerTrack,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set mixer track label with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, expect=expect, strict=strict)
        )

    def get_color(self, index: int | MixerTrack) -> int:
        """Retrieve mixer track RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | MixerTrack,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set mixer track color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, expect=expect, strict=strict)
        )

    def get_peak(self, index: int | MixerTrack) -> float:
        """Retrieve instantaneous peak level (0.0 to 1.0) for mixer track."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_peak, index))

    def route(
        self,
        source: int | MixerTrack,
        dest: int | MixerTrack,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Route audio send from source track to destination track."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.route, source, dest, enabled=enabled, expect=expect, strict=strict
            )
        )

    def link_channel(
        self,
        channel: int | Channel,
        track: int | MixerTrack,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Link a channel rack item to route its output into target mixer track."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.link_channel, channel, track, expect=expect, strict=strict
            )
        )


__all__ = [
    "AsyncMixer",
    "SyncMixer",
]
