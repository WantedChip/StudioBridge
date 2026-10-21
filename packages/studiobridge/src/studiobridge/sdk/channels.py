"""Channel rack management namespace for StudioBridge Python SDK.

Provides high-level typed channel rack controllers (AsyncChannels and SyncChannels)
mounted on AsyncStudio.channels and Studio.channels per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, PreconditionError
from studiobridge.sdk.refs import Channel, resolve_reference
from studiobridge.sdk.types import UntrustedString, Verified
from studiobridge.sdk.units import Color, Db, Pan, Percent, Volume
from studiobridge.sdk.verification import build_expect_guard, tolerance_matches, verify_mutation

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

    async def get_name(self, index: int | Channel) -> UntrustedString:
        """Retrieve channel name tagged with untrusted metadata."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelName", {"index": idx})
        return UntrustedString(res) if res is not None else UntrustedString("")

    async def set_name(
        self,
        index: int | Channel,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set channel display label with read-back verification."""
        idx = _resolve_channel_index(index)
        str_val = str(name)
        before = await self.get_name(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = str(expect)
                guard = build_expect_guard(
                    "channels.setChannelName", "channels.getChannelName", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelName: "
                        f"expected {exp_val!r}, current value is {before!r}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.setChannelName",
            {"index": idx, "name": str_val},
            opts=call_opts,
        )
        after = await self.get_name(idx)
        return verify_mutation(
            "channels.setChannelName",
            str_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Ensure channel index exists and name is valid.",
        )

    async def get_volume(self, index: int | Channel) -> float:
        """Retrieve normalized channel volume (0.0 to 1.0)."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelVolume", {"index": idx})
        return float(res) if res is not None else 0.78

    async def set_volume(
        self,
        index: int | Channel,
        val: float | Volume | Db | Percent,
        *,
        expect: float | Volume | Db | Percent | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized channel volume with read-back verification."""
        idx = _resolve_channel_index(index)
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
                        f"Precondition guard failed for channels.setChannelVolume: "
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
                    "channels.setChannelVolume",
                    "channels.getChannelVolume",
                    [idx],
                    exp_val,
                    tol=0.01,
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.01):
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelVolume: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.01},
                    )

        await self._session.call(
            "channels.setChannelVolume",
            {"index": idx, "volume": vol_val},
            opts=call_opts,
        )
        after = await self.get_volume(idx)
        return verify_mutation(
            "channels.setChannelVolume",
            vol_val,
            after,
            before=before,
            tol=0.01,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether channel volume is clamped within 0.0 to 1.0.",
        )

    async def get_pan(self, index: int | Channel) -> float:
        """Retrieve channel pan position (-1.0 left to 1.0 right)."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelPan", {"index": idx})
        return float(res) if res is not None else 0.0

    async def set_pan(
        self,
        index: int | Channel,
        val: float | Pan,
        *,
        expect: float | Pan | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pan position (-1.0 to 1.0) with read-back verification."""
        idx = _resolve_channel_index(index)
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
                        f"Precondition guard failed for channels.setChannelPan: "
                        f"expected {exp_eq}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_eq, "actual": before, "tol": exp_tol},
                    )
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "channels.setChannelPan", "channels.getChannelPan", [idx], exp_val, tol=0.01
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.01):
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelPan: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.01},
                    )

        await self._session.call(
            "channels.setChannelPan",
            {"index": idx, "pan": pan_val},
            opts=call_opts,
        )
        after = await self.get_pan(idx)
        return verify_mutation(
            "channels.setChannelPan",
            pan_val,
            after,
            before=before,
            tol=0.01,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether channel pan is within valid range [-1.0, 1.0].",
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
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute channel with read-back verification."""
        idx = _resolve_channel_index(index)
        target = bool(muted)
        before = await self.is_muted(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "channels.muteChannel", "channels.isChannelMuted", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.muteChannel: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.muteChannel",
            {"index": idx, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.is_muted(idx)
        return verify_mutation(
            "channels.muteChannel",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether channel mute state is locked.",
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
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo channel with read-back verification."""
        idx = _resolve_channel_index(index)
        target = bool(soloed)
        before = await self.is_solo(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "channels.soloChannel", "channels.isChannelSolo", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.soloChannel: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.soloChannel",
            {"index": idx, "value": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.is_solo(idx)
        return verify_mutation(
            "channels.soloChannel",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether other channels prevent solo state changes.",
        )

    async def get_color(self, index: int | Channel) -> int:
        """Retrieve channel RGB color integer."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getChannelColor", {"index": idx})
        return int(res) if res is not None else 0

    async def set_color(
        self,
        index: int | Channel,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set channel RGB color with read-back verification."""
        idx = _resolve_channel_index(index)
        col_val = int(Color(color)) if not isinstance(color, int) else int(color)
        before = await self.get_color(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(Color(expect)) if not isinstance(expect, int) else int(expect)
                guard = build_expect_guard(
                    "channels.setChannelColor", "channels.getChannelColor", [idx], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelColor: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.setChannelColor",
            {"index": idx, "color": col_val},
            opts=call_opts,
        )
        after = await self.get_color(idx)
        return verify_mutation(
            "channels.setChannelColor",
            col_val,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Ensure color value is formatted as valid 24-bit RGB integer.",
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
        expect: float | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pitch offset with read-back verification."""
        idx = _resolve_channel_index(index)
        pitch_val = float(val)
        before = await self.get_pitch(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
                exp_eq = expect.get("eq", expect.get("value"))
                exp_tol = expect.get("tol", 0.01)
                if exp_eq is not None and not tolerance_matches(exp_eq, before, tol=exp_tol):
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelPitch: "
                        f"expected {exp_eq}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_eq, "actual": before, "tol": exp_tol},
                    )
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "channels.setChannelPitch", "channels.getChannelPitch", [idx], exp_val, tol=0.01
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.01):
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setChannelPitch: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.01},
                    )

        await self._session.call(
            "channels.setChannelPitch",
            {"index": idx, "pitch": pitch_val},
            opts=call_opts,
        )
        after = await self.get_pitch(idx)
        return verify_mutation(
            "channels.setChannelPitch",
            pitch_val,
            after,
            before=before,
            tol=0.01,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether channel pitch is supported by generator plugin.",
        )

    async def get_target_fx(self, index: int | Channel) -> int:
        """Retrieve target mixer track index linked to channel."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getTargetFxTrack", {"index": idx})
        return int(res) if res is not None else 0

    async def set_target_fx(
        self,
        index: int | Channel,
        track: int,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set target mixer track routing for channel with read-back verification."""
        idx = _resolve_channel_index(index)
        trk = int(track)
        before = await self.get_target_fx(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(expect)
                guard = build_expect_guard(
                    "channels.setTargetFxTrack", "channels.getTargetFxTrack", [idx], exp_val
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
            {"index": idx, "track": trk},
            opts=call_opts,
        )
        after = await self.get_target_fx(idx)
        return verify_mutation(
            "channels.setTargetFxTrack",
            trk,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Ensure target mixer track index exists.",
        )

    async def trigger_note(
        self,
        index: int | Channel,
        note: int = 60,
        vel: int = 100,
        dur: int = 1,
        *,
        expect: Any = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Audition a single note on target channel."""
        idx = _resolve_channel_index(index)
        await self._session.call(
            "channels.triggerNote",
            {"index": idx, "note": note, "velocity": vel, "duration": dur},
        )
        self._session.safety.journal.record(
            op="channels.triggerNote",
            target=f"channel.{idx}",
            before=None,
            after=True,
            proof="none",
            verified=True,
            details={"channel": idx, "note": note, "vel": vel, "dur": dur},
        )
        return Verified(
            value=True,
            requested=True,
            verified=True,
            plane="live",
            settled=True,
            proof="none",
            fp=self._session.fp,
            evidence={"channel": idx, "note": note, "vel": vel, "dur": dur},
        )

    async def get_step_grid(self, index: int | Channel) -> list[int]:
        """Retrieve channel step sequencer activation pattern as list of 0/1 integers."""
        idx = _resolve_channel_index(index)
        res = await self._session.call("channels.getStepGrid", {"index": idx})
        if isinstance(res, list):
            return [int(x) for x in res]
        return [0] * 16

    async def set_step_grid(
        self,
        index: int | Channel,
        steps: list[int] | list[bool],
        *,
        expect: list[int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[list[int]]:
        """Set channel step sequencer activation pattern with read-back verification."""
        idx = _resolve_channel_index(index)
        if len(steps) != 16:
            raise ValueError(f"Step grid must have exactly 16 steps, got {len(steps)}")
        step_ints = [1 if s else 0 for s in steps]
        before = await self.get_step_grid(idx)

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_list = [1 if s else 0 for s in expect]
                guard = build_expect_guard(
                    "channels.setStepGrid", "channels.getStepGrid", [idx], exp_list
                )
                call_opts = {"expect": guard}
                if before != exp_list:
                    raise PreconditionError(
                        f"Precondition guard failed for channels.setStepGrid: "
                        f"expected {exp_list}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "channels.setStepGrid",
            {"index": idx, "steps": step_ints},
            opts=call_opts,
        )
        after = await self.get_step_grid(idx)
        return verify_mutation(
            "channels.setStepGrid",
            step_ints,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            evidence={"channel": idx},
            journal=self._session.safety.journal,
            remedy="Check whether step grid length matches pattern length.",
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
        target_fx = await self.get_target_fx(idx)
        step_grid = await self.get_step_grid(idx)

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
            step_grid=step_grid,
        )

    async def list(self) -> list[Channel]:
        """Retrieve list of Channel objects for all channels in the channel rack."""
        total = await self.count()
        channels: list[Channel] = []
        for i in range(total):
            channels.append(await self.get_channel(i))
        return channels

    async def find(self, name: str) -> Channel:
        """Find channel rack item by name per 09 §3.2.

        Args:
            name: Channel name to look up.

        Returns:
            Resolved Channel handle.

        Raises:
            AmbiguousRefError: When multiple channels match name.
            BadRefError: When no channel matches name.
        """
        channels = await self.list()
        return resolve_reference(
            channels,
            name,
            name_accessor=lambda c: c.name,
            entity_type="channel",
        )


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

    def find(self, name: str) -> Channel:
        """Find channel rack item by name per 09 §3.2."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.find, name))

    def get_name(self, index: int | Channel) -> UntrustedString | str:
        """Retrieve channel name tagged with untrusted metadata."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_name, index))

    def set_name(
        self,
        index: int | Channel,
        name: str,
        *,
        expect: str | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[str]:
        """Set channel display label with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_name, index, name, expect=expect, strict=strict)
        )

    def get_volume(self, index: int | Channel) -> float:
        """Retrieve normalized channel volume (0.0 to 1.0)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_volume, index))

    def set_volume(
        self,
        index: int | Channel,
        val: float | Volume | Db | Percent,
        *,
        expect: float | Volume | Db | Percent | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized channel volume with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_volume, index, val, expect=expect, strict=strict)
        )

    def get_pan(self, index: int | Channel) -> float:
        """Retrieve channel pan position (-1.0 left to 1.0 right)."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_pan, index))

    def set_pan(
        self,
        index: int | Channel,
        val: float | Pan,
        *,
        expect: float | Pan | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pan position (-1.0 to 1.0) with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_pan, index, val, expect=expect, strict=strict)
        )

    def is_muted(self, index: int | Channel) -> bool:
        """Query whether channel is muted."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.is_muted, index))

    def mute(
        self,
        index: int | Channel,
        muted: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Mute or unmute channel with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.mute, index, muted=muted, expect=expect, strict=strict)
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
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Solo or unsolo channel with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.solo, index, soloed=soloed, expect=expect, strict=strict)
        )

    def get_color(self, index: int | Channel) -> int:
        """Retrieve channel RGB color integer."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_color, index))

    def set_color(
        self,
        index: int | Channel,
        color: int | Color | str | tuple[int, int, int],
        *,
        expect: int | Color | str | tuple[int, int, int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set channel RGB color with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_color, index, color, expect=expect, strict=strict)
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
        expect: float | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set channel pitch offset with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_pitch, index, val, expect=expect, strict=strict)
        )

    def trigger_note(
        self,
        index: int | Channel,
        note: int = 60,
        vel: int = 100,
        dur: int = 1,
        *,
        expect: Any = None,
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
                expect=expect,
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
        expect: list[int] | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[list[int]]:
        """Set channel step sequencer activation pattern with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_step_grid, index, steps, expect=expect, strict=strict)
        )


__all__ = [
    "AsyncChannels",
    "SyncChannels",
]
