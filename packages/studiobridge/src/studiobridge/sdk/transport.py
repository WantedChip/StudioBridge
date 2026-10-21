"""Transport control namespace for StudioBridge Python SDK.

Provides high-level typed transport controllers (AsyncTransport and SyncTransport)
mounted on AsyncStudio.transport and Studio.transport per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, PreconditionError
from studiobridge.sdk.types import Verified
from studiobridge.sdk.units import Tempo
from studiobridge.sdk.verification import build_expect_guard, tolerance_matches, verify_mutation

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncTransport:
    """Asynchronous FL Studio transport management interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def play(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Start or resume playback in FL Studio transport."""
        before = await self.is_playing()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("transport.start", "transport.isPlaying", [], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for transport.start: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call("transport.start", {}, opts=call_opts)
        after = await self.is_playing()
        return verify_mutation(
            "transport.start",
            True,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            remedy="Ensure FL Studio audio device is enabled and not frozen.",
        )

    async def stop(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Stop playback in FL Studio transport."""
        before = await self.is_playing()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("transport.stop", "transport.isPlaying", [], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for transport.stop: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call("transport.stop", {}, opts=call_opts)
        after = await self.is_playing()
        return verify_mutation(
            "transport.stop",
            False,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            remedy="Check whether recording or external sync is overriding transport stop.",
        )

    async def record(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Toggle or engage recording mode in FL Studio transport."""
        before = await self._is_recording()
        target = not before

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard("transport.record", "transport.isRecording", [], exp_val)
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for transport.record: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call("transport.record", {}, opts=call_opts)
        after = await self._is_recording()
        return verify_mutation(
            "transport.record",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            remedy="Verify recording filter settings in FL Studio.",
        )

    async def is_playing(self) -> bool:
        """Query whether transport playback is currently active."""
        res = await self._session.call("transport.isPlaying", {})
        return bool(res)

    async def _is_recording(self) -> bool:
        """Query whether transport recording mode is currently active."""
        res = await self._session.call("transport.isRecording", {})
        return bool(res)

    async def get_tempo(self) -> float:
        """Retrieve current project tempo in BPM."""
        res = await self._session.call("transport.getTempo", {})
        return float(res) if res is not None else 120.0

    async def set_tempo(
        self,
        bpm: float | Tempo,
        *,
        expect: float | Tempo | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set project tempo in BPM with read-back verification."""
        bpm_val = float(bpm)
        before = await self.get_tempo()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
                exp_eq = expect.get("eq", expect.get("value"))
                exp_tol = expect.get("tol", 0.1)
                if exp_eq is not None and not tolerance_matches(exp_eq, before, tol=exp_tol):
                    raise PreconditionError(
                        f"Precondition guard failed for transport.setTempo: "
                        f"expected {exp_eq}, current value is {before}",
                        code="E_PRECONDITION",
                    )
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "transport.setTempo", "transport.getTempo", [], exp_val, tol=0.1
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.1):
                    raise PreconditionError(
                        f"Precondition guard failed for transport.setTempo: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                        details={"expected": exp_val, "actual": before, "tol": 0.1},
                    )

        await self._session.call("transport.setTempo", {"bpm": bpm_val}, opts=call_opts)
        after = await self.get_tempo()
        return verify_mutation(
            "transport.setTempo",
            bpm_val,
            after,
            before=before,
            tol=0.1,
            strict=strict,
            fp=self._session.fp,
            remedy="Verify tempo range constraints (10.0 to 522.0 BPM).",
        )

    async def get_time(self, mode: int = 0) -> float:
        """Retrieve normalized song playback position (0.0 to 1.0) or beats."""
        res = await self._session.call("transport.getSongPos", {"mode": mode})
        return float(res) if res is not None else 0.0

    async def set_time(
        self,
        pos: float,
        *,
        expect: float | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized song playback position with read-back verification."""
        pos_val = float(pos)
        before = await self.get_time()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = float(expect)
                guard = build_expect_guard(
                    "transport.setSongPos", "transport.getSongPos", [], exp_val, tol=0.05
                )
                call_opts = {"expect": guard}
                if not tolerance_matches(exp_val, before, tol=0.05):
                    raise PreconditionError(
                        f"Precondition guard failed for transport.setSongPos: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call("transport.setSongPos", {"pos": pos_val}, opts=call_opts)
        after = await self.get_time()
        return verify_mutation(
            "transport.setSongPos",
            pos_val,
            after,
            before=before,
            tol=0.05,
            strict=strict,
            fp=self._session.fp,
            remedy="Ensure playback position is within song boundaries.",
        )

    async def get_loop_mode(self) -> int:
        """Retrieve loop mode (0 = Pattern, 1 = Song)."""
        res = await self._session.call("transport.getLoopMode", {})
        return int(res) if res is not None else 0

    async def set_loop_mode(
        self,
        mode: int | None = None,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set or toggle loop playback mode (0 = Pattern, 1 = Song)."""
        before = await self.get_loop_mode()
        target = int(mode) if mode is not None else (1 if before == 0 else 0)
        call_args: dict[str, Any] = {"mode": target} if mode is not None else {}

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = int(expect)
                guard = build_expect_guard(
                    "transport.setLoopMode", "transport.getLoopMode", [], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for transport.setLoopMode: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call("transport.setLoopMode", call_args, opts=call_opts)
        after = await self.get_loop_mode()
        return verify_mutation(
            "transport.setLoopMode",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            remedy="Verify loop mode value (0 = Pattern, 1 = Song).",
        )

    async def get_metronome(self) -> bool:
        """Retrieve metronome active state."""
        res = await self._session.call("transport.getMetronome", {})
        return bool(res)

    async def set_metronome(
        self,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Toggle or set metronome state with read-back verification."""
        target = bool(enabled)
        before = await self.get_metronome()

        call_opts: dict[str, Any] | None = None
        if expect is not None:
            if isinstance(expect, dict):
                call_opts = {"expect": expect}
            else:
                exp_val = bool(expect)
                guard = build_expect_guard(
                    "transport.setMetronome", "transport.getMetronome", [], exp_val
                )
                call_opts = {"expect": guard}
                if before != exp_val:
                    raise PreconditionError(
                        f"Precondition guard failed for transport.setMetronome: "
                        f"expected {exp_val}, current value is {before}",
                        code="E_PRECONDITION",
                    )

        await self._session.call(
            "transport.setMetronome",
            {"enabled": 1 if target else 0},
            opts=call_opts,
        )
        after = await self.get_metronome()
        return verify_mutation(
            "transport.setMetronome",
            target,
            after,
            before=before,
            strict=strict,
            fp=self._session.fp,
            remedy="Check whether metronome is available in current project mode.",
        )

    async def get_time_signature(self) -> tuple[int, int]:
        """Retrieve project time signature as (numerator, denominator) tuple."""
        res = await self._session.call("transport.getTimeSignature", {})
        if isinstance(res, (list, tuple)) and len(res) == 2:
            return int(res[0]), int(res[1])
        return (4, 4)

    async def metronome(
        self,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Alias for set_metronome."""
        return await self.set_metronome(enabled, expect=expect, strict=strict)

    async def time_signature(self) -> tuple[int, int]:
        """Alias for get_time_signature."""
        return await self.get_time_signature()


class SyncTransport:
    """Synchronous FL Studio transport interface wrapping AsyncTransport."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_transport: AsyncTransport,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_transport
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError(
                "Cannot issue transport operation: Session is disconnected.",
                code="E_DISCONNECTED",
                remedy="Establish session connection before calling transport operations.",
            )

    def play(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Start or resume playback in FL Studio transport."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.play, expect=expect, strict=strict))

    def stop(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Stop playback in FL Studio transport."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.stop, expect=expect, strict=strict))

    def record(
        self,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Toggle or engage recording mode in FL Studio transport."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.record, expect=expect, strict=strict)
        )

    def is_playing(self) -> bool:
        """Query whether transport playback is currently active."""
        self._check_connection()
        return self._portal.call(self._async.is_playing)

    def get_tempo(self) -> float:
        """Retrieve current project tempo in BPM."""
        self._check_connection()
        return self._portal.call(self._async.get_tempo)

    def set_tempo(
        self,
        bpm: float | Tempo,
        *,
        expect: float | Tempo | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set project tempo in BPM with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_tempo, bpm, expect=expect, strict=strict)
        )

    def get_time(self, mode: int = 0) -> float:
        """Retrieve normalized song playback position (0.0 to 1.0) or beats."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_time, mode=mode))

    def set_time(
        self,
        pos: float,
        *,
        expect: float | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[float]:
        """Set normalized song playback position with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_time, pos, expect=expect, strict=strict)
        )

    def get_loop_mode(self) -> int:
        """Retrieve loop mode (0 = Pattern, 1 = Song)."""
        self._check_connection()
        return self._portal.call(self._async.get_loop_mode)

    def set_loop_mode(
        self,
        mode: int | None = None,
        *,
        expect: int | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[int]:
        """Set or toggle loop playback mode (0 = Pattern, 1 = Song)."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_loop_mode, mode=mode, expect=expect, strict=strict)
        )

    def get_metronome(self) -> bool:
        """Retrieve metronome active state."""
        self._check_connection()
        return self._portal.call(self._async.get_metronome)

    def set_metronome(
        self,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Toggle or set metronome state with read-back verification."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.set_metronome, enabled=enabled, expect=expect, strict=strict
            )
        )

    def get_time_signature(self) -> tuple[int, int]:
        """Retrieve project time signature as (numerator, denominator) tuple."""
        self._check_connection()
        return self._portal.call(self._async.get_time_signature)

    def metronome(
        self,
        enabled: bool = True,
        *,
        expect: bool | dict[str, Any] | None = None,
        strict: bool = False,
    ) -> Verified[bool]:
        """Alias for set_metronome."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.set_metronome, enabled=enabled, expect=expect, strict=strict
            )
        )

    def time_signature(self) -> tuple[int, int]:
        """Alias for get_time_signature."""
        self._check_connection()
        return self._portal.call(self._async.get_time_signature)


__all__ = [
    "AsyncTransport",
    "SyncTransport",
]
