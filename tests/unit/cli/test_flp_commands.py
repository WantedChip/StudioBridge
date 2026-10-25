"""Unit tests for sbridge flp inspect, diff, and roundtrip CLI commands.

Verifies CLI command parsing, standard exit codes, and JSON serialization
per 10_l2_interfaces.md §3 and v0.5.2.
"""

from __future__ import annotations

import io
import json
import struct
from pathlib import Path
from typing import Any

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


# =============================================================================
# sbridge flp edit tests
# =============================================================================


def test_cli_flp_edit_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp edit applies mutations and saves to output file."""
    # req: FLP-30, FLP-31
    flp_path = _create_test_flp(tmp_path / "song.flp", title="Old Title", tempo=120.0)
    out_path = tmp_path / "edited.flp"

    code = cli_entry(
        [
            "flp",
            "edit",
            str(flp_path),
            "--tempo",
            "138",
            "--title",
            "Brand New Title",
            "--rename-channel",
            "0:808 Sub",
            "--out",
            str(out_path),
        ]
    )
    assert code == 0

    captured = capsys.readouterr()
    assert "[OK] Applied 3 mutations; saved atomically to edited.flp" in captured.out
    assert out_path.is_file()

    # Verify re-parsed values
    from studiobridge.flp import Project

    re_proj = Project.load(out_path)
    assert re_proj.tempo == 138.0
    assert re_proj.title == "Brand New Title"
    assert re_proj.channels[0].name == "808 Sub"


def test_cli_flp_edit_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp edit --json outputs structured mutation audit log."""
    # req: FLP-30, FLP-31
    flp_path = _create_test_flp(tmp_path / "song.flp", tempo=120.0)
    out_path = tmp_path / "edited.flp"

    code = cli_entry(
        [
            "flp",
            "edit",
            str(flp_path),
            "--tempo",
            "140",
            "--out",
            str(out_path),
            "--json",
        ]
    )
    assert code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["mutations_applied"] == 1
    assert payload["destination"] == str(out_path.resolve())


def test_cli_flp_edit_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp edit --dry-run validates mutations without modifying files."""
    # req: FLP-30
    flp_path = _create_test_flp(tmp_path / "song.flp", tempo=120.0)
    out_path = tmp_path / "should_not_exist.flp"

    code = cli_entry(
        [
            "flp",
            "edit",
            str(flp_path),
            "--tempo",
            "150",
            "--out",
            str(out_path),
            "--dry-run",
        ]
    )
    assert code == 0
    assert not out_path.exists()

    captured = capsys.readouterr()
    assert "[DRY-RUN] Verified 1 mutations" in captured.out


def test_cli_flp_edit_in_place_creates_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """sbridge flp edit --in-place modifies file and creates backup file."""
    # req: FLP-31
    flp_path = _create_test_flp(tmp_path / "song.flp", tempo=120.0)

    code = cli_entry(
        [
            "flp",
            "edit",
            str(flp_path),
            "--tempo",
            "160",
            "--in-place",
        ]
    )
    assert code == 0

    backups = list(tmp_path.glob("song.flp.bak-*"))
    assert len(backups) == 1

    from studiobridge.flp import Project

    re_proj = Project.load(flp_path)
    assert re_proj.tempo == 160.0


def test_cli_flp_edit_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp edit on missing file returns exit code 1."""
    code = cli_entry(["flp", "edit", "non_existent.flp", "--tempo", "130"])
    assert code == 1


def test_cli_flp_new_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp new generates functional .flp project via cli_entry (# req: FLP-40)."""
    out_file = tmp_path / "created.flp"
    code = cli_entry(
        [
            "flp",
            "new",
            str(out_file),
            "--template",
            "sampler",
            "--title",
            "Generated Beat",
            "--tempo",
            "138",
            "--json",
        ]
    )
    assert code == 0
    assert out_file.is_file()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["template"] == "sampler"
    assert data["title"] == "Generated Beat"
    assert data["tempo"] == 138.0


def test_cli_flp_template_list_entry(capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp template list prints templates via cli_entry (# req: FLP-40)."""
    code = cli_entry(["flp", "template", "list", "--json"])
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert any(t["name"] == "minimal" for t in data["templates"])
    assert any(f["name"] == "3x Osc" for f in data["fragments"])


def test_cli_flp_template_add_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp template add extracts fragment via cli_entry (# req: FLP-40)."""
    flp_path = _create_test_flp(tmp_path / "source.flp")
    code = cli_entry(
        [
            "flp",
            "template",
            "add",
            str(flp_path),
            "--select",
            "channel:0",
            "--name",
            "Kick Fragment",
            "--author",
            "Drum Programmer",
            "--json",
        ]
    )
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["fragment"]["name"] == "Kick Fragment"
    assert data["fragment"]["provenance"]["author"] == "Drum Programmer"


def test_cli_flp_validate_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp validate <file> outputs text validation report (# req: FLP-50)."""
    flp_path = _create_test_flp(tmp_path / "valid.flp")
    code = cli_entry(["flp", "validate", str(flp_path)])
    assert code == 0

    captured = capsys.readouterr()
    assert "Validating: valid.flp" in captured.out
    assert "Structural Invariants: PASS" in captured.out
    assert "Risk Assessment: LOW" in captured.out


def test_cli_flp_validate_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp validate <file> --json outputs machine-readable JSON (# req: FLP-50)."""
    flp_path = _create_test_flp(tmp_path / "valid.flp")
    code = cli_entry(["flp", "validate", str(flp_path), "--json"])
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["invariants"]["valid"] is True
    assert data["risk"]["level"] == "low"
    assert data["risk"]["is_safe_to_load"] is True


def test_cli_flp_validate_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    """sbridge flp validate missing file returns exit code 1."""
    code = cli_entry(["flp", "validate", "nonexistent.flp"])
    assert code == 1


def test_cli_flp_validate_in_fl_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """sbridge flp validate <file> --in-fl executes headless preflight (# req: FLP-50)."""
    flp_path = _create_test_flp(tmp_path / "song.flp")

    from studiobridge.flp.validate.fl_load import FlLoadHarness, FlLoadResult

    def fake_run(self: Any, project: Any, timeout_s: float = 30.0) -> FlLoadResult:
        return FlLoadResult(
            outcome="ok",
            exit_code=0,
            duration_s=1.2,
            output_generated=True,
        )

    monkeypatch.setattr(FlLoadHarness, "run", fake_run)

    code = cli_entry(["flp", "validate", str(flp_path), "--in-fl", "--json"])
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["fl_load"] is not None
    assert data["fl_load"]["outcome"] == "ok"
    assert data["fl_load"]["is_ok"] is True
