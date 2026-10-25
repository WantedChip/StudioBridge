"""Unit tests for piano-roll notes MCP tools per spec 06_l0d §15 and 10_l2_interfaces §2.4, §2.8.

Verifies:
1. Tool definitions and schemas for notes_apply, notes_read, notes_from_midi.
2. Structured note array application returning honest trigger tiers (T1-T3) (# req: ACT-01, ACT-02).
3. Mode support: append, replace_all, replace_range.
4. Input notes file reading (JSON and MIDI).
5. Path containment verification rejecting '..' traversal and UNC paths (# req: MCP §2.8).
6. Oracle-backed notes_read and SMF notes_from_midi translation.
7. Dispatch via StudioMcpServer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.core.errors import ArgumentError, SecurityError
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.mcp.tools.notes import NotesTools, get_notes_tools
from studiobridge.pianoroll.midi import write_midi_file
from studiobridge.pianoroll.oracle import MockNoteOracleParser
from studiobridge.pianoroll.types import Note


def test_notes_tool_definitions() -> None:
    """Verify tool definitions and schema availability for notes tool suite (# req: ACT-01)."""
    tools = get_notes_tools()
    names = {t.name for t in tools}
    assert names == {"notes_apply", "notes_read", "notes_from_midi"}

    for t in tools:
        assert t.toolset == "notes"
        schema = get_schema(t.name)
        assert schema is not None
        assert "inputSchema" in schema
        assert "outputSchema" in schema


def test_notes_apply_structured_notes(tmp_path: Path) -> None:
    """Verify notes_apply accepts structured notes and returns receipt (# req: ACT-01, ACT-02)."""
    pyscript_dir = tmp_path / "pyscripts"
    tools = NotesTools()
    tools.orchestrator.pyscript_dir = pyscript_dir

    raw_notes = [
        {"pos": 0, "length": 96, "key": 60, "velocity": 0.8},
        {"pos": 96, "length": 96, "key": 64, "velocity": 0.8},
        {"pos": 192, "length": 96, "key": 67, "velocity": 0.8},
    ]

    res = tools.notes_apply(
        notes=raw_notes,
        channel=0,
        pattern=1,
        mode="append",
        dry_run=True,
    )

    assert res.is_error is False
    data = res.structured_content
    assert data["status"] in ("applied", "pending")
    assert data["trigger"] in ("T1", "T2", "T3")
    assert data["notes_count"] == 3
    assert data["channel"] == 0
    assert data["pattern"] == 1
    assert data["job_id"].startswith("sbj-") or len(data["job_id"]) > 0


def test_notes_apply_modes(tmp_path: Path) -> None:
    """Verify notes_apply handles replace_all and replace_range modes (# req: ACT-01)."""
    tools = NotesTools()
    tools.orchestrator.pyscript_dir = tmp_path / "pyscripts"

    notes = [Note(pos=0, length=96, key=60), Note(pos=96, length=96, key=62)]

    # Test replace_all
    res_replace = tools.notes_apply(notes=notes, mode="replace_all", dry_run=True)
    assert res_replace.is_error is False
    assert res_replace.structured_content["notes_count"] == 2

    # Test replace_range
    res_range = tools.notes_apply(notes=notes, mode="replace_range", range=[0, 384], dry_run=True)
    assert res_range.is_error is False
    assert res_range.structured_content["notes_count"] == 2


def test_notes_apply_from_json_file(tmp_path: Path) -> None:
    """Verify notes_apply reads notes definitions from a JSON file (# req: ACT-01)."""
    json_file = tmp_path / "chords.json"
    note_data = [
        {"pos": 0, "length": 96, "key": 60, "velocity": 0.9},
        {"pos": 0, "length": 96, "key": 64, "velocity": 0.9},
        {"pos": 0, "length": 96, "key": 67, "velocity": 0.9},
    ]
    json_file.write_text(json.dumps(note_data), encoding="utf-8")

    tools = NotesTools()
    tools.orchestrator.pyscript_dir = tmp_path / "pyscripts"

    res = tools.notes_apply(file=json_file, channel=2, pattern=3, dry_run=True)
    assert res.is_error is False
    data = res.structured_content
    assert data["notes_count"] == 3
    assert data["channel"] == 2
    assert data["pattern"] == 3


def test_notes_apply_from_midi_file(tmp_path: Path) -> None:
    """Verify notes_apply reads and parses notes from a Standard MIDI File (# req: ACT-01)."""
    midi_file = tmp_path / "lead.mid"
    original_notes = [
        Note(pos=0, length=96, key=72, velocity=0.8),
        Note(pos=96, length=96, key=74, velocity=0.8),
    ]
    write_midi_file(original_notes, midi_file, ppq=96)

    tools = NotesTools()
    tools.orchestrator.pyscript_dir = tmp_path / "pyscripts"

    res = tools.notes_apply(file=midi_file, dry_run=True)
    assert res.is_error is False
    assert res.structured_content["notes_count"] == 2


def test_notes_apply_empty_raises_argument_error() -> None:
    """Verify notes_apply raises ArgumentError when no notes are supplied."""
    tools = NotesTools()
    with pytest.raises(ArgumentError):
        tools.notes_apply(notes=[], file=None)


def test_notes_read(tmp_path: Path) -> None:
    """Verify notes_read returns pattern and channel notes via oracle parser (# req: ACT-02)."""
    dummy_flp = tmp_path / "project.flp"
    dummy_flp.write_bytes(b"FLhd\x06\x00\x00\x00")

    expected_notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]
    mock_parser = MockNoteOracleParser()
    mock_parser.set_notes(pattern=1, channel=0, notes=expected_notes)

    tools = NotesTools(oracle_parser=mock_parser)
    res = tools.notes_read(flp_path=dummy_flp, pattern=1, channel=0)

    assert res.is_error is False
    data = res.structured_content
    assert data["flp_path"] == str(dummy_flp.resolve())
    assert data["pattern"] == 1
    assert data["channel"] == 0
    assert data["count"] == 2
    assert len(data["notes"]) == 2
    assert data["notes"][0]["key"] == 60


def test_notes_from_midi(tmp_path: Path) -> None:
    """Verify notes_from_midi parses MIDI file to note list (# req: MCP §2.8)."""
    midi_file = tmp_path / "arpeggio.mid"
    notes = [
        Note(pos=0, length=48, key=60),
        Note(pos=48, length=48, key=63),
        Note(pos=96, length=48, key=67),
    ]
    write_midi_file(notes, midi_file, ppq=96)

    tools = NotesTools()
    res = tools.notes_from_midi(path=midi_file, ppq=96)

    assert res.is_error is False
    data = res.structured_content
    assert data["path"] == str(midi_file.resolve())
    assert data["ppq"] == 96
    assert data["count"] == 3
    assert len(data["notes"]) == 3
    assert data["notes"][1]["key"] == 63


def test_notes_path_traversal_rejection() -> None:
    """Verify notes tools enforce containment and reject traversal (# req: MCP §2.8)."""
    tools = NotesTools()

    # Traversal attempts with '..'
    with pytest.raises(SecurityError):
        tools.notes_from_midi(path="../outside.mid")

    with pytest.raises(SecurityError):
        tools.notes_apply(file="dir/../../traversal.mid")

    with pytest.raises(SecurityError):
        tools.notes_read(flp_path="..\\system.flp")

    # Unauthorized UNC paths
    with pytest.raises(SecurityError):
        tools.notes_from_midi(path="\\\\evil-host\\share\\exploit.mid")

    with pytest.raises(SecurityError):
        tools.notes_apply(file="//remote-server/share/payload.json")


def test_notes_tools_server_dispatch(tmp_path: Path) -> None:
    """Verify notes tools can be dispatched via StudioMcpServer (# req: ACT-01)."""
    server = StudioMcpServer(toolsets="notes")
    active_names = {t.name for t in server.get_active_tools()}
    assert "notes_apply" in active_names
    assert "notes_read" in active_names
    assert "notes_from_midi" in active_names

    midi_file = tmp_path / "scale.mid"
    write_midi_file([Note(pos=0, length=96, key=60)], midi_file, ppq=96)

    call_res = server.call_tool(
        "notes_from_midi",
        {"path": str(midi_file), "ppq": 96},
    )

    assert call_res.get("isError") is False
    content = call_res.get("structuredContent", {})
    assert content.get("count") == 1
