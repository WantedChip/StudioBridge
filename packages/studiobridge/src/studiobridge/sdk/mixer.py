"""Mixer management namespace for StudioBridge Python SDK.

Provides high-level typed mixer controllers (AsyncMixer and SyncMixer)
mounted on AsyncStudio.mixer and Studio.mixer per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import Channel, MixerTrack, Verified

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
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized track volume with read-back verification."""
        idx = _resolve_track_index(index)
        vol_val = float(val)
        before = await self.get_volume(idx)
        await self._session.call("mixer.setTrackVolume", {"index": idx, "volume": vol_val})
        after = await self.get_volume(idx)
        tol = 0.01
        verified = abs(after - vol_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} volume: requested {vol_val}, got {after}",
                target_value=vol_val,
                actual_value=after,
                details={"track": idx, "before": before, "after": after, "tol": tol},
                remedy="Check whether mixer track volume is clamped or automated.",
            )

        return Verified(
            value=after,
            requested=vol_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after, "tol": tol},
        )

    async def get_pan(self, index: int | MixerTrack) -> float:
        """Retrieve track pan position (-1.0 left to 1.0 right)."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackPan", {"index": idx})
        return float(res) if res is not None else 0.0

    async def set_pan(
        self,
        index: int | MixerTrack,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set track pan position (-1.0 to 1.0) with read-back verification."""
        idx = _resolve_track_index(index)
        pan_val = float(val)
        before = await self.get_pan(idx)
        await self._session.call("mixer.setTrackPan", {"index": idx, "pan": pan_val})
        after = await self.get_pan(idx)
        tol = 0.01
        verified = abs(after - pan_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} pan: requested {pan_val}, got {after}",
                target_value=pan_val,
                actual_value=after,
                details={"track": idx, "before": before, "after": after, "tol": tol},
                remedy="Ensure pan value is within range [-1.0, 1.0].",
            )

        return Verified(
            value=after,
            requested=pan_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after, "tol": tol},
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute mixer track with read-back verification."""
        idx = _resolve_track_index(index)
        target = bool(muted)
        before = await self.is_muted(idx)
        await self._session.call("mixer.muteTrack", {"index": idx, "value": 1 if target else 0})
        after = await self.is_muted(idx)
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} mute state: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"track": idx, "before": before, "after": after},
                remedy="Check whether track mute state is locked or overridden by solo.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after},
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo mixer track with read-back verification."""
        idx = _resolve_track_index(index)
        target = bool(soloed)
        before = await self.is_solo(idx)
        await self._session.call("mixer.soloTrack", {"index": idx, "value": 1 if target else 0})
        after = await self.is_solo(idx)
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} solo state: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"track": idx, "before": before, "after": after},
                remedy="Check whether other tracks hold exclusive solo.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after},
        )

    async def is_armed(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is armed for disk recording."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.isTrackArmed", {"index": idx})
        return bool(res)

    async def arm(
        self,
        index: int | MixerTrack,
        armed: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Arm or disarm mixer track for recording."""
        idx = _resolve_track_index(index)
        target = bool(armed)
        before = await self.is_armed(idx)
        await self._session.call("mixer.armTrack", {"index": idx, "value": 1 if target else 0})
        after = await self.is_armed(idx)
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} arm state: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"track": idx, "before": before, "after": after},
                remedy="Ensure recording destination path is valid in FL Studio.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after},
        )

    async def get_name(self, index: int | MixerTrack) -> str:
        """Retrieve mixer track name."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackName", {"index": idx})
        return str(res) if res is not None else ""

    async def set_name(
        self,
        index: int | MixerTrack,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set mixer track label with read-back verification."""
        idx = _resolve_track_index(index)
        str_val = str(name)
        before = await self.get_name(idx)
        await self._session.call("mixer.setTrackName", {"index": idx, "name": str_val})
        after = await self.get_name(idx)
        verified = after == str_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} name: requested {str_val!r}, got {after!r}",
                target_value=str_val,
                actual_value=after,
                details={"track": idx, "before": before, "after": after},
                remedy="Check whether track name contains unsupported characters.",
            )

        return Verified(
            value=after,
            requested=str_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after},
        )

    async def get_color(self, index: int | MixerTrack) -> int:
        """Retrieve mixer track RGB color integer."""
        idx = _resolve_track_index(index)
        res = await self._session.call("mixer.getTrackColor", {"index": idx})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | MixerTrack,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set mixer track color with read-back verification."""
        idx = _resolve_track_index(index)
        col_val = int(color)
        before = await self.get_color(idx)
        await self._session.call("mixer.setTrackColor", {"index": idx, "color": col_val})
        after = await self.get_color(idx)
        verified = after == col_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify mixer track {idx} color: "
                f"requested 0x{col_val:06X}, got 0x{after:06X}",
                target_value=col_val,
                actual_value=after,
                details={"track": idx, "before": before, "after": after},
                remedy="Ensure color value is formatted as valid 24-bit RGB integer.",
            )

        return Verified(
            value=after,
            requested=col_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"track": idx, "before": before, "after": after},
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Route audio send from source track to destination track."""
        src = _resolve_track_index(source)
        dst = _resolve_track_index(dest)
        target = bool(enabled)
        before = bool(await self._session.call("mixer.getRouteTo", {"source": src, "dest": dst}))
        await self._session.call(
            "mixer.setRouteTo",
            {"source": src, "dest": dst, "value": 1 if target else 0},
        )
        after = bool(await self._session.call("mixer.getRouteTo", {"source": src, "dest": dst}))
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify routing from track {src} to {dst}: "
                f"requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"source": src, "dest": dst, "before": before, "after": after},
                remedy="Check whether circular routing is prohibited.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"source": src, "dest": dst, "before": before, "after": after},
        )

    async def link_channel(
        self,
        channel: int | Channel,
        track: int | MixerTrack,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Link a channel rack item to route its output into target mixer track."""
        chan = _resolve_channel_index(channel)
        trk = _resolve_track_index(track)
        before = int(await self._session.call("channels.getTargetFxTrack", {"index": chan}))
        await self._session.call("channels.setTargetFxTrack", {"index": chan, "track": trk})
        after = int(await self._session.call("channels.getTargetFxTrack", {"index": chan}))
        verified = after == trk

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {chan} link to track {trk}: got {after}",
                target_value=trk,
                actual_value=after,
                details={"channel": chan, "track": trk, "before": before, "after": after},
                remedy="Ensure channel and track indices are valid.",
            )

        return Verified(
            value=after,
            requested=trk,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": chan, "track": trk, "before": before, "after": after},
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

    def get_volume(self, index: int | MixerTrack) -> float:
        """Retrieve normalized track volume (0.0 to 1.0)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_volume, index))

    def set_volume(
        self,
        index: int | MixerTrack,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized track volume with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_volume, index, val, strict=strict)
        )

    def get_pan(self, index: int | MixerTrack) -> float:
        """Retrieve track pan position (-1.0 left to 1.0 right)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_pan, index))

    def set_pan(
        self,
        index: int | MixerTrack,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set track pan position (-1.0 to 1.0) with read-back verification."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.set_pan, index, val, strict=strict))

    def is_muted(self, index: int | MixerTrack) -> bool:
        """Query whether mixer track is muted."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_muted, index))

    def mute(
        self,
        index: int | MixerTrack,
        muted: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute mixer track with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.mute, index, muted=muted, strict=strict)
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo mixer track with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.solo, index, soloed=soloed, strict=strict)
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Arm or disarm mixer track for recording."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.arm, index, armed=armed, strict=strict)
        )

    def get_name(self, index: int | MixerTrack) -> str:
        """Retrieve mixer track name."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | MixerTrack,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set mixer track label with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, strict=strict)
        )

    def get_color(self, index: int | MixerTrack) -> int:
        """Retrieve mixer track RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | MixerTrack,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set mixer track color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, strict=strict)
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
        strict: bool = False,
    ) -> Verified[bool]:
        """Route audio send from source track to destination track."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.route, source, dest, enabled=enabled, strict=strict)
        )

    def link_channel(
        self,
        channel: int | Channel,
        track: int | MixerTrack,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Link a channel rack item to route its output into target mixer track."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.link_channel, channel, track, strict=strict)
        )


__all__ = [
    "AsyncMixer",
    "SyncMixer",
]
