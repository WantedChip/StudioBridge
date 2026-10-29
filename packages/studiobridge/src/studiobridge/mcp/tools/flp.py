"""Offline FL Studio project (.flp) MCP tool suite.

Implements offline project inspection, diffing, validation, editing, save-as,
and template instantiation [MCP-SEC, FLP-30..40].
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from studiobridge.core.errors import ArgumentError
from studiobridge.core.paths import validate_safe_path
from studiobridge.flp.diff import diff_projects
from studiobridge.flp.model.elements import Note
from studiobridge.flp.model.project import Project
from studiobridge.flp.validate.invariants import check_invariants
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult


def _parse_notes(raw_notes: Sequence[Any]) -> list[Note]:
    """Convert raw note definitions (dicts or Note instances) into typed Note objects."""
    notes: list[Note] = []
    for item in raw_notes:
        if isinstance(item, Note):
            notes.append(item)
        elif isinstance(item, dict):
            notes.append(
                Note(
                    pos=int(item.get("pos", 0)),
                    len=int(item.get("len", item.get("length", 96))),
                    key=int(item.get("key", 60)),
                    velocity=float(item.get("velocity", 0.8)),
                    pan=float(item.get("pan", 0.0)),
                    release=int(item.get("release", 64)),
                    fcut=float(item.get("fcut", 0.0)),
                    fres=float(item.get("fres", 0.0)),
                    group=int(item.get("group", 0)),
                    color=int(item["color"]) if item.get("color") is not None else None,
                    slide=bool(item.get("slide", False)),
                )
            )
        else:
            raise ArgumentError(
                f"Unsupported note item type: {type(item).__name__}",
                code="E_ARGS",
            )
    return notes


class FlpTools:
    """Provider for offline FL Studio project manipulation and inspection MCP tools."""

    def __init__(self, client: Any = None, server: Any = None) -> None:
        self.client = client
        self.server = server

    def flp_inspect(
        self,
        file: str,
        fields: list[str] | str | None = None,
        max_channels: int = 100,
        max_patterns: int = 100,
        include_empty_tracks: bool = False,
    ) -> ToolResult:
        """Inspect offline project structure without launching FL."""
        safe_path = validate_safe_path(file)
        if not safe_path.is_file():
            raise ArgumentError(f"Project file not found: '{safe_path}'", code="E_NOT_FOUND")

        project = Project.load(safe_path)

        # Resolve field filtering
        if fields is None:
            req_fields = {"all"}
        elif isinstance(fields, str):
            req_fields = {f.strip().lower() for f in fields.split(",") if f.strip()}
        else:
            req_fields = {str(f).strip().lower() for f in fields}
        include_all = "all" in req_fields or not req_fields

        # Metadata with untrusted marker per [SEC-05]
        metadata = {
            "title": project.title,
            "author": project.author,
            "comments": project.comments,
            "untrusted": True,
        }

        # Channels with untrusted names
        channels_summary: list[dict[str, Any]] = []
        if include_all or "channels" in req_fields:
            for ch in project.channels[:max_channels]:
                channels_summary.append(
                    {
                        "index": ch.index,
                        "name": ch.name,
                        "type": ch.channel_type,
                        "color": ch.color,
                        "volume": round(ch.volume, 3),
                        "pan": round(ch.pan, 3),
                        "mixer_track": ch.target_mixer_track,
                        "untrusted": True,
                    }
                )

        # Patterns with untrusted names
        patterns_summary: list[dict[str, Any]] = []
        if include_all or "patterns" in req_fields:
            for pat in project.patterns[:max_patterns]:
                patterns_summary.append(
                    {
                        "number": pat.number,
                        "name": pat.name,
                        "color": pat.color,
                        "note_count": len(pat.notes),
                        "untrusted": True,
                    }
                )

        # Mixer tracks with untrusted names
        mixer_tracks: list[dict[str, Any]] = []
        if include_all or "mixer" in req_fields:
            for trk in project.mixer:
                is_default = (
                    trk.index != 0
                    and trk.name == f"Insert {trk.index}"
                    and abs(trk.volume - 0.8) < 0.001
                    and abs(trk.pan) < 0.001
                    and not trk.mute
                    and not trk.solo
                    and not any(not s.is_empty for s in trk.slots)
                )
                if include_empty_tracks or not is_default:
                    mixer_tracks.append(
                        {
                            "index": trk.index,
                            "name": trk.name,
                            "volume": round(trk.volume, 3),
                            "pan": round(trk.pan, 3),
                            "muted": trk.mute,
                            "solo": trk.solo,
                            "slots_count": len([s for s in trk.slots if not s.is_empty]),
                            "untrusted": True,
                        }
                    )

        # Playlist information with untrusted markers
        playlist_info: dict[str, Any] = {}
        if include_all or "playlist" in req_fields:
            playlist_info = {
                "tracks_count": len(project.arrangement.tracks),
                "items_count": len(project.arrangement.items),
                "markers": [
                    {
                        "name": m.name,
                        "pos": m.position_ticks,
                        "untrusted": True,
                    }
                    for m in project.arrangement.markers
                ],
            }

        payload: dict[str, Any] = {
            "file": str(safe_path),
            "version": project.version,
            "tempo": round(project.tempo, 2),
            "ppq": project.ppq,
            "metadata": metadata if (include_all or "metadata" in req_fields) else {},
            "channel_count": len(project.channels),
            "channels": channels_summary,
            "pattern_count": len(project.patterns),
            "patterns": patterns_summary,
            "mixer_track_count": len(project.mixer),
            "mixer_tracks": mixer_tracks,
            "playlist": playlist_info,
            "unmodeled_events_count": len(project.unmodeled_events),
        }

        text_summary = (
            f"FLP Project '{safe_path.name}' (FL {project.version}): "
            f"{len(project.channels)} channels, {len(project.patterns)} patterns, "
            f"tempo {round(project.tempo, 1)} BPM, PPQ {project.ppq}."
        )

        return ToolResult(
            content=[{"type": "text", "text": text_summary}],
            structured_content=payload,
            is_error=False,
        )

    def flp_diff(
        self,
        file_a: str,
        file_b: str,
    ) -> ToolResult:
        """Compare two FL Studio project files (.flp) and return structured differences."""
        path_a = validate_safe_path(file_a)
        path_b = validate_safe_path(file_b)

        if not path_a.is_file():
            raise ArgumentError(f"Project A file not found: '{path_a}'", code="E_NOT_FOUND")
        if not path_b.is_file():
            raise ArgumentError(f"Project B file not found: '{path_b}'", code="E_NOT_FOUND")

        proj_a = Project.load(path_a)
        proj_b = Project.load(path_b)
        diff = diff_projects(proj_a, proj_b)

        payload = {
            "file_a": str(path_a),
            "file_b": str(path_b),
            "has_differences": diff.has_differences,
            "diff": diff.to_dict(),
            "summary": diff.format_text(),
        }

        if diff.has_differences:
            diff_text = diff.format_text()
            text_summary = (
                f"Differences detected between '{path_a.name}' and '{path_b.name}':\n{diff_text}"
            )
        else:
            text_summary = (
                f"Projects '{path_a.name}' and '{path_b.name}' are semantically identical."
            )

        return ToolResult(
            content=[{"type": "text", "text": text_summary}],
            structured_content=payload,
            is_error=False,
        )

    def flp_validate(
        self,
        file: str,
        test_fl_load: bool = False,
        timeout_s: float = 30.0,
    ) -> ToolResult:
        """Execute invariant checks and static risk scoring on an FL Studio project file (.flp)."""
        safe_path = validate_safe_path(file)
        if not safe_path.is_file():
            raise ArgumentError(f"Project file not found: '{safe_path}'", code="E_NOT_FOUND")

        project = Project.load(safe_path)
        report = project.validate(test_fl_load=test_fl_load, timeout_s=timeout_s)

        payload = {
            "file": str(safe_path),
            "is_valid": report.is_valid,
            "is_safe_to_load": report.is_safe_to_load,
            "invariants": list(report.invariants),
            "risk": report.risk.to_dict(),
            "fl_load": report.fl_load.to_dict() if report.fl_load else None,
            "live_verification": (
                report.live_verification.to_dict() if report.live_verification else None
            ),
        }

        inv_count = len(report.invariants)
        status_str = "VALID" if report.is_valid else f"INVALID ({inv_count} violation(s))"
        risk_str = f"Risk: {report.risk.level.upper()} ({report.risk.score}/100)"
        text_summary = f"Validation for '{safe_path.name}': {status_str}, {risk_str}."

        return ToolResult(
            content=[{"type": "text", "text": text_summary}],
            structured_content=payload,
            is_error=False,
        )

    def flp_save_as(
        self,
        source: str,
        destination: str,
        force_unknown_version: bool = False,
    ) -> ToolResult:
        """Atomically save project to a new destination path with invariant validation."""
        src_path = validate_safe_path(source)
        dest_path = validate_safe_path(destination)

        if not src_path.is_file():
            raise ArgumentError(f"Source file not found: '{src_path}'", code="E_NOT_FOUND")

        if src_path.resolve() == dest_path.resolve():
            raise ArgumentError(
                "Destination cannot be identical to source in save_as; use in-place edit instead.",
                code="E_ARGS",
            )

        project = Project.load(src_path)
        saved_path = project.save_as(dest_path, force_unknown_version=force_unknown_version)
        size_bytes = saved_path.stat().st_size

        payload = {
            "source": str(src_path),
            "destination": str(saved_path),
            "size_bytes": size_bytes,
            "version": project.version,
            "is_valid": True,
            "message": f"Successfully saved project to '{saved_path.name}'.",
        }

        return ToolResult(
            content=[
                {
                    "type": "text",
                    "text": f"Project saved to '{saved_path}' ({size_bytes} bytes).",
                }
            ],
            structured_content=payload,
            is_error=False,
        )

    def flp_new_from_template(
        self,
        destination: str,
        template: str = "minimal",
        title: str | None = None,
        author: str | None = None,
        tempo: float | None = None,
        ppq: int | None = None,
    ) -> ToolResult:
        """Generate a clean project file from an existing seed template."""
        dest_path = validate_safe_path(destination)

        params: dict[str, Any] = {}
        if title is not None:
            params["title"] = str(title)
        if author is not None:
            params["author"] = str(author)
        if tempo is not None:
            params["tempo"] = float(tempo)
        if ppq is not None:
            params["ppq"] = int(ppq)

        project = Project.new(template=template, params=params)
        saved_path = project.save_as(dest_path)
        size_bytes = saved_path.stat().st_size

        payload = {
            "destination": str(saved_path),
            "template": template,
            "size_bytes": size_bytes,
            "channel_count": len(project.channels),
            "tempo": round(project.tempo, 2),
            "ppq": project.ppq,
            "message": f"Successfully created new project from template '{template}'.",
        }

        return ToolResult(
            content=[
                {
                    "type": "text",
                    "text": (
                        f"Created new project '{saved_path.name}' from template '{template}' "
                        f"({size_bytes} bytes, {len(project.channels)} channels, "
                        f"{project.tempo:.1f} BPM)."
                    ),
                }
            ],
            structured_content=payload,
            is_error=False,
        )

    def flp_edit(
        self,
        file: str,
        mutations: list[dict[str, Any]],
        destination: str | None = None,
        in_place: bool = False,
        force_unknown_version: bool = False,
    ) -> ToolResult:
        """Apply a validated list of mutations to an offline project."""
        src_path = validate_safe_path(file)
        if not src_path.is_file():
            raise ArgumentError(f"File not found: '{src_path}'", code="E_NOT_FOUND")

        if destination is not None:
            dest_path = validate_safe_path(destination)
        elif in_place:
            dest_path = src_path
        else:
            raise ArgumentError(
                "Target destination must be provided, or set in_place=True to overwrite.",
                code="E_ARGS",
            )

        if not isinstance(mutations, list):
            m_type = type(mutations).__name__
            raise ArgumentError(
                f"'mutations' must be an array of mutation objects, got {m_type}.",
                code="E_ARGS",
            )

        project = Project.load(src_path)
        mutator = project.mutate()

        for idx, mutation in enumerate(mutations):
            if not isinstance(mutation, dict):
                raise ArgumentError(
                    f"Mutation at index {idx} must be an object/dict.",
                    code="E_ARGS",
                )
            op = mutation.get("op") or mutation.get("action")
            if not op:
                raise ArgumentError(
                    f"Mutation at index {idx} is missing required 'op' field.",
                    code="E_ARGS",
                )
            self._apply_mutation(mutator, op, mutation, idx)

        # Validate structural invariants before saving
        check_invariants(project)

        # Save project atomically
        if dest_path.resolve() != src_path.resolve():
            saved_path = project.save_as(dest_path, force_unknown_version=force_unknown_version)
        else:
            saved_path = project.save(
                in_place=True,
                force_unknown_version=force_unknown_version,
                make_backup=True,
            )

        records = [r.to_dict() for r in mutator.records]
        payload = {
            "source": str(src_path),
            "destination": str(saved_path),
            "mutations_applied": len(records),
            "records": records,
            "is_valid": True,
            "message": f"Successfully applied {len(records)} mutation(s) to '{saved_path.name}'.",
        }

        return ToolResult(
            content=[
                {
                    "type": "text",
                    "text": f"Applied {len(records)} mutations to '{saved_path.name}'.",
                }
            ],
            structured_content=payload,
            is_error=False,
        )

    def _apply_mutation(
        self,
        mutator: Any,
        op: str,
        m: dict[str, Any],
        idx: int,
    ) -> None:
        """Dispatch a single mutation operation on the ProjectMutator instance."""
        if op == "set_tempo":
            bpm = float(m.get("bpm", m.get("tempo", 120.0)))
            mutator.set_tempo(bpm)
        elif op == "set_title":
            mutator.set_title(str(m.get("title", "")))
        elif op == "set_author":
            mutator.set_author(str(m.get("author", "")))
        elif op == "set_comments":
            mutator.set_comments(str(m.get("comments", m.get("comment", ""))))
        elif op == "add_pattern":
            mutator.add_pattern(
                name=m.get("name"),
                color=int(m["color"]) if m.get("color") is not None else None,
            )
        elif op in ("rename_pattern", "pattern_rename"):
            pat = int(m.get("pattern", m.get("pattern_number", m.get("number", 1))))
            mutator.rename_pattern(pat, str(m.get("name", "")))
        elif op in ("recolor_pattern", "pattern_recolor"):
            pat = int(m.get("pattern", m.get("pattern_number", m.get("number", 1))))
            mutator.recolor_pattern(pat, int(m.get("color", 0)))
        elif op == "set_notes":
            pat = int(m.get("pattern", m.get("pattern_number", m.get("number", 1))))
            ch = int(m.get("channel", m.get("channel_index", 0)))
            notes_raw = m.get("notes", [])
            notes = _parse_notes(notes_raw)
            mode = str(m.get("mode", "append"))
            mutator.set_notes(pat, ch, notes, mode=mode)
        elif op in ("clear_pattern", "pattern_clear"):
            pat = int(m.get("pattern", m.get("pattern_number", m.get("number", 1))))
            mutator.clear_pattern(pat)
        elif op == "add_channel_from_template":
            kind = str(m.get("kind", "sampler"))
            params = m.get("params") or {
                k: v for k, v in m.items() if k not in ("op", "action", "kind")
            }
            mutator.add_channel_from_template(kind, params)
        elif op in ("rename_channel", "channel_rename"):
            ch = int(m.get("channel", m.get("channel_index", m.get("index", 0))))
            mutator.rename_channel(ch, str(m.get("name", "")))
        elif op in ("recolor_channel", "channel_recolor"):
            ch = int(m.get("channel", m.get("channel_index", m.get("index", 0))))
            mutator.recolor_channel(ch, int(m.get("color", 0)))
        elif op == "set_mixer_target":
            ch = int(m.get("channel", m.get("channel_index", 0)))
            target = int(m.get("mixer_track", m.get("target", m.get("track", 0))))
            mutator.set_mixer_target(ch, target)
        elif op == "set_channel_volume":
            ch = int(m.get("channel", m.get("channel_index", 0)))
            mutator.set_channel_volume(ch, float(m.get("volume", 1.0)))
        elif op == "set_channel_pan":
            ch = int(m.get("channel", m.get("channel_index", 0)))
            mutator.set_channel_pan(ch, float(m.get("pan", 0.0)))
        elif op in ("rename_track", "track_rename"):
            trk = int(m.get("track", m.get("track_index", m.get("index", 0))))
            mutator.rename_track(trk, str(m.get("name", "")))
        elif op in ("recolor_track", "track_recolor"):
            trk = int(m.get("track", m.get("track_index", m.get("index", 0))))
            mutator.recolor_track(trk, int(m.get("color", 0)))
        elif op == "set_track_volume":
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_volume(trk, float(m.get("volume", 0.8)))
        elif op == "set_track_pan":
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_pan(trk, float(m.get("pan", 0.0)))
        elif op == "set_track_mute":
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_mute(trk, bool(m.get("mute", True)))
        elif op == "set_track_solo":
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_solo(trk, bool(m.get("solo", True)))
        elif op == "set_track_routing":
            src = int(m.get("source_track", m.get("source", 0)))
            tgt = int(m.get("target_track", m.get("target", 0)))
            enabled = bool(m.get("enabled", True))
            send_amount = float(m["send_amount"]) if m.get("send_amount") is not None else None
            mutator.set_track_routing(src, tgt, enabled=enabled, send_amount=send_amount)
        elif op == "set_slot_state":
            trk = int(m.get("track", m.get("track_index", 0)))
            slot = int(m.get("slot", m.get("slot_index", 0)))
            enabled = bool(m.get("enabled", True))
            mutator.set_slot_state(trk, slot, enabled=enabled)
        elif op == "add_playlist_item":
            trk = int(m.get("track", 0))
            start = int(m.get("start", 0))
            length = int(m.get("length", 96))
            pat = int(m["pattern"]) if m.get("pattern") is not None else None
            clip_ch = int(m["clip_channel"]) if m.get("clip_channel") is not None else None
            mutator.add_playlist_item(trk, start, length, pattern_number=pat, clip_channel=clip_ch)
        elif op == "move_playlist_item":
            item_idx = int(m.get("item_index", m.get("index", 0)))
            new_trk = int(m["new_track"]) if m.get("new_track") is not None else None
            new_start = int(m["new_start"]) if m.get("new_start") is not None else None
            mutator.move_playlist_item(item_idx, new_track=new_trk, new_start=new_start)
        elif op == "delete_playlist_item":
            item_idx = int(m.get("item_index", m.get("index", 0)))
            mutator.delete_playlist_item(item_idx)
        elif op in ("set_track_name", "set_playlist_track_name"):
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_name(trk, str(m.get("name", "")))
        elif op in ("set_track_color", "set_playlist_track_color"):
            trk = int(m.get("track", m.get("track_index", 0)))
            mutator.set_track_color(trk, int(m.get("color", 0)))
        elif op == "add_marker":
            name = str(m.get("name", "Marker"))
            pos = int(m.get("pos", 0))
            mutator.add_marker(name, pos)
        else:
            raise ArgumentError(
                f"Unknown mutation operation at index {idx}: '{op}'",
                code="E_INVALID_MUTATION",
            )


def get_flp_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for offline FLP project MCP tool suite."""
    provider = FlpTools(client=client, server=server)

    s_inspect = get_schema("flp_inspect")
    s_edit = get_schema("flp_edit")
    s_diff = get_schema("flp_diff")
    s_validate = get_schema("flp_validate")
    s_save_as = get_schema("flp_save_as")
    s_new = get_schema("flp_new_from_template")

    return [
        ToolDefinition(
            name="flp_inspect",
            title=s_inspect.get("title", "FLP Inspect"),
            description=s_inspect.get(
                "description",
                "Inspect offline FL Studio project structure without launching FL.",
            ),
            input_schema=s_inspect.get("inputSchema", {}),
            toolset="flp",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.flp_inspect,
        ),
        ToolDefinition(
            name="flp_edit",
            title=s_edit.get("title", "FLP Edit"),
            description=s_edit.get(
                "description",
                "Apply a validated list of mutations to an offline FL Studio project.",
            ),
            input_schema=s_edit.get("inputSchema", {}),
            toolset="flp",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.flp_edit,
        ),
        ToolDefinition(
            name="flp_diff",
            title=s_diff.get("title", "FLP Diff"),
            description=s_diff.get(
                "description",
                "Compare two FL Studio project files (.flp) and return structured differences.",
            ),
            input_schema=s_diff.get("inputSchema", {}),
            toolset="flp",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.flp_diff,
        ),
        ToolDefinition(
            name="flp_validate",
            title=s_validate.get("title", "FLP Validate"),
            description=s_validate.get(
                "description",
                (
                    "Execute structural invariant checks and static risk scoring "
                    "on an FL Studio project."
                ),
            ),
            input_schema=s_validate.get("inputSchema", {}),
            toolset="flp",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.flp_validate,
        ),
        ToolDefinition(
            name="flp_save_as",
            title=s_save_as.get("title", "FLP Save As"),
            description=s_save_as.get(
                "description",
                "Atomically save project to a new destination path with invariant validation.",
            ),
            input_schema=s_save_as.get("inputSchema", {}),
            toolset="flp",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.flp_save_as,
        ),
        ToolDefinition(
            name="flp_new_from_template",
            title=s_new.get("title", "FLP New From Template"),
            description=s_new.get(
                "description",
                "Generate a clean FL Studio project file from an existing seed template.",
            ),
            input_schema=s_new.get("inputSchema", {}),
            toolset="flp",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.flp_new_from_template,
        ),
    ]


__all__ = [
    "FlpTools",
    "get_flp_tools",
]
