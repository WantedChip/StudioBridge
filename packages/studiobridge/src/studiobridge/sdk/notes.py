"""Piano roll notes namespace for StudioBridge Python SDK.

Provides high-level typed note controllers (AsyncNotes and SyncNotes)
mounted on AsyncStudio.notes and Studio.notes.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from anyio.from_thread import BlockingPortal

from studiobridge.core.errors import DisconnectedError
from studiobridge.pianoroll.oracle import NoteOracleParser, OracleReport, OracleVerifier
from studiobridge.pianoroll.orchestrator import NoteApplyOrchestrator, NoteApplyResult
from studiobridge.pianoroll.types import DEFAULT_PPQ, ApplyMode, Note
from studiobridge.sdk.refs import Channel, Pattern

if TYPE_CHECKING:
    from studiobridge.sdk.session import Session


class AsyncNotes:
    """Asynchronous piano-roll note management and actuation interface."""

    def __init__(
        self,
        session: Session,
        orchestrator: NoteApplyOrchestrator | None = None,
    ) -> None:
        self._session = session
        cfg = getattr(session, "config", None)
        self._orchestrator = orchestrator or NoteApplyOrchestrator(config=cfg)

    @property
    def orchestrator(self) -> NoteApplyOrchestrator:
        """Underlying NoteApplyOrchestrator instance."""
        return self._orchestrator

    async def apply(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        *,
        channel: int | str | Channel | None = None,
        pattern: int | str | Pattern | None = None,
        mode: ApplyMode | str = "append",
        range_ticks: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
        allow_focus_steal: bool | None = None,
        force: bool = False,
        dry_run: bool = False,
        verify: Literal["none", "oracle", "covert"] = "none",
        oracle_parser: NoteOracleParser | None = None,
        fallback: Literal["none", "step_grid", "midi"] = "none",
        midi_out_path: Path | str | None = None,
        target_flp: Path | str | None = None,
    ) -> NoteApplyResult:
        """Apply notes to piano roll across tiered ladder (T1..T3) with honest status.

        # req: ACT-01, ACT-02
        """
        return await self._orchestrator.apply_notes(
            notes,
            session=self._session,
            channel=channel,
            pattern=pattern,
            mode=mode,
            range_ticks=range_ticks,
            job_id=job_id,
            ppq=ppq,
            allow_focus_steal=allow_focus_steal,
            force=force,
            dry_run=dry_run,
            verify=verify,
            oracle_parser=oracle_parser,
            fallback=fallback,
            midi_out_path=midi_out_path,
            target_flp=target_flp,
        )

    async def apply_step_grid(
        self,
        channel: int | str | Channel,
        steps: Sequence[int | bool | Note | Any],
        *,
        pattern: int | str | Pattern | None = None,
    ) -> NoteApplyResult:
        """Apply simple rhythm pattern via 16-step sequencer grid fallback.

        # req: ACT-01, ACT-02
        """
        return await self._orchestrator.apply_step_grid(
            channel=channel,
            steps=steps,
            pattern=pattern,
            session=self._session,
        )

    def export_midi(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        path: Path | str | None = None,
        ppq: int = DEFAULT_PPQ,
        tempo_bpm: float = 120.0,
    ) -> Path:
        """Export notes to standard MIDI file (.mid) fallback."""
        return self._orchestrator.export_midi(
            notes=notes,
            path=path,
            ppq=ppq,
            tempo_bpm=tempo_bpm,
        )

    async def verify_oracle(
        self,
        expected_notes: Sequence[Note],
        *,
        flp_path: Path | str | None = None,
        pattern: int = 1,
        channel: int = 0,
        parser: NoteOracleParser | None = None,
    ) -> OracleReport:
        """Verify applied notes via project save-new-version and oracle parser."""
        verifier = self._orchestrator.oracle_verifier
        if parser is not None:
            verifier = OracleVerifier(
                parser=parser,
                pitch_tolerance=verifier.pitch_tolerance,
                time_tolerance_ticks=verifier.time_tolerance_ticks,
                velocity_tolerance=verifier.velocity_tolerance,
            )
        return await verifier.verify(
            expected_notes=expected_notes,
            session=self._session,
            flp_path=flp_path,
            pattern=pattern,
            channel=channel,
        )


class SyncNotes:
    """Synchronous wrapper around AsyncNotes via BlockingPortal [SDK-01]."""

    def __init__(
        self,
        portal: BlockingPortal,
        async_notes: AsyncNotes,
        session: Session | None = None,
    ) -> None:
        self._portal = portal
        self._async = async_notes
        self._session = session

    def _check_connection(self) -> None:
        if self._session is not None and not self._session.is_connected:
            raise DisconnectedError("Operation failed: StudioBridge session is disconnected.")

    def apply(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        *,
        channel: int | str | Channel | None = None,
        pattern: int | str | Pattern | None = None,
        mode: ApplyMode | str = "append",
        range_ticks: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
        allow_focus_steal: bool | None = None,
        force: bool = False,
        dry_run: bool = False,
        verify: Literal["none", "oracle", "covert"] = "none",
        oracle_parser: NoteOracleParser | None = None,
        fallback: Literal["none", "step_grid", "midi"] = "none",
        midi_out_path: Path | str | None = None,
        target_flp: Path | str | None = None,
    ) -> NoteApplyResult:
        """Apply notes synchronously across tiered ladder (T1..T3)."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.apply,
                notes,
                channel=channel,
                pattern=pattern,
                mode=mode,
                range_ticks=range_ticks,
                job_id=job_id,
                ppq=ppq,
                allow_focus_steal=allow_focus_steal,
                force=force,
                dry_run=dry_run,
                verify=verify,
                oracle_parser=oracle_parser,
                fallback=fallback,
                midi_out_path=midi_out_path,
                target_flp=target_flp,
            )
        )

    def apply_step_grid(
        self,
        channel: int | str | Channel,
        steps: Sequence[int | bool | Note | Any],
        *,
        pattern: int | str | Pattern | None = None,
    ) -> NoteApplyResult:
        """Apply simple rhythm pattern synchronously via 16-step sequencer grid."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.apply_step_grid,
                channel,
                steps,
                pattern=pattern,
            )
        )

    def export_midi(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        path: Path | str | None = None,
        ppq: int = DEFAULT_PPQ,
        tempo_bpm: float = 120.0,
    ) -> Path:
        """Export notes synchronously to standard MIDI file (.mid)."""
        return self._async.export_midi(
            notes=notes,
            path=path,
            ppq=ppq,
            tempo_bpm=tempo_bpm,
        )

    def verify_oracle(
        self,
        expected_notes: Sequence[Note],
        *,
        flp_path: Path | str | None = None,
        pattern: int = 1,
        channel: int = 0,
        parser: NoteOracleParser | None = None,
    ) -> OracleReport:
        """Verify applied notes synchronously via oracle parser."""
        self._check_connection()
        return self._portal.call(
            functools.partial(
                self._async.verify_oracle,
                expected_notes,
                flp_path=flp_path,
                pattern=pattern,
                channel=channel,
                parser=parser,
            )
        )


__all__ = [
    "AsyncNotes",
    "SyncNotes",
]
