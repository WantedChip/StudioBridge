"""Plugin parameter inspection and mutation namespace for StudioBridge Python SDK.

Provides high-level typed plugin controllers (AsyncPlugins and SyncPlugins)
mounted on AsyncStudio.plugins and Studio.plugins per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import contextlib
import functools
from typing import TYPE_CHECKING, overload

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import MixerTrack, PluginInfo, PluginParam, Slot, Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncPlugins:
    """Asynchronous FL Studio plugin parameter inspection and control interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @overload
    async def get_plugin(
        self,
        slot: Slot,
        /,
    ) -> PluginInfo: ...

    @overload
    async def get_plugin(
        self,
        track: int | MixerTrack,
        slot: int,
        /,
    ) -> PluginInfo: ...

    async def get_plugin(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot: int | None = None,
        /,
    ) -> PluginInfo:
        """Retrieve plugin information for target track and effect slot."""
        if isinstance(track_or_slot, Slot):
            t, s = track_or_slot.track, track_or_slot.slot
        else:
            t = track_or_slot.index if isinstance(track_or_slot, MixerTrack) else int(track_or_slot)
            s = int(slot if slot is not None else 0)

        is_valid = bool(await self._session.call("plugins.isValid", {"index": t, "slot": s}))
        name = ""
        param_count = 0
        color = 0
        preset_count = 0
        if is_valid:
            name_res = await self._session.call("plugins.getPluginName", {"index": t, "slot": s})
            name = str(name_res) if name_res is not None else ""
            if not name:
                name_res2 = await self._session.call("plugins.getName", {"index": t, "slot": s})
                name = str(name_res2) if name_res2 is not None else ""
            pc_res = await self._session.call("plugins.getParamCount", {"index": t, "slot": s})
            param_count = int(pc_res) if pc_res is not None else 0
            c_res = await self._session.call("plugins.getColor", {"index": t, "slot": s})
            color = int(c_res) if c_res is not None else 0
            pr_res = await self._session.call("plugins.getPresetCount", {"index": t, "slot": s})
            preset_count = int(pr_res) if pr_res is not None else 0

        return PluginInfo(
            track=t,
            slot=s,
            name=name,
            param_count=param_count,
            is_valid=is_valid,
            color=color,
            preset_count=preset_count,
        )

    async def list_plugins(
        self,
        track: int | MixerTrack,
        max_slots: int = 10,
    ) -> list[PluginInfo]:
        """List all valid plugins in effect slots of target track."""
        t = track.index if isinstance(track, MixerTrack) else int(track)
        plugins: list[PluginInfo] = []
        for slot_idx in range(max_slots):
            info = await self.get_plugin(t, slot_idx)
            if info.is_valid:
                plugins.append(info)
        return plugins

    @overload
    async def get_param(
        self,
        slot: Slot,
        param_id: int,
        /,
    ) -> PluginParam: ...

    @overload
    async def get_param(
        self,
        track: int | MixerTrack,
        slot: int,
        param_id: int,
        /,
    ) -> PluginParam: ...

    async def get_param(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot_or_param_id: int,
        param_id: int | None = None,
        /,
    ) -> PluginParam:
        """Read plugin parameter metadata, value, and display representation."""
        if isinstance(track_or_slot, Slot):
            t, s = track_or_slot.track, track_or_slot.slot
            p = int(slot_or_param_id)
        else:
            t = track_or_slot.index if isinstance(track_or_slot, MixerTrack) else int(track_or_slot)
            s = int(slot_or_param_id)
            p = int(param_id if param_id is not None else 0)

        name_res = await self._session.call(
            "plugins.getParamName", {"paramIndex": p, "index": t, "slot": s}
        )
        param_name = str(name_res) if name_res is not None else f"Param {p}"

        val_res = await self._session.call(
            "plugins.getParamValue", {"paramIndex": p, "index": t, "slot": s}
        )
        param_val = float(val_res) if val_res is not None else 0.0

        text_val = ""
        with contextlib.suppress(Exception):
            txt_res = await self._session.call(
                "plugins.getParamValueText", {"paramIndex": p, "index": t, "slot": s}
            )
            if txt_res is not None:
                text_val = str(txt_res)
        if not text_val:
            text_val = f"{param_val:.2f}"

        return PluginParam(
            track=t,
            slot=s,
            param_id=p,
            name=param_name,
            value=param_val,
            min_value=0.0,
            max_value=1.0,
            text=text_val,
        )

    @overload
    async def set_param(
        self,
        slot: Slot,
        param_id: int,
        val: float,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]: ...

    @overload
    async def set_param(
        self,
        track: int | MixerTrack,
        slot: int,
        param_id: int,
        val: float,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]: ...

    async def set_param(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot_or_param_id: int,
        param_id_or_val: int | float,
        val: float | None = None,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]:
        """Set plugin parameter value with read-back verification."""
        if isinstance(track_or_slot, Slot):
            t, s = track_or_slot.track, track_or_slot.slot
            p = int(slot_or_param_id)
            target_val = float(param_id_or_val)
        else:
            t = track_or_slot.index if isinstance(track_or_slot, MixerTrack) else int(track_or_slot)
            s = int(slot_or_param_id)
            p = int(param_id_or_val)
            target_val = float(val if val is not None else 0.0)

        before = await self.get_param(t, s, p)

        await self._session.call(
            "plugins.setParamValue",
            {"value": target_val, "paramIndex": p, "index": t, "slot": s},
        )

        after = await self.get_param(t, s, p)
        verified = abs(after.value - target_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify plugin (track {t}, slot {s}) param {p} value: "
                f"requested {target_val}, got {after.value} (tol={tol})",
                target_value=target_val,
                actual_value=after.value,
                details={
                    "track": t,
                    "slot": s,
                    "param_id": p,
                    "before": before.value,
                    "after": after.value,
                },
                remedy="Check parameter ranges (typically 0.0..1.0) and plugin edit state.",
            )

        return Verified(
            value=after.value,
            requested=target_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={
                "track": t,
                "slot": s,
                "param_id": p,
                "before": before.value,
                "after": after.value,
                "tol": tol,
            },
        )


class SyncPlugins:
    """Synchronous FL Studio plugin parameter interface wrapping AsyncPlugins."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_plugins: AsyncPlugins,
        *,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_plugins
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue plugin operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before invoking plugin methods.",
            )

    @overload
    def get_plugin(
        self,
        slot: Slot,
        /,
    ) -> PluginInfo: ...

    @overload
    def get_plugin(
        self,
        track: int | MixerTrack,
        slot: int,
        /,
    ) -> PluginInfo: ...

    def get_plugin(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot: int | None = None,
        /,
    ) -> PluginInfo:
        """Retrieve plugin information for target track and effect slot."""
        self._check_connection()
        if isinstance(track_or_slot, Slot):
            return self._portal.call(functools.partial(self._async.get_plugin, track_or_slot))
        return self._portal.call(
            functools.partial(
                self._async.get_plugin,
                track_or_slot,
                int(slot if slot is not None else 0),
            )
        )

    def list_plugins(
        self,
        track: int | MixerTrack,
        max_slots: int = 10,
    ) -> list[PluginInfo]:
        """List all valid plugins in effect slots of target track."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.list_plugins, track, max_slots=max_slots)
        )

    @overload
    def get_param(
        self,
        slot: Slot,
        param_id: int,
        /,
    ) -> PluginParam: ...

    @overload
    def get_param(
        self,
        track: int | MixerTrack,
        slot: int,
        param_id: int,
        /,
    ) -> PluginParam: ...

    def get_param(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot_or_param_id: int,
        param_id: int | None = None,
        /,
    ) -> PluginParam:
        """Read plugin parameter metadata, value, and display representation."""
        self._check_connection()
        if isinstance(track_or_slot, Slot):
            return self._portal.call(
                functools.partial(self._async.get_param, track_or_slot, slot_or_param_id)
            )
        return self._portal.call(
            functools.partial(
                self._async.get_param,
                track_or_slot,
                slot_or_param_id,
                int(param_id if param_id is not None else 0),
            )
        )

    @overload
    def set_param(
        self,
        slot: Slot,
        param_id: int,
        val: float,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]: ...

    @overload
    def set_param(
        self,
        track: int | MixerTrack,
        slot: int,
        param_id: int,
        val: float,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]: ...

    def set_param(
        self,
        track_or_slot: int | MixerTrack | Slot,
        slot_or_param_id: int,
        param_id_or_val: int | float,
        val: float | None = None,
        /,
        *,
        strict: bool = False,
        tol: float = 0.01,
    ) -> Verified[float]:
        """Set plugin parameter value with read-back verification."""
        self._check_connection()
        if isinstance(track_or_slot, Slot):
            return self._portal.call(
                functools.partial(
                    self._async.set_param,
                    track_or_slot,
                    slot_or_param_id,
                    float(param_id_or_val),
                    strict=strict,
                    tol=tol,
                )
            )
        return self._portal.call(
            functools.partial(
                self._async.set_param,
                track_or_slot,
                slot_or_param_id,
                int(param_id_or_val),
                float(val if val is not None else 0.0),
                strict=strict,
                tol=tol,
            )
        )


__all__ = [
    "AsyncPlugins",
    "SyncPlugins",
]
