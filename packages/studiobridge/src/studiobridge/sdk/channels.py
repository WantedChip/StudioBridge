"""Channel rack namespace for StudioBridge Python SDK.

Provides high-level typed channel controllers (AsyncChannels and SyncChannels)
mounted on AsyncStudio.channels and Studio.channels per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import Channel, Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


def _resolve_channel_index(channel: int | Channel) -> int:
    idx = channel.index if isinstance(channel, Channel) else int(channel)
    if idx < 0:
        raise ValueError(f"Channel index must be non-negative (0-based), got {idx}")
    return idx


class AsyncChannels:
    """Asynchronous FL Studio channel rack management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def count(self) -> int:
        """Retrieve total number of channels in the channel rack."""
        res = await self._session.call("channels.channelCount", {})
        return int(res) if res is not None else 0

    async def get_name(self, index: int | Channel) -> str:
        """Retrieve channel name."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelName", {"index": idx})
        return str(res) if res is not None else ""

    async def set_name(
        self,
        index: int | Channel,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set channel display label with read-back verification."""
        idx = _resolve_channel_index(index)
        str_val = str(name)
        before = await self.get_name(idx)
        await self._session.call("channels.setChannelName", {"index": idx, "name": str_val})
        after = await self.get_name(idx)
        verified = after == str_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} name: requested {str_val!r}, got {after!r}",
                target_value=str_val,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after},
                remedy="Ensure channel index exists and name is valid.",
            )

        return Verified(
            value=after,
            requested=str_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after},
        )

    async def get_volume(self, index: int | Channel) -> float:
        """Retrieve normalized channel volume (0.0 to 1.0)."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelVolume", {"index": idx})
        return float(res) if res is not None else 0.78

    async def set_volume(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized channel volume with read-back verification."""
        idx = _resolve_channel_index(index)
        vol_val = float(val)
        before = await self.get_volume(idx)
        await self._session.call("channels.setChannelVolume", {"index": idx, "volume": vol_val})
        after = await self.get_volume(idx)
        tol = 0.01
        verified = abs(after - vol_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} volume: requested {vol_val}, got {after}",
                target_value=vol_val,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after, "tol": tol},
                remedy="Check whether channel volume is clamped within 0.0 to 1.0.",
            )

        return Verified(
            value=after,
            requested=vol_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after, "tol": tol},
        )

    async def get_pan(self, index: int | Channel) -> float:
        """Retrieve channel pan position (-1.0 left to 1.0 right)."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelPan", {"index": idx})
        return float(res) if res is not None else 0.0

    async def set_pan(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pan position (-1.0 to 1.0) with read-back verification."""
        idx = _resolve_channel_index(index)
        pan_val = float(val)
        before = await self.get_pan(idx)
        await self._session.call("channels.setChannelPan", {"index": idx, "pan": pan_val})
        after = await self.get_pan(idx)
        tol = 0.01
        verified = abs(after - pan_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} pan: requested {pan_val}, got {after}",
                target_value=pan_val,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after, "tol": tol},
                remedy="Ensure pan value is within -1.0 to 1.0.",
            )

        return Verified(
            value=after,
            requested=pan_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after, "tol": tol},
        )

    async def is_muted(self, index: int | Channel) -> bool:
        """Query whether channel is muted."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.isChannelMuted", {"index": idx})
        return bool(res)

    async def mute(
        self,
        index: int | Channel,
        muted: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute channel with read-back verification."""
        idx = _resolve_channel_index(index)
        target = bool(muted)
        before = await self.is_muted(idx)
        await self._session.call(
            "channels.muteChannel", {"index": idx, "value": 1 if target else 0}
        )
        after = await self.is_muted(idx)
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} mute state: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after},
                remedy="Check whether channel state is locked or soloed.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after},
        )

    async def is_solo(self, index: int | Channel) -> bool:
        """Query whether channel is soloed."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.isChannelSolo", {"index": idx})
        return bool(res)

    async def solo(
        self,
        index: int | Channel,
        soloed: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo channel with read-back verification."""
        idx = _resolve_channel_index(index)
        target = bool(soloed)
        before = await self.is_solo(idx)
        await self._session.call(
            "channels.soloChannel", {"index": idx, "value": 1 if target else 0}
        )
        after = await self.is_solo(idx)
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} solo state: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after},
                remedy="Check whether another channel has exclusive solo.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after},
        )

    async def get_color(self, index: int | Channel) -> int:
        """Retrieve channel RGB color integer."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelColor", {"index": idx})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | Channel,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set channel RGB color with read-back verification."""
        idx = _resolve_channel_index(index)
        col_val = int(color)
        before = await self.get_color(idx)
        await self._session.call("channels.setChannelColor", {"index": idx, "color": col_val})
        after = await self.get_color(idx)
        verified = after == col_val

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} color: "
                f"requested 0x{col_val:06X}, got 0x{after:06X}",
                target_value=col_val,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after},
                remedy="Ensure color is valid 24-bit RGB integer.",
            )

        return Verified(
            value=after,
            requested=col_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after},
        )

    async def get_pitch(self, index: int | Channel) -> float:
        """Retrieve channel pitch offset in semitones / cents."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelPitch", {"index": idx})
        return float(res) if res is not None else 0.0

    async def set_pitch(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pitch offset with read-back verification."""
        idx = _resolve_channel_index(index)
        pitch_val = float(val)
        before = await self.get_pitch(idx)
        await self._session.call("channels.setChannelPitch", {"index": idx, "pitch": pitch_val})
        after = await self.get_pitch(idx)
        tol = 0.01
        verified = abs(after - pitch_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} pitch: requested {pitch_val}, got {after}",
                target_value=pitch_val,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after, "tol": tol},
                remedy="Check whether channel pitch range is constrained.",
            )

        return Verified(
            value=after,
            requested=pitch_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after, "tol": tol},
        )

    async def trigger_note(
        self,
        index: int | Channel,
        note: int = 60,
        vel: int = 100,
        dur: int = 1,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Audition a single note on target channel."""
        idx = _resolve_channel_index(index)
        await self._session.call(
            "channels.triggerNote",
            {"index": idx, "note": int(note), "velocity": int(vel), "duration": int(dur)},
        )
        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="none",
            fp=self._session.fp,
            evidence={"channel": idx, "note": note, "velocity": vel, "duration": dur},
        )

    async def get_step_grid(self, index: int | Channel) -> list[int]:
        """Retrieve channel step sequencer activation pattern as list of 0/1 integers."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getStepGrid", {"index": idx})
        if isinstance(res, (list, tuple)):
            return [int(s) for s in res]
        return [0] * 16

    async def set_step_grid(
        self,
        index: int | Channel,
        steps: list[int] | list[bool],
        *,
        strict: bool = False,
    ) -> Verified[list[int]]:
        """Set channel step sequencer activation pattern with read-back verification."""
        idx = _resolve_channel_index(index)
        if len(steps) < 4:
            raise ValueError(f"Step grid must contain at least 4 steps, got {len(steps)}")
        int_steps = [int(bool(s)) for s in steps]
        before = await self.get_step_grid(idx)
        await self._session.call("channels.setStepGrid", {"index": idx, "steps": int_steps})
        after = await self.get_step_grid(idx)
        verified = after == int_steps

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify channel {idx} step grid: requested {int_steps}, got {after}",
                target_value=int_steps,
                actual_value=after,
                details={"channel": idx, "before": before, "after": after},
                remedy="Ensure step grid length matches pattern step resolution.",
            )

        return Verified(
            value=after,
            requested=int_steps,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"channel": idx, "before": before, "after": after},
        )

    async def get_channel(self, index: int | Channel) -> Channel:
        """Retrieve full snapshot state of a channel as a Channel object."""
        idx = _resolve_channel_index(index)
        name = await self.get_name(idx)
        volume = await self.get_volume(idx)
        pan = await self.get_pan(idx)
        muted = await self.is_muted(idx)
        solo = await self.is_solo(idx)
        color = await self.get_color(idx)
        pitch = await self.get_pitch(idx)
        target_fx_res = await self._session.call("channels.getTargetFxTrack", {"index": idx})
        target_fx = int(target_fx_res) if target_fx_res is not None else 0
        grid = await self.get_step_grid(idx)

        return Channel(
            index=idx,
            name=name,
            volume=volume,
            pan=pan,
            muted=muted,
            solo=solo,
            color=color,
            pitch=pitch,
            target_fx=target_fx,
            step_grid=grid,
        )

    async def list(self) -> list[Channel]:
        """Retrieve list of Channel objects for all channels in the channel rack."""
        total = await self.count()
        channels: list[Channel] = []
        for i in range(total):
            channels.append(await self.get_channel(i))
        return channels


class SyncChannels:
    """Synchronous FL Studio channel rack interface wrapping AsyncChannels via BlockingPortal."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_channels: AsyncChannels,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_channels
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue channel operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling channel operations.",
            )

    def count(self) -> int:
        """Retrieve total number of channels in the channel rack."""
        self._check_connection()
        return self._portal.call(self._async.count)

    def get_channel(self, index: int | Channel) -> Channel:
        """Retrieve full snapshot state of a channel as a Channel object."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_channel, index))

    def list(self) -> list[Channel]:
        """Retrieve list of Channel objects for all channels in the channel rack."""
        self._check_connection()
        return self._portal.call(self._async.list)

    def get_name(self, index: int | Channel) -> str:
        """Retrieve channel name."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | Channel,
        name: str,
        *,
        strict: bool = False,
    ) -> Verified[str]:
        """Set channel display label with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, strict=strict)
        )

    def get_volume(self, index: int | Channel) -> float:
        """Retrieve normalized channel volume (0.0 to 1.0)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_volume, index))

    def set_volume(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized channel volume with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_volume, index, val, strict=strict)
        )

    def get_pan(self, index: int | Channel) -> float:
        """Retrieve channel pan position (-1.0 left to 1.0 right)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_pan, index))

    def set_pan(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pan position (-1.0 to 1.0) with read-back verification."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.set_pan, index, val, strict=strict))

    def is_muted(self, index: int | Channel) -> bool:
        """Query whether channel is muted."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_muted, index))

    def mute(
        self,
        index: int | Channel,
        muted: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute channel with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.mute, index, muted=muted, strict=strict)
        )

    def is_solo(self, index: int | Channel) -> bool:
        """Query whether channel is soloed."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_solo, index))

    def solo(
        self,
        index: int | Channel,
        soloed: bool = True,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo channel with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.solo, index, soloed=soloed, strict=strict)
        )

    def get_color(self, index: int | Channel) -> int:
        """Retrieve channel RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | Channel,
        color: int,
        *,
        strict: bool = False,
    ) -> Verified[int]:
        """Set channel RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, strict=strict)
        )

    def get_pitch(self, index: int | Channel) -> float:
        """Retrieve channel pitch offset in semitones / cents."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_pitch, index))

    def set_pitch(
        self,
        index: int | Channel,
        val: float,
        *,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pitch offset with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_pitch, index, val, strict=strict)
        )

    def trigger_note(
        self,
        index: int | Channel,
        note: int = 60,
        vel: int = 100,
        dur: int = 1,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Audition a single note on target channel."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.trigger_note,
                index,
                note=note,
                vel=vel,
                dur=dur,
                strict=strict,
            )
        )

    def get_step_grid(self, index: int | Channel) -> list[int]:
        """Retrieve channel step sequencer activation pattern as list of 0/1 integers."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_step_grid, index))

    def set_step_grid(
        self,
        index: int | Channel,
        steps: list[int] | list[bool],
        *,
        strict: bool = False,
    ) -> Verified[list[int]]:
        """Set channel step sequencer activation pattern with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_step_grid, index, steps, strict=strict)
        )


__all__ = [
    "AsyncChannels",
    "SyncChannels",
]
