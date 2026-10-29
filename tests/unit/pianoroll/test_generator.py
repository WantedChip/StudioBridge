"""Unit tests for piano-roll script generator, templates, and idempotency [PR-01]..[PR-06]."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import types
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from studiobridge.core.errors import ArgumentError, PayloadTooLargeError
from studiobridge.pianoroll.generator import (
    PyscriptGenerator,
    generate_pyscript,
    generate_pyscript_jobs,
)
from studiobridge.pianoroll.templates import render_apply_script
from studiobridge.pianoroll.types import (
    MAX_PAYLOAD_BYTES,
    Note,
    midi_to_note_name,
    normalize_color,
    normalize_filter,
    normalize_pan,
    normalize_release,
    normalize_velocity,
    note_name_to_midi,
    subdivision_to_ticks,
    ticks_to_subdivision,
)
from studiobridge.sdk.units import Bars, Beats, Ticks

# -----------------------------------------------------------------------------
# Mock FL Studio flpianoroll runtime for execution testing
# -----------------------------------------------------------------------------


class MockNote:
    """Mock flpianoroll.Note object."""

    def __init__(self) -> None:
        self.time: int = 0
        self.length: int = 0
        self.number: int = 0
        self.velocity: float = 0.0
        self.pan: float = 0.0
        self.release: float = 0.0
        self.color: int = 0
        self.group: int = 0
        self.fcut: float = 0.5
        self.fres: float = 0.5
        self.slide: bool = False

    def to_tuple(self) -> tuple[int, int, int, float, float, float, int, int, float, float, bool]:
        return (
            self.time,
            self.length,
            self.number,
            round(self.velocity, 6),
            round(self.pan, 6),
            round(self.release, 6),
            self.color,
            self.group,
            round(self.fcut, 6),
            round(self.fres, 6),
            self.slide,
        )


class MockMarker:
    """Mock flpianoroll.Marker object."""

    def __init__(self) -> None:
        self.name: str = ""
        self.time: int = 0


class MockScore:
    """Mock flpianoroll.score object simulating FL Studio piano roll state."""

    def __init__(self) -> None:
        self.notes: list[MockNote] = []
        self.markers: list[MockMarker] = []

    @property
    def noteCount(self) -> int:
        return len(self.notes)

    @property
    def markerCount(self) -> int:
        return len(self.markers)

    def getNote(self, index: int) -> MockNote:
        return self.notes[index]

    def addNote(self, note: MockNote) -> None:
        self.notes.append(note)

    def deleteNote(self, index: int) -> None:
        del self.notes[index]

    def clearNotes(self, all_notes: bool = True) -> None:
        self.notes.clear()

    def getMarker(self, index: int) -> MockMarker:
        return self.markers[index]

    def addMarker(self, marker: MockMarker) -> None:
        self.markers.append(marker)

    def deleteMarker(self, index: int) -> None:
        del self.markers[index]

    def clearMarkers(self) -> None:
        self.markers.clear()


@pytest.fixture
def mock_fpr_runtime() -> Generator[types.ModuleType, None, None]:
    """Provide a mock flpianoroll module registered in sys.modules during test."""
    mod = types.ModuleType("flpianoroll")
    mod.Note = MockNote  # pyright: ignore[reportAttributeAccessIssue]
    mod.Marker = MockMarker  # pyright: ignore[reportAttributeAccessIssue]
    mod.score = MockScore()  # pyright: ignore[reportAttributeAccessIssue]

    saved = sys.modules.get("flpianoroll")
    sys.modules["flpianoroll"] = mod
    try:
        yield mod
    finally:
        if saved is not None:
            sys.modules["flpianoroll"] = saved
        else:
            sys.modules.pop("flpianoroll", None)


def execute_pyscript(script_code: str, score: MockScore) -> dict[str, Any]:
    """Execute generated .pyscript source code in mock flpianoroll environment."""
    mock_module = types.ModuleType("flpianoroll")
    mock_module.Note = MockNote  # pyright: ignore[reportAttributeAccessIssue]
    mock_module.Marker = MockMarker  # pyright: ignore[reportAttributeAccessIssue]
    mock_module.score = score  # pyright: ignore[reportAttributeAccessIssue]

    saved = sys.modules.get("flpianoroll")
    sys.modules["flpianoroll"] = mock_module
    scope: dict[str, Any] = {}
    try:
        compiled = compile(script_code, "<pyscript>", "exec")
        exec(compiled, scope)
        if "apply" in scope:
            scope["apply"](score)
        elif "applyScore" in scope:
            scope["applyScore"](score)
    finally:
        if saved is not None:
            sys.modules["flpianoroll"] = saved
        else:
            sys.modules.pop("flpianoroll", None)

    return scope


# -----------------------------------------------------------------------------
# Unit Tests
# -----------------------------------------------------------------------------


# req: PR-01
def test_pyscript_self_contained_template_and_modes() -> None:
    """Verify generated script is self-contained and supports append, replace_all, replace_range."""
    gen = PyscriptGenerator()
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]

    # Test append mode
    script_append = gen.generate(notes, mode="append", job_id="sbj-test-append")
    assert "import flpianoroll as fpr" in script_append
    assert 'MODE = "append"' in script_append
    assert 'JOB = "sbj-test-append"' in script_append
    assert "(0, 96, 60," in script_append
    assert "(96, 96, 64," in script_append

    # Test replace_all mode
    script_replace_all = gen.generate(notes, mode="replace_all", job_id="sbj-test-replall")
    assert 'MODE = "replace_all"' in script_replace_all

    # Test replace_range mode
    script_range = gen.generate(
        notes,
        mode="replace_range",
        time_range=(0, 192),
        job_id="sbj-test-range",
    )
    assert 'MODE = "replace_range"' in script_range
    assert "RANGE = (0, 192)" in script_range

    # Validation: replace_range requires time_range
    with pytest.raises(ArgumentError, match="Mode 'replace_range' requires time_range"):
        gen.generate(notes, mode="replace_range", time_range=None)

    # Validation: invalid mode
    with pytest.raises(ArgumentError, match="Invalid mode 'invalid'"):
        gen.generate(notes, mode="invalid")  # type: ignore[arg-type]


# req: PR-01
def test_pyscript_execution_append_mode() -> None:
    """Verify executing an append-mode pyscript adds notes without deleting existing ones."""
    score = MockScore()
    # Pre-populate score with an existing note
    initial_note = MockNote()
    initial_note.time = 0
    initial_note.length = 48
    initial_note.number = 50
    score.addNote(initial_note)

    notes = [
        Note(pos=96, length=96, key=60, velocity=0.8),
        Note(pos=192, length=96, key=67, velocity=0.7),
    ]
    script = generate_pyscript(notes, mode="append", job_id="sbj-exec-append")

    execute_pyscript(script, score)

    # Pre-existing note + 2 added notes = 3
    assert score.noteCount == 3
    assert score.getNote(0).number == 50
    assert score.getNote(1).number == 60
    assert score.getNote(2).number == 67

    # Verify status marker was set
    assert score.markerCount == 1
    assert score.getMarker(0).name == "JOB:sbj-exec-append:OK:2"


# req: PR-01
def test_pyscript_execution_replace_all_mode() -> None:
    """Verify executing a replace_all-mode pyscript clears existing notes and adds new ones."""
    score = MockScore()
    for pitch in (48, 52, 55):
        n = MockNote()
        n.time = 0
        n.length = 96
        n.number = pitch
        score.addNote(n)
    assert score.noteCount == 3

    new_notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]
    script = generate_pyscript(new_notes, mode="replace_all", job_id="sbj-exec-replall")

    execute_pyscript(script, score)

    # Existing 3 notes wiped; replaced by the 2 new notes
    assert score.noteCount == 2
    assert score.getNote(0).number == 60
    assert score.getNote(1).number == 64
    assert score.getMarker(0).name == "JOB:sbj-exec-replall:OK:2"


# req: PR-01
def test_pyscript_execution_replace_range_mode() -> None:
    """Verify executing a replace_range-mode pyscript deletes only notes in range."""
    score = MockScore()
    # Add notes at 0, 96, 192, 288
    for t, p in [(0, 48), (96, 50), (192, 52), (288, 55)]:
        n = MockNote()
        n.time = t
        n.length = 96
        n.number = p
        score.addNote(n)
    assert score.noteCount == 4

    # Replace range [96, 288) with single note at 144
    new_notes = [Note(pos=144, length=96, key=62)]
    gen = PyscriptGenerator()
    script = gen.generate(
        new_notes,
        mode="replace_range",
        time_range=(96, 288),
        job_id="sbj-exec-range",
    )

    execute_pyscript(script, score)

    # Notes at 96 and 192 deleted; 0 and 288 preserved; 144 added -> total 3
    assert score.noteCount == 3
    assert score.getNote(0).time == 0
    assert score.getNote(0).number == 48
    assert score.getNote(1).time == 288
    assert score.getNote(1).number == 55
    assert score.getNote(2).time == 144
    assert score.getNote(2).number == 62
    assert score.getMarker(0).name == "JOB:sbj-exec-range:OK:1"


# req: PR-02
def test_payload_chunking_and_sequencing() -> None:
    """Verify large payloads (> 200 KB) are automatically split and sequenced into sub-jobs."""
    gen = PyscriptGenerator()

    # Create 3,500 notes which serialize to ~220 KB (> 200 KB limit)
    notes = [Note(pos=i * 24, length=24, key=(60 + (i % 12)), velocity=0.8) for i in range(3500)]

    # generate() raises PayloadTooLargeError when exceeding limit
    with pytest.raises(PayloadTooLargeError) as exc_info:
        gen.generate(notes, mode="replace_all", job_id="sbj-large-payload")
    assert "exceeds limit" in str(exc_info.value)
    assert exc_info.value.details["parts_required"] > 1

    # generate_jobs() automatically chunks into sequential jobs
    jobs = gen.generate_jobs(notes, mode="replace_all", job_id="sbj-large-payload")
    assert len(jobs) >= 2

    # Every sub-job must strictly respect the 200 KB limit
    for job in jobs:
        assert job.byte_size <= MAX_PAYLOAD_BYTES, (
            f"Job {job.job_id} exceeded 200 KB: {job.byte_size}"
        )

    # Verify sequencing invariants: Part 1 has requested mode, subsequent parts append
    assert jobs[0].part_index == 1
    assert jobs[0].total_parts == len(jobs)
    assert jobs[0].mode == "replace_all"
    assert jobs[0].job_id.endswith("-01")
    assert 'MODE = "replace_all"' in jobs[0].script_content

    for job in jobs[1:]:
        assert job.mode == "append"
        assert 'MODE = "append"' in job.script_content
        assert job.total_parts == len(jobs)

    # Total notes preserved across all jobs
    total_notes_in_jobs = sum(j.note_count for j in jobs)
    assert total_notes_in_jobs == len(notes)


# req: PR-02
def test_payload_chunking_small_threshold_execution() -> None:
    """Verify sequential execution of chunked jobs produces complete note set."""
    # Use low byte limit (4,800 bytes) where overhead is ~3.5 KB to force chunking with 40 notes
    gen = PyscriptGenerator(max_payload_bytes=4800)
    notes = [Note(pos=i * 48, length=48, key=(50 + (i % 24)), velocity=0.75) for i in range(40)]

    jobs = gen.generate_jobs(notes, mode="replace_all", job_id="sbj-test-chunk-exec")
    assert len(jobs) >= 2

    score = MockScore()
    # Add dummy initial note
    dummy = MockNote()
    dummy.time = 0
    dummy.length = 96
    dummy.number = 36
    score.addNote(dummy)

    # Sequentially execute each sub-job
    for job in jobs:
        execute_pyscript(job.script_content, score)

    # Dummy note wiped by Part 1 replace_all, all 40 notes present
    assert score.noteCount == 40
    for i in range(40):
        assert score.getNote(i).number == 50 + (i % 24)
        assert score.getNote(i).time == i * 48


# req: PR-03
def test_idempotency_marker_prevents_duplicate_runs() -> None:
    """Verify in-script marker guard aborts accidental re-runs without duplicating notes."""
    score = MockScore()
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
    ]
    script = generate_pyscript(notes, mode="append", job_id="sbj-idempotent-001")

    # Run 1: applied cleanly
    execute_pyscript(script, score)
    assert score.noteCount == 2
    assert score.markerCount == 1
    assert score.getMarker(0).name == "JOB:sbj-idempotent-001:OK:2"

    # Run 2: accidental double-trigger (e.g. repeated Ctrl+Alt+Y)
    execute_pyscript(script, score)

    # Note count must remain 2, not 4!
    assert score.noteCount == 2
    assert score.markerCount == 1


# req: PR-03
def test_idempotency_marker_with_existing_job_marker() -> None:
    """Verify script aborts if a raw job marker already exists before notes are processed."""
    score = MockScore()
    existing_marker = MockMarker()
    existing_marker.name = "JOB:sbj-preexisting"
    existing_marker.time = 0
    score.addMarker(existing_marker)

    notes = [Note(pos=0, length=96, key=60)]
    script = generate_pyscript(notes, mode="append", job_id="sbj-preexisting")

    execute_pyscript(script, score)

    # Aborted immediately: 0 notes added
    assert score.noteCount == 0


# req: PR-04
def test_undo_grouping_and_in_script_count_validation() -> None:
    """Verify in-script note count validation asserts exact counts before status marker."""
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=67),
    ]
    script = generate_pyscript(notes, mode="append", job_id="sbj-validation-test")

    # Tamper with score to simulate a failure during addition (e.g. dropped note)
    class FailingScore(MockScore):
        def addNote(self, note: MockNote) -> None:
            # Drop note when key == 67
            if note.number != 67:
                super().addNote(note)

    failing_score = FailingScore()

    # Script must raise AssertionError on count mismatch
    with pytest.raises(AssertionError, match="Validation failure: expected 2 notes, got 1"):
        execute_pyscript(script, failing_score)

    # Status marker must NOT be set on validation failure
    assert failing_score.markerCount == 0


# req: PR-05
def test_project_ppq_resolution_and_musical_subdivisions() -> None:
    """Verify conversion of musical subdivisions into integer tick timestamps at project PPQ."""
    # 96 PPQ (standard default)
    assert subdivision_to_ticks("1/1", ppq=96) == 384  # whole note (4 beats)
    assert subdivision_to_ticks("1/2", ppq=96) == 192  # half note (2 beats)
    assert subdivision_to_ticks("1/4", ppq=96) == 96  # quarter note (1 beat)
    assert subdivision_to_ticks("1/8", ppq=96) == 48  # eighth note
    assert subdivision_to_ticks("1/16", ppq=96) == 24  # sixteenth note (1 step)
    assert subdivision_to_ticks("step", ppq=96) == 24
    assert subdivision_to_ticks("beat", ppq=96) == 96
    assert subdivision_to_ticks("bar", ppq=96) == 384
    assert subdivision_to_ticks("1/8t", ppq=96) == 32  # eighth triplet (96 / 3)
    assert subdivision_to_ticks("1/16t", ppq=96) == 16  # sixteenth triplet (48 / 3)
    assert subdivision_to_ticks("1/4d", ppq=96) == 144  # dotted quarter (1.5 * 96)

    # 192 PPQ (double resolution)
    assert subdivision_to_ticks("1/4", ppq=192) == 192
    assert subdivision_to_ticks("1/16", ppq=192) == 48

    # Duck-typing support for SDK units
    assert subdivision_to_ticks(Ticks(120), ppq=96) == 120
    assert subdivision_to_ticks(Beats(2.5), ppq=96) == 240
    assert subdivision_to_ticks(Bars(1.0), ppq=96) == 384

    # Reverse conversion
    assert ticks_to_subdivision(24, ppq=96) == "1/16"
    assert ticks_to_subdivision(96, ppq=96) == "1/4"


# req: PR-05
def test_velocity_and_pan_normalization() -> None:
    """Verify external MIDI values (0..127) translate accurately to flpianoroll floats."""
    # Velocity: 0..127 -> 0.0..1.0
    assert normalize_velocity(127) == 1.0
    assert normalize_velocity(0) == 0.0
    assert normalize_velocity(100) == pytest.approx(100 / 127.0, abs=1e-5)
    assert normalize_velocity(0.85) == 0.85  # Preserves float 0.0..1.0

    # Pan: 0..127 (center 64) -> -1.0..1.0
    assert normalize_pan(64) == 0.0  # Center
    assert normalize_pan(0) == -1.0  # Full left
    assert normalize_pan(127) == 1.0  # Full right
    assert normalize_pan(32) == -0.5
    assert normalize_pan(-0.4) == -0.4  # Preserves float -1.0..1.0

    # Release and filter
    assert normalize_release(64) == pytest.approx(64 / 127.0, abs=1e-5)
    assert normalize_filter(127) == 1.0
    assert normalize_filter(0) == 0.0

    # Color
    assert normalize_color(0) == 0
    assert normalize_color(15) == 15
    assert normalize_color(25) == 15  # Clamped to 15


# req: PR-05
def test_note_from_midi_and_pitch_names() -> None:
    """Verify Note.from_midi handles pitch strings and MIDI normalization."""
    # Middle C in FL Studio is C5 = MIDI 60
    assert note_name_to_midi("C5") == 60
    assert note_name_to_midi("A4") == 57
    assert note_name_to_midi("A5") == 69
    assert note_name_to_midi("F#4") == 54
    assert note_name_to_midi("Bb3") == 46
    assert midi_to_note_name(60) == "C5"
    assert midi_to_note_name(69) == "A5"

    note = Note.from_midi(
        pos="1/4",
        length="1/16",
        key="C5",
        velocity=100,
        pan=64,
        release=64,
        color=2,
        group=1,
        ppq=96,
    )
    assert note.pos == 96
    assert note.length == 24
    assert note.key == 60
    assert note.velocity == pytest.approx(100 / 127.0, abs=1e-5)
    assert note.pan == 0.0
    assert note.release == pytest.approx(64 / 127.0, abs=1e-5)
    assert note.color == 2
    assert note.group == 1
    assert note.slide is False


# req: PR-01
def test_render_apply_script_direct() -> None:
    """Verify direct template rendering via render_apply_script."""
    script = render_apply_script(job_id="sbj-direct-tmpl", notes=[], mode="append")
    assert 'JOB = "sbj-direct-tmpl"' in script
    assert "NOTES = []" in script


# req: PR-02
def test_generate_pyscript_jobs_convenience_helper() -> None:
    """Verify generate_pyscript_jobs convenience function returns valid PyscriptJob instances."""
    notes = [Note(pos=0, length=96, key=60)]
    jobs = generate_pyscript_jobs(notes, mode="append", job_id="sbj-helper-01")
    assert len(jobs) == 1
    assert jobs[0].job_id == "sbj-helper-01"
    assert jobs[0].note_count == 1


# req: PR-06
def test_single_file_regenerate_and_overwrite() -> None:
    """Verify single-file pyscript generation with baked note literals and zero external imports."""
    gen = PyscriptGenerator()
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=62),
    ]

    script = gen.generate(notes, mode="append", job_id="sbj-single-file-01")
    # Verify script starts with device header
    assert script.startswith("# name=SBridge Apply")
    # Verify exactly one import (flpianoroll)
    import_lines = [line for line in script.splitlines() if line.startswith("import ")]
    assert import_lines == ["import flpianoroll as fpr"]


# req: PR-01
def test_python_39_syntax_validation() -> None:
    """Verify generated .pyscript source code compiles under Python 3.9 syntax without errors."""
    notes = [
        Note(
            pos=0,
            length=96,
            key=60,
            velocity=0.8,
            pan=-0.5,
            release=0.5,
            color=1,
            group=0,
            fcut=0.5,
            fres=0.5,
            slide=False,
        ),
        Note(
            pos=96,
            length=96,
            key=64,
            velocity=0.7,
            pan=0.5,
            release=0.5,
            color=0,
            group=2,
            fcut=0.6,
            fres=0.4,
            slide=True,
        ),
    ]
    script = generate_pyscript(
        notes,
        mode="replace_range",
        time_range=(0, 192),
        job_id="sbj-py39-val",
    )

    # 1. Native Python compile check
    compiled = compile(script, "<pyscript>", "exec")
    assert compiled is not None

    # 2. Ruff linter targeting Python 3.9
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(script)
        tmp_path = tmp.name

    try:
        res = subprocess.run(
            ["uv", "run", "ruff", "check", "--target-version", "py39", tmp_path],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, (
            f"Ruff check failed on generated pyscript: {res.stderr}\n{res.stdout}"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# req: PR-04
def test_empty_notes_replace_all_clears_score() -> None:
    """Verify replace_all mode with empty notes list cleanly clears score."""
    score = MockScore()
    n = MockNote()
    n.time = 0
    n.length = 96
    n.number = 60
    score.addNote(n)
    assert score.noteCount == 1

    script = generate_pyscript([], mode="replace_all", job_id="sbj-clear-score")
    execute_pyscript(script, score)

    assert score.noteCount == 0
    assert score.markerCount == 1
    assert score.getMarker(0).name == "JOB:sbj-clear-score:OK:0"


# req: PR-04
def test_all_11_note_parameters_roundtrip() -> None:
    """Verify all 11 note parameters accurately preserve values upon execution."""
    note = Note(
        pos=192,
        length=48,
        key=71,
        velocity=0.854321,
        pan=-0.654321,
        release=0.321456,
        color=7,
        group=4,
        fcut=0.712345,
        fres=0.298765,
        slide=True,
    )
    script = generate_pyscript([note], mode="replace_all", job_id="sbj-11params")
    score = MockScore()
    execute_pyscript(script, score)

    assert score.noteCount == 1
    applied = score.getNote(0)
    assert applied.time == 192
    assert applied.length == 48
    assert applied.number == 71
    assert applied.velocity == pytest.approx(0.854321, abs=1e-5)
    assert applied.pan == pytest.approx(-0.654321, abs=1e-5)
    assert applied.release == pytest.approx(0.321456, abs=1e-5)
    assert applied.color == 7
    assert applied.group == 4
    assert applied.fcut == pytest.approx(0.712345, abs=1e-5)
    assert applied.fres == pytest.approx(0.298765, abs=1e-5)
    assert applied.slide is True
