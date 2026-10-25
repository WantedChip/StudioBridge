"""Unit tests for sbridge flp inspect, diff, and roundtrip CLI commands.

Verifies CLI command parsing, standard exit codes, and JSON serialization
per 10_l2_interfaces.md §3 and v0.5.2.
"""

from __future__ import annotations

import io
import json
import struct
from pathlib import Path

import pytest

from studiobridge.cli.main import cli_entry
from studiobridge.flp import Event
from studiobridge.flp.codec.writer import serialize_events


def _create_test_flp(path: Path, title: str = "CLI Song", tempo: float = 125.0) -> Path:
    """Helper to write a valid synthetic FLP file for CLI tests."""
    out = io.BytesIO()

    # Header
    out.write(b"FLhd")
    header_payload = struct.pack("<HHH", 0, 2, 96)
    out.write(struct.pack("<I", len(header_payload)))
    out.write(header_payload)

    events: list[Event] = [
        Event(id=199, raw=b"26.1.0\x00"),
        Event(id=68, raw=struct.pack("<H", int(tempo))),
        Event(id=156, raw=struct.pack("<I", int(tempo * 1000))),
        Event(id=201, raw=title.encode("utf-16-le") + b"\x00\x00"),
        Event(id=64, raw=struct.pack("<H", 0)),
        Event(id=200, raw="Kick".encode("utf-16-le") + b"\x00\x00"),
        Event(id=64, raw=struct.pack("<H", 1)),
        Event(id=200, raw="Snare".encode("utf-16-le") + b"\x00\x00"),
    ]

    events_payload = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(events_payload)))
    out.write(events_payload)

    path.write_bytes(out.getvalue())
    return path


def test_cli_flp_inspect_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp inspect <file> outputs formatted text summary."""
    # req: FLP-20
    flp_path = _create_test_flp(tmp_path / "song.flp", title="Test Inspect Track")

    code = cli_entry(["flp", "inspect", str(flp_path)])
    assert code == 0

    captured = capsys.readouterr()
    assert "Project: song.flp" in captured.out
    assert "Version: 26.1.0" in captured.out
    assert "Title: Test Inspect Track" in captured.out
    assert "125.00 BPM" in captured.out
    assert "Channels (2):" in captured.out


def test_cli_flp_inspect_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp inspect <file> --json outputs structured JSON."""
    # req: FLP-20
    flp_path = _create_test_flp(tmp_path / "song.flp")

    code = cli_entry(["flp", "inspect", str(flp_path), "--json"])
    assert code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert "project" in payload
    assert payload["summary"]["tempo"] == 125.0


def test_cli_flp_inspect_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp inspect non-existent file returns error code 1."""
    code = cli_entry(["flp", "inspect", "non_existent_file.flp"])
    assert code == 1


def test_cli_flp_diff_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp diff <a.flp> <b.flp> prints comparison."""
    # req: FLP-20
    flp_a = _create_test_flp(tmp_path / "a.flp", title="Mix A", tempo=120.0)
    flp_b = _create_test_flp(tmp_path / "b.flp", title="Mix B", tempo=130.0)

    code = cli_entry(["flp", "diff", str(flp_a), str(flp_b)])
    assert code == 0

    captured = capsys.readouterr()
    assert "Diffing a.flp -> b.flp:" in captured.out
    assert "120.0" in captured.out
    assert "130.0" in captured.out


def test_cli_flp_diff_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp diff <a.flp> <b.flp> --json outputs structured diff JSON."""
    # req: FLP-20
    flp_a = _create_test_flp(tmp_path / "a.flp", title="Mix A")
    flp_b = _create_test_flp(tmp_path / "b.flp", title="Mix B")

    code = cli_entry(["flp", "diff", str(flp_a), str(flp_b), "--json"])
    assert code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert "diff" in payload
    assert payload["diff"]["has_differences"] is True


def test_cli_flp_roundtrip_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp roundtrip verifies byte-identical re-serialization."""
    # req: FLP-20
    flp_path = _create_test_flp(tmp_path / "roundtrip.flp")

    code = cli_entry(["flp", "roundtrip", str(flp_path)])
    assert code == 0

    captured = capsys.readouterr()
    assert "[OK] Byte-identical roundtrip verified" in captured.out


def test_cli_flp_roundtrip_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp roundtrip --json outputs status and size."""
    # req: FLP-20
    flp_path = _create_test_flp(tmp_path / "roundtrip.flp")

    code = cli_entry(["flp", "roundtrip", str(flp_path), "--json"])
    assert code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["byte_identical"] is True
    assert payload["size_bytes"] > 0
