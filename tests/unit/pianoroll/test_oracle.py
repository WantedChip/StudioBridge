"""Unit tests for piano-roll oracle verification engine [ACT-02]."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from studiobridge.pianoroll.midi import write_midi_file
from studiobridge.pianoroll.oracle import (
    MockNoteOracleParser,
    OracleReport,
    OracleVerifier,
)
from studiobridge.pianoroll.types import Note


class DummySession:
    """Mock session recording calls for testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, op: str, args: dict[str, Any]) -> Any:
        self.calls.append((op, args))
        if op == "project.saveNewVersion":
            return True
        return None


def test_oracle_verifier_exact_match() -> None:
    """Verify oracle returns verified='oracle' when notes match exactly (# req: ACT-02)."""
    expected = [
        Note(pos=0, length=96, key=60, velocity=0.8),
        Note(pos=96, length=96, key=64, velocity=0.8),
        Note(pos=192, length=96, key=67, velocity=0.8),
    ]
    parser = MockNoteOracleParser(canned_notes=expected)
    verifier = OracleVerifier(parser=parser)

    import anyio

    async def run() -> OracleReport:
        return await verifier.verify(expected, trigger_save=False)

    report = anyio.run(run)

    assert report.matched is True
    assert report.verified == "oracle"
    assert report.expected_count == 3
    assert report.actual_count == 3
    assert report.matched_notes_count == 3
    assert len(report.mismatches) == 0


def test_oracle_verifier_note_count_mismatch() -> None:
    """Verify oracle reports verified='none' when note count does not match (# req: ACT-02)."""
    import anyio

    expected = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]
    actual = [
        Note(pos=0, length=96, key=60),
    ]
    parser = MockNoteOracleParser(canned_notes=actual)
    verifier = OracleVerifier(parser=parser)

    async def run() -> OracleReport:
        return await verifier.verify(expected, trigger_save=False)

    report = anyio.run(run)
    assert report.matched is False
    assert report.verified == "none"
    assert report.expected_count == 2
    assert report.actual_count == 1
    assert any("Note count mismatch" in m for m in report.mismatches)


def test_oracle_verifier_pitch_mismatch() -> None:
    """Verify oracle detects pitch mismatches and respects pitch_tolerance (# req: ACT-02)."""
    import anyio

    expected = [Note(pos=0, length=96, key=60)]
    actual = [Note(pos=0, length=96, key=62)]  # 2 semitones off

    parser = MockNoteOracleParser(canned_notes=actual)

    # 1. Zero tolerance fails
    verifier_strict = OracleVerifier(parser=parser, pitch_tolerance=0)

    async def run_strict() -> OracleReport:
        return await verifier_strict.verify(expected, trigger_save=False)

    report_strict = anyio.run(run_strict)
    assert report_strict.matched is False
    assert report_strict.verified == "none"
    assert any("pitch mismatch" in m for m in report_strict.mismatches)

    # 2. Tolerance of 2 semitones passes
    verifier_lenient = OracleVerifier(parser=parser, pitch_tolerance=2)

    async def run_lenient() -> OracleReport:
        return await verifier_lenient.verify(expected, trigger_save=False)

    report_lenient = anyio.run(run_lenient)
    assert report_lenient.matched is True
    assert report_lenient.verified == "oracle"


def test_oracle_verifier_timing_and_velocity_tolerance() -> None:
    """Verify oracle checks timing positions, duration, and velocities (# req: ACT-02)."""
    import anyio

    expected = [Note(pos=100, length=96, key=60, velocity=0.8)]
    actual = [Note(pos=102, length=94, key=60, velocity=0.82)]

    parser = MockNoteOracleParser(canned_notes=actual)
    verifier = OracleVerifier(
        parser=parser,
        time_tolerance_ticks=5,
        velocity_tolerance=0.05,
    )

    async def run() -> OracleReport:
        return await verifier.verify(expected, trigger_save=False)

    report = anyio.run(run)
    assert report.matched is True
    assert report.verified == "oracle"


def test_oracle_trigger_save_new_version() -> None:
    """Verify oracle triggers project save-new-version (FPT_SaveNew) (# req: ACT-02)."""
    import anyio

    session = DummySession()
    expected = [Note(pos=0, length=96, key=60)]
    parser = MockNoteOracleParser(canned_notes=expected)
    verifier = OracleVerifier(parser=parser)

    async def run() -> OracleReport:
        return await verifier.verify(expected, session=session, trigger_save=True)

    report = anyio.run(run)
    assert report.verified == "oracle"
    assert len(session.calls) == 1
    assert session.calls[0][0] == "project.saveNewVersion"


def test_mock_parser_pattern_channel_mapping() -> None:
    """Verify MockNoteOracleParser isolates notes by (pattern, channel) (# req: ACT-02)."""
    parser = MockNoteOracleParser()
    notes_p1_c0 = [Note(pos=0, length=96, key=60)]
    notes_p2_c0 = [Note(pos=0, length=96, key=72)]

    parser.set_notes(pattern=1, channel=0, notes=notes_p1_c0)
    parser.set_notes(pattern=2, channel=0, notes=notes_p2_c0)

    assert parser.parse_notes(Path("dummy.flp"), pattern=1, channel=0) == notes_p1_c0
    assert parser.parse_notes(Path("dummy.flp"), pattern=2, channel=0) == notes_p2_c0


def test_mock_parser_midi_file_parsing(tmp_path: Path) -> None:
    """Verify MockNoteOracleParser automatically parses real MIDI files (# req: ACT-02)."""
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=67),
    ]
    mid_file = tmp_path / "oracle_test.mid"
    write_midi_file(notes, mid_file)

    parser = MockNoteOracleParser()
    parsed = parser.parse_notes(mid_file)
    assert len(parsed) == 2
    assert parsed[0].key == 60
    assert parsed[1].key == 67
