"""Piano-roll note application and inspection MCP tools for StudioBridge.

Implements piano-roll tools per spec 06_l0d_pianoroll_actuation_render.md §15,
10_l2_interfaces.md §2.4, §2.8, and [ACT-01], [ACT-02]:
- notes_apply: Structured note application returning status and trigger tier (T1-T3).
- notes_read: Oracle-backed note reader returning patterns and notes from saved project state.
- notes_from_midi: Convert standard MIDI file into normalized note payload with path containment.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
from collections.abc import Callable, Coroutine, Sequence
from pathlib import Path
from typing import Any, TypeVar

import anyio

from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.core.errors import ArgumentError
from studiobridge.core.paths import validate_safe_path
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult
from studiobridge.pianoroll.midi import read_midi_notes
from studiobridge.pianoroll.oracle import MockNoteOracleParser, NoteOracleParser
from studiobridge.pianoroll.orchestrator import (
    NoteApplyOrchestrator,
    NoteApplyResult,
)
from studiobridge.pianoroll.types import ApplyMode, Note

T = TypeVar("T")


def _run_sync(coro_fn: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Execute asynchronous coroutine in synchronous context safely."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(anyio.run, coro_fn).result()
    return anyio.run(coro_fn)


def _resolve_client(client: Any = None, server: Any = None) -> Any:
    """Resolve active Studio client from explicit arg or server reference."""
    if client is not None:
        return client
    if server is not None and getattr(server, "client", None) is not None:
        return server.client
    return None


class NotesTools:
    """Provider for piano roll note operations and MIDI translation MCP tools."""

    def __init__(
        self,
        client: Any = None,
        server: Any = None,
        config: StudioBridgeConfig | None = None,
        orchestrator: NoteApplyOrchestrator | None = None,
        oracle_parser: NoteOracleParser | None = None,
    ) -> None:
        self.client = client
        self.server = server
        self.config = config or load_config()
        self.orchestrator = orchestrator or NoteApplyOrchestrator(config=self.config)
        self.oracle_parser = oracle_parser or MockNoteOracleParser()

    def _get_active_session(self) -> Any:
        """Resolve session from active client if connected."""
        client = _resolve_client(self.client, self.server)
        if client is None:
            return None
        session = getattr(client, "_session", None)
        if session is None and hasattr(client, "_async"):
            session = getattr(client._async, "session", None)
        return session

    def notes_apply(
        self,
        notes: Sequence[Any] | None = None,
        file: str | Path | None = None,
        channel: int | None = None,
        pattern: int | None = None,
        mode: ApplyMode | str = "append",
        range: Sequence[int] | None = None,
        ppq: int | None = None,
        job_id: str | None = None,
        verify: str = "none",
        fallback: str = "none",
        allow_focus_steal: bool | None = None,
        force: bool = False,
        dry_run: bool = False,
        target_flp: str | Path | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Apply structured notes to FL Studio piano roll returning honest tier execution status.

        # req: ACT-01, ACT-02
        """
        payload_notes: list[Any] = []

        # 1. Parse notes from file argument if provided
        if file is not None:
            safe_file = validate_safe_path(file)
            if not safe_file.exists():
                raise ArgumentError(f"Notes file not found: '{safe_file}'", code="E_ARGS")

            suffix = safe_file.suffix.lower()
            if suffix == ".mid":
                _, parsed_midi = read_midi_notes(safe_file)
                payload_notes.extend(parsed_midi)
            elif suffix == ".json":
                try:
                    data = json.loads(safe_file.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        payload_notes.extend(data)
                    elif (
                        isinstance(data, dict)
                        and "notes" in data
                        and isinstance(data["notes"], list)
                    ):
                        payload_notes.extend(data["notes"])
                    else:
                        payload_notes.append(data)
                except Exception as exc:
                    raise ArgumentError(
                        f"Failed to parse notes JSON file '{safe_file}': {exc}", code="E_ARGS"
                    ) from exc
            else:
                raise ArgumentError(
                    f"Unsupported notes file format '{suffix}'. Supported: .mid, .json",
                    code="E_ARGS",
                )

        # 2. Add notes directly supplied as sequence
        if notes is not None:
            if isinstance(notes, (list, tuple)):
                payload_notes.extend(notes)
            else:
                payload_notes.append(notes)

        if not payload_notes:
            raise ArgumentError(
                "Either 'notes' array or 'file' path must be provided.", code="E_ARGS"
            )

        # 3. Format range tuple if specified
        range_ticks: tuple[int, int] | None = None
        if range is not None and len(range) >= 2:
            range_ticks = (int(range[0]), int(range[1]))

        # 4. Resolve safe target_flp if oracle verification is requested
        safe_flp = None
        if target_flp is not None:
            safe_flp = validate_safe_path(target_flp)

        # 5. Execute via NoteApplyOrchestrator
        session = self._get_active_session()

        async def _apply() -> NoteApplyResult:
            return await self.orchestrator.apply_notes(
                notes=payload_notes,
                session=session,
                channel=channel,
                pattern=pattern,
                mode=mode,
                range_ticks=range_ticks,
                job_id=job_id,
                ppq=ppq,
                allow_focus_steal=allow_focus_steal,
                force=force,
                dry_run=dry_run,
                verify=verify,  # type: ignore
                oracle_parser=self.oracle_parser,
                fallback=fallback,  # type: ignore
                target_flp=safe_flp,
            )

        res = _run_sync(_apply)

        receipt: dict[str, Any] = {
            "status": res.status,
            "applied": res.applied,
            "trigger": res.trigger,
            "job_id": res.job_id,
            "notes_count": res.notes_count,
            "channel": res.channel,
            "pattern": res.pattern,
            "verified": res.verified,
            "script_path": str(res.script_path) if res.script_path else None,
            "instructions": res.instructions,
            "details": res.details,
        }

        human_text = (
            f"Note application {res.status} via {res.trigger} "
            f"({res.notes_count} note(s), job {res.job_id}, verified={res.verified})."
        )
        if res.instructions:
            human_text += "\n" + "\n".join(res.instructions)

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=(res.status == "failed"),
        )

    def notes_read(
        self,
        flp_path: str | Path,
        pattern: int = 1,
        channel: int = 0,
        **kwargs: Any,
    ) -> ToolResult:
        """Read patterns and notes from saved project file (.flp or .mid) via oracle parser.

        # req: ACT-02, MCP-20
        """
        safe_path = validate_safe_path(flp_path)
        if not safe_path.exists():
            raise ArgumentError(f"Target project file not found: '{safe_path}'", code="E_ARGS")

        if safe_path.suffix.lower() == ".mid":
            _, raw_notes = read_midi_notes(safe_path)
            notes_list = raw_notes
        else:
            parser = self.oracle_parser or MockNoteOracleParser()
            notes_list = parser.parse_notes(safe_path, pattern=pattern, channel=channel)

        note_dicts: list[dict[str, Any]] = []
        for n in notes_list:
            if isinstance(n, Note):
                note_dicts.append(n.to_dict())
            elif isinstance(n, dict):
                note_dicts.append(n)
            elif hasattr(n, "to_dict"):
                note_dicts.append(n.to_dict())
            else:
                note_dicts.append(dict(n))

        receipt: dict[str, Any] = {
            "flp_path": str(safe_path),
            "pattern": int(pattern),
            "channel": int(channel),
            "count": len(note_dicts),
            "notes": note_dicts,
        }

        human_text = (
            f"Read {len(note_dicts)} note(s) from '{safe_path.name}' "
            f"(pattern {pattern}, channel {channel})."
        )
        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def notes_from_midi(
        self,
        path: str | Path,
        ppq: int = 96,
        **kwargs: Any,
    ) -> ToolResult:
        """Convert standard MIDI file into structured note payload with path containment.

        # req: MCP §2.8
        """
        safe_path = validate_safe_path(path)
        if not safe_path.exists():
            raise ArgumentError(f"MIDI file not found: '{safe_path}'", code="E_ARGS")

        file_ppq, parsed_notes = read_midi_notes(safe_path)

        # Scale tick positions/lengths if target PPQ is specified and differs
        effective_ppq = int(ppq) if ppq else file_ppq
        if effective_ppq != file_ppq and file_ppq > 0:
            ratio = float(effective_ppq) / float(file_ppq)
            scaled: list[Note] = []
            for n in parsed_notes:
                scaled.append(
                    Note(
                        pos=int(round(n.pos * ratio)),
                        length=max(1, int(round(n.length * ratio))),
                        key=n.key,
                        velocity=n.velocity,
                        pan=n.pan,
                        release=n.release,
                        color=n.color,
                        group=n.group,
                        fcut=n.fcut,
                        fres=n.fres,
                        slide=n.slide,
                    )
                )
            parsed_notes = scaled

        note_dicts = [n.to_dict() for n in parsed_notes]

        receipt: dict[str, Any] = {
            "path": str(safe_path),
            "ppq": effective_ppq,
            "count": len(note_dicts),
            "notes": note_dicts,
        }

        human_text = (
            f"Decoded {len(note_dicts)} note(s) from MIDI file '{safe_path.name}' "
            f"at {effective_ppq} PPQ."
        )
        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )


def get_notes_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for piano-roll notes MCP tool suite."""
    provider = NotesTools(client=client, server=server)

    s_apply = get_schema("notes_apply")
    s_read = get_schema("notes_read")
    s_midi = get_schema("notes_from_midi")

    return [
        ToolDefinition(
            name="notes_apply",
            title=s_apply.get("title", "Notes Apply"),
            description=s_apply.get(
                "description",
                (
                    "Apply structured note arrays to the FL Studio piano roll with "
                    "honest tier execution metadata."
                ),
            ),
            input_schema=s_apply.get("inputSchema", {}),
            toolset="notes",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.notes_apply,
        ),
        ToolDefinition(
            name="notes_read",
            title=s_read.get("title", "Notes Read"),
            description=s_read.get(
                "description",
                "Oracle-backed note reader returning patterns and notes from saved project state.",
            ),
            input_schema=s_read.get("inputSchema", {}),
            toolset="notes",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.notes_read,
        ),
        ToolDefinition(
            name="notes_from_midi",
            title=s_midi.get("title", "Notes From MIDI"),
            description=s_midi.get(
                "description",
                "Convert a Standard MIDI File (.mid) into a structured note payload.",
            ),
            input_schema=s_midi.get("inputSchema", {}),
            toolset="notes",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.notes_from_midi,
        ),
    ]


__all__ = [
    "NotesTools",
    "get_notes_tools",
]
