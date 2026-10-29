"""Plugin parameter inspection and mutation namespace for StudioBridge Python SDK.

Provides high-level typed plugin controllers (AsyncPlugins and SyncPlugins)
mounted on AsyncStudio.plugins and Studio.plugins.
"""

from __future__ import annotations

import contextlib
import functools
from typing import TYPE_CHECKING, Any, overload

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, PreconditionError
from studiobridge.sdk.types import (
    MixerTrack,
    PluginInfo,
    PluginParam,
    Slot,
    UntrustedString,
    Verified,
)
from studiobridge.sdk.verification import build_expect_guard, tolerance_matches, verify_mutation

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
            name=UntrustedString(name),
            param_count=param_count,
            is_valid=is_valid,
            color=color,
            preset_count=preset_count,
            untrusted=True,
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
            name=UntrustedString(param_name),
            value=param_val,
            min_value=0.0,
            max_value=1.0,
            text=UntrustedString(text_val),
            untrusted=True,
        )

    @overload
    async def set_param(
        self,
        slot: Slot,
        param_id: int,
        val: float,
        /,
        *,
        expect: float | dict[str, Any] | None = None,
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
        expect: float | dict[str, Any] | None = None,
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
        expect: float | dict[str, Any] | None = None,
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

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
                exp_eq = expect.get("eq", expect.get("value"))
                exp_tol = expect.get("tol", tol)
                if exp_eq is not None and not tolerance_matches(exp_eq, before.value, tol=exp_tol):
                    raise PreconditionError(
                        f"Precondition guard failed for plugins.setParamValue: "
                        f"expected {exp_eq}, current value is {before.value}",
                        code="E_PRECONDITION",
                        details={"expected": exp_eq, "actual": before.value, "tol": exp_tol},
                    )
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "plugins.setParamValue",
                    "plugins.getParamValue",
                    [p, t, s],
                    exp_val,
                    tol=tol,
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before.value, tol=tol):
                    raise PreconditionError(
                        f"Precondition guard failed for plugins.setParamValue: "
                        f"expected {exp_val}, current value is {before.value}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before.value, "tol": tol},
                    )

        await self._session.call(
            "plugins.setParamValue",
            {"value": target_val, "paramIndex": p, "index": t, "slot": s},
            opts=call_opts,
        )

        after = await self.get_param(t, s, p)
        return verify_mutation(
            "plugins.setParamValue",
            target_val,
            after.value,
            before=before.value,
            tol=tol,
            strict=strict,
            fp=self._session.fp,
            evidence={"track": t, "slot": s, "param_id": p, "text": after.text},
            journal=self._session.safety.journal,
            remedy="Check parameter ranges (typically 0.0..1.0) and plugin edit state.",
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
        expect: float | dict[str, Any] | None = None,
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
        expect: float | dict[str, Any] | None = None,
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
        expect: float | dict[str, Any] | None = None,
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
                    expect=expect,
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
                expect=expect,
                strict=strict,
                tol=tol,
            )
        )


__all__ = [
    "AsyncPlugins",
    "SyncPlugins",
]
