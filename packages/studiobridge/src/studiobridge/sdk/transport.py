"""Transport control namespace for StudioBridge Python SDK.

Provides high-level typed transport controllers (AsyncTransport and SyncTransport)
mounted on AsyncStudio.transport and Studio.transport per spec 09_l1_sdk.md §4.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError, UnverifiedWriteError
from studiobridge.sdk.types import Verified

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncTransport:
    """Asynchronous FL Studio transport control interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def play(self, *, strict: bool = False) -> Verified[bool]:
        """Start playback in FL Studio transport."""
        before = await self.is_playing()
        await self._session.call("transport.start", {})
        after = await self.is_playing()
        verified = after is True

        if strict and not verified:
            raise UnverifiedWriteError(
                "Failed to verify transport.play: playback is not active",
                target_value=True,
                actual_value=after,
                details={"before": before, "after": after},
                remedy="Ensure FL Studio audio device is enabled and not frozen.",
            )

        return Verified(
            value=after,
            requested=True,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
        )

    async def stop(self, *, strict: bool = False) -> Verified[bool]:
        """Stop playback in FL Studio transport."""
        before = await self.is_playing()
        await self._session.call("transport.stop", {})
        after = await self.is_playing()
        verified = after is False

        if strict and not verified:
            raise UnverifiedWriteError(
                "Failed to verify transport.stop: playback is still active",
                target_value=False,
                actual_value=after,
                details={"before": before, "after": after},
                remedy="Check whether recording or external sync is overriding transport stop.",
            )

        return Verified(
            value=after,
            requested=False,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
        )

    async def record(self, *, strict: bool = False) -> Verified[bool]:
        """Toggle or engage recording mode in FL Studio transport."""
        before = await self._is_recording()
        await self._session.call("transport.record", {})
        after = await self._is_recording()
        target = not before
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify transport.record: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"before": before, "after": after},
                remedy="Verify recording filter settings in FL Studio.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
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

    async def set_tempo(self, bpm: float, *, strict: bool = False) -> Verified[float]:
        """Set project tempo in BPM with read-back verification."""
        bpm_val = float(bpm)
        before = await self.get_tempo()
        await self._session.call("transport.setTempo", {"bpm": bpm_val})
        after = await self.get_tempo()
        tol = 0.1
        verified = abs(after - bpm_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify set_tempo: requested {bpm_val} BPM, got {after} BPM",
                target_value=bpm_val,
                actual_value=after,
                details={"before": before, "after": after, "tol": tol},
                remedy="Verify tempo range constraints (10.0 to 522.0 BPM).",
            )

        return Verified(
            value=after,
            requested=bpm_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after, "tol": tol},
        )

    async def get_time(self, mode: int = 0) -> float:
        """Retrieve normalized song playback position (0.0 to 1.0) or beats."""
        res = await self._session.call("transport.getSongPos", {"mode": mode})
        return float(res) if res is not None else 0.0

    async def set_time(self, pos: float, *, strict: bool = False) -> Verified[float]:
        """Set normalized song playback position with read-back verification."""
        pos_val = float(pos)
        before = await self.get_time()
        await self._session.call("transport.setSongPos", {"pos": pos_val})
        after = await self.get_time()
        tol = 0.05
        verified = abs(after - pos_val) <= tol

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify set_time: requested position {pos_val}, got {after}",
                target_value=pos_val,
                actual_value=after,
                details={"before": before, "after": after, "tol": tol},
                remedy="Ensure playback position is within song boundaries.",
            )

        return Verified(
            value=after,
            requested=pos_val,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after, "tol": tol},
        )

    async def get_loop_mode(self) -> int:
        """Retrieve loop mode (0 = Pattern, 1 = Song)."""
        res = await self._session.call("transport.getLoopMode", {})
        return int(res) if res is not None else 0

    async def set_loop_mode(
        self, mode: int | None = None, *, strict: bool = False
    ) -> Verified[int]:
        """Set or toggle loop playback mode (0 = Pattern, 1 = Song)."""
        before = await self.get_loop_mode()
        target = int(mode) if mode is not None else (1 if before == 0 else 0)
        call_args: dict[str, Any] = {"mode": target} if mode is not None else {}
        await self._session.call("transport.setLoopMode", call_args)
        after = await self.get_loop_mode()
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify set_loop_mode: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"before": before, "after": after},
                remedy="Verify loop mode value (0 = Pattern, 1 = Song).",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
        )

    async def _get_metronome(self) -> bool:
        """Query whether metronome click is enabled."""
        res = await self._session.call("transport.getMetronome", {})
        return bool(res)

    async def metronome(
        self,
        enabled: bool | None = None,
        *,
        strict: bool = False,
    ) -> Verified[bool]:
        """Toggle or explicitly configure metronome click state."""
        before = await self._get_metronome()
        target = bool(enabled) if enabled is not None else (not before)
        await self._session.call("transport.setMetronome", {"enabled": target})
        after = await self._get_metronome()
        verified = after == target

        if strict and not verified:
            raise UnverifiedWriteError(
                f"Failed to verify metronome: requested {target}, got {after}",
                target_value=target,
                actual_value=after,
                details={"before": before, "after": after},
                remedy="Check whether metronome is disabled in global audio settings.",
            )

        return Verified(
            value=after,
            requested=target,
            verified=verified,
            plane="live",
            settled=True,
            proof="readback",
            fp=self._session.fp,
            evidence={"before": before, "after": after},
        )

    async def time_signature(self) -> tuple[int, int]:
        """Retrieve project time signature as (numerator, denominator) tuple."""
        res = await self._session.call("transport.getTimeSignature", {})
        if isinstance(res, (list, tuple)) and len(res) >= 2:
            return (int(res[0]), int(res[1]))
        return (4, 4)


class SyncTransport:
    """Synchronous FL Studio transport interface wrapping AsyncTransport via BlockingPortal."""

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

    def play(self, *, strict: bool = False) -> Verified[bool]:
        """Start playback in FL Studio transport."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.play, strict=strict))

    def stop(self, *, strict: bool = False) -> Verified[bool]:
        """Stop playback in FL Studio transport."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.stop, strict=strict))

    def record(self, *, strict: bool = False) -> Verified[bool]:
        """Toggle or engage recording mode in FL Studio transport."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.record, strict=strict))

    def is_playing(self) -> bool:
        """Query whether transport playback is currently active."""
        self._check_connection()
        return self._portal.call(self._async.is_playing)

    def get_tempo(self) -> float:
        """Retrieve current project tempo in BPM."""
        self._check_connection()
        return self._portal.call(self._async.get_tempo)

    def set_tempo(self, bpm: float, *, strict: bool = False) -> Verified[float]:
        """Set project tempo in BPM with read-back verification."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.set_tempo, bpm, strict=strict))

    def get_time(self, mode: int = 0) -> float:
        """Retrieve normalized song playback position (0.0 to 1.0) or beats."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.get_time, mode=mode))

    def set_time(self, pos: float, *, strict: bool = False) -> Verified[float]:
        """Set normalized song playback position with read-back verification."""
        self._check_connection()
        return self._portal.call(functools.partial(self._async.set_time, pos, strict=strict))

    def get_loop_mode(self) -> int:
        """Retrieve loop mode (0 = Pattern, 1 = Song)."""
        self._check_connection()
        return self._portal.call(self._async.get_loop_mode)

    def set_loop_mode(self, mode: int | None = None, *, strict: bool = False) -> Verified[int]:
        """Set or toggle loop playback mode (0 = Pattern, 1 = Song)."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.set_loop_mode, mode=mode, strict=strict)
        )

    def metronome(self, enabled: bool | None = None, *, strict: bool = False) -> Verified[bool]:
        """Toggle or explicitly configure metronome click state."""
        self._check_connection()
        return self._portal.call(
            functools.partial(self._async.metronome, enabled=enabled, strict=strict)
        )

    def time_signature(self) -> tuple[int, int]:
        """Retrieve project time signature as (numerator, denominator) tuple."""
        self._check_connection()
        return self._portal.call(self._async.time_signature)


__all__ = [
    "AsyncTransport",
    "SyncTransport",
]
