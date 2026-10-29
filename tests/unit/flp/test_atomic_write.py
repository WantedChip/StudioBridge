"""Unit tests for atomic FLP project writing, fsync, backups, and version gating.

Verifies temporary file isolation, atomic replacement, backup generation on in-place writes,
write-risk blocking for unknown versions ([FLP-32]), and invariant rollback [FLP-31].
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from studiobridge.core.errors import (
    FlpInvariantViolationError,
    FlpVersionUnsupportedError,
    FlpWriteRiskError,
)
from studiobridge.flp import (
    Event,
    Note,
    Project,
    atomic_save,
)
from studiobridge.flp.codec.writer import serialize_events


def _build_test_flp_bytes(*, version: str = "26.1.0", tempo: float = 125.0) -> bytes:
    """Helper to assemble a test FLP file."""
    out = io.BytesIO()

    # Header
    out.write(b"FLhd")
    header_data = struct.pack("<HHH", 0, 1, 96)
    out.write(struct.pack("<I", len(header_data)))
    out.write(header_data)

    # Events
    events = [
        Event(id=199, raw=version.encode("ascii") + b"\x00"),
        Event(id=68, raw=struct.pack("<H", int(tempo))),
        Event(id=156, raw=struct.pack("<I", int(tempo * 1000))),
        Event(id=201, raw="Atomic Test Track".encode("utf-16-le") + b"\x00\x00"),
        Event(id=64, raw=struct.pack("<H", 0)),
        Event(id=200, raw="Master Instrument".encode("utf-16-le") + b"\x00\x00"),
        Event(id=215, raw=b"\x00" * 32),
        Event(id=65, raw=struct.pack("<H", 1)),
        Event(id=200, raw="Main Pattern".encode("utf-16-le") + b"\x00\x00"),
    ]
    ev_bytes = serialize_events(events)
    out.write(b"FLdt")
    out.write(struct.pack("<I", len(ev_bytes)))
    out.write(ev_bytes)

    return out.getvalue()


# =============================================================================
# 1. Atomic Save Workflow ([FLP-31])
# =============================================================================


def test_atomic_save_creates_new_file(tmp_path: Path) -> None:
    """atomic_save serializes project cleanly to a new file path [FLP-31]."""
    # req: FLP-31
    raw = _build_test_flp_bytes(tempo=128.0)
    proj = Project.load(raw)
    dest_file = tmp_path / "saved_song.flp"

    saved_path = atomic_save(proj, dest_file)
    assert saved_path == dest_file
    assert dest_file.is_file()
    assert dest_file.stat().st_size > 0

    # Verify written file re-parses with identical state
    re_proj = Project.load(dest_file)
    assert re_proj.tempo == 128.0
    assert re_proj.title == "Atomic Test Track"
    assert len(re_proj.channels) == 1
    assert re_proj.channels[0].name == "Master Instrument"


def test_project_save_as_method(tmp_path: Path) -> None:
    """Project.save_as delegates to atomic_save [FLP-31]."""
    # req: FLP-31
    raw = _build_test_flp_bytes()
    proj = Project.load(raw)
    dest_file = tmp_path / "project_save_as.flp"

    result = proj.save_as(dest_file)
    assert result == dest_file
    assert dest_file.is_file()


def test_project_save_method_without_source_file_fails() -> None:
    """Project.save without a file_path raises ValueError [FLP-31]."""
    # req: FLP-31
    raw = _build_test_flp_bytes()
    proj = Project.load(raw)  # loaded from bytes, so file_path is None

    with pytest.raises(ValueError) as exc_info:
        proj.save()
    assert "use save_as" in str(exc_info.value)


# =============================================================================
# 2. In-Place Overwrite Prevention and Backups ([FLP-31])
# =============================================================================


def test_in_place_overwrite_blocked_without_flag(tmp_path: Path) -> None:
    """Overwriting an existing file without in_place=True raises FlpWriteRiskError [FLP-31]."""
    # req: FLP-31
    orig_file = tmp_path / "existing.flp"
    orig_file.write_bytes(_build_test_flp_bytes(tempo=120.0))

    proj = Project.load(orig_file)
    proj.mutate().set_tempo(140.0)

    # Attempt overwrite without in_place=True
    with pytest.raises(FlpWriteRiskError) as exc_info:
        atomic_save(proj, orig_file, in_place=False)
    assert exc_info.value.code == "E_FLP_WRITE_RISK"
    assert "without in_place=True" in str(exc_info.value)

    # Original file must remain untouched
    re_check = Project.load(orig_file)
    assert re_check.tempo == 120.0


def test_in_place_overwrite_creates_timestamped_backup(tmp_path: Path) -> None:
    """Overwriting in-place with in_place=True creates a verified backup file [FLP-31]."""
    # req: FLP-31
    orig_file = tmp_path / "my_track.flp"
    orig_bytes = _build_test_flp_bytes(tempo=120.0)
    orig_file.write_bytes(orig_bytes)

    proj = Project.load(orig_file)
    proj.mutate().set_tempo(135.0)

    # Save in place
    saved_path = proj.save(in_place=True)
    assert saved_path == orig_file

    # Verify backup exists
    backups = list(tmp_path.glob("my_track.flp.bak-*"))
    assert len(backups) == 1
    backup_file = backups[0]
    assert backup_file.read_bytes() == orig_bytes

    # Verify target file has updated tempo
    updated_proj = Project.load(orig_file)
    assert updated_proj.tempo == 135.0


# =============================================================================
# 3. Version Gating Safety Gates ([FLP-32])
# =============================================================================


def test_version_gating_blocks_unknown_versions(tmp_path: Path) -> None:
    """Writing to an FLP project from an unknown/future version is blocked [FLP-32]."""
    # req: FLP-32
    raw = _build_test_flp_bytes(version="27.0.0")  # FL 27 is unknown
    proj = Project.load(raw)
    out_file = tmp_path / "future.flp"

    # Blocked by default
    with pytest.raises(FlpVersionUnsupportedError) as exc_info:
        atomic_save(proj, out_file, force_unknown_version=False)
    assert exc_info.value.code == "E_FLP_VERSION"
    assert "27.0.0" in str(exc_info.value)
    assert not out_file.exists()


def test_version_gating_override_with_force(tmp_path: Path) -> None:
    """Passing force_unknown_version=True permits writing to unknown versions [FLP-32]."""
    # req: FLP-32
    raw = _build_test_flp_bytes(version="27.0.0")
    proj = Project.load(raw)
    out_file = tmp_path / "future_forced.flp"

    saved = atomic_save(proj, out_file, force_unknown_version=True)
    assert saved == out_file
    assert out_file.is_file()

    re_proj = Project.load(out_file)
    assert re_proj.version == "27.0.0"


# =============================================================================
# 4. Invariant Failure Halts Writing Without Corrupting Destination ([FLP-31])
# =============================================================================


def test_invariant_violation_aborts_write(tmp_path: Path) -> None:
    """Structural invariant failure aborts write before touching destination [FLP-31]."""
    # req: FLP-31
    raw = _build_test_flp_bytes()
    proj = Project.load(raw)

    # Artificially inject invalid note key
    proj.pattern(1).notes[0] = [Note(pos=0, len=96, key=200)]  # invalid MIDI key

    dest_file = tmp_path / "invalid_project.flp"
    with pytest.raises(FlpInvariantViolationError) as exc_info:
        atomic_save(proj, dest_file)
    assert exc_info.value.code == "E_FLP_INVARIANT"
    assert not dest_file.exists()
    # Temporary files should be cleaned up
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_atomic_replace_cleans_up_on_failure(tmp_path: Path) -> None:
    """If replace fails, temporary files are safely unlinked without corruption."""
    raw = _build_test_flp_bytes()
    proj = Project.load(raw)
    dest_file = tmp_path / "fail_replace.flp"

    with (
        patch("os.replace", side_effect=OSError("Disk hardware error")),
        pytest.raises(OSError),
    ):
        atomic_save(proj, dest_file)

    assert not dest_file.exists()
    assert list(tmp_path.glob("*.tmp")) == []
