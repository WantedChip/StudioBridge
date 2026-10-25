"""Unit tests for CLI render and notes commands per spec 10_l2_interfaces.md §3.

Verifies:
1. 'sbridge notes apply <file> [--target channel:X,pattern:Y] [--mode append|replace] [--json]'
   (# req: ACT-01, ACT-02).
2. 'sbridge notes from-midi <file> [--json]'.
3. 'sbridge render <project.flp> [--format wav|mp3|flac] [--watch] [--json]' (# req: RND-01).
4. 'sbridge render status <job_id> [--json]'.
5. 'sbridge render cancel <job_id> [--json]'.
6. 'sbridge render analyze <file.wav> [--json]' (# req: RND-05).
7. Path containment security enforcement across CLI commands (# req: MCP §2.8).
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from studiobridge.cli.commands.render import set_default_runner
from studiobridge.cli.main import ExitCode, cli_entry
from studiobridge.core.paths import get_jobs_dir
from studiobridge.pianoroll.midi import write_midi_file
from studiobridge.pianoroll.types import Note
from studiobridge.render.job import JobState, RenderJob
from studiobridge.render.runner import RenderRunner


def _create_synthetic_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 44100) -> Path:
    """Generate a clean synthetic PCM 16-bit WAV file for testing."""
    n_samples = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(16384 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return path


class MockCliRenderRunner(RenderRunner):
    """Mock runner simulating headless export for CLI test environments."""

    def __init__(self, output_wav: Path | None = None) -> None:
        self.output_wav = output_wav

    def run(self, job: RenderJob) -> RenderJob:
        job.state = JobState.RENDERING
        out_dir = job.out_dir or (get_jobs_dir() / job.job_id / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        job.out_dir = out_dir

        if self.output_wav and self.output_wav.exists():
            dest = out_dir / f"{job.source.stem}.wav"
            dest.write_bytes(self.output_wav.read_bytes())
            job.output_files = [dest]

        job.state = JobState.DONE
        job.metrics = {
            "duration_s": 1.0,
            "peak_dbfs": -6.0,
            "rms_dbfs": -9.0,
            "silence_ratio": 0.0,
        }
        return job


def test_cli_notes_apply(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify 'sbridge notes apply' parses arguments and emits structured JSON (# req: ACT-01)."""
    notes_file = tmp_path / "notes.json"
    note_data = [
        {"pos": 0, "length": 96, "key": 60, "velocity": 0.8},
        {"pos": 96, "length": 96, "key": 64, "velocity": 0.8},
    ]
    notes_file.write_text(json.dumps(note_data), encoding="utf-8")

    code = cli_entry(
        [
            "notes",
            "apply",
            str(notes_file),
            "--target",
            "channel:1,pattern:2",
            "--mode",
            "replace",
            "--dry-run",
            "--json",
        ]
    )

    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] in ("applied", "pending")
    assert data["notes_count"] == 2
    assert data["channel"] == 1
    assert data["pattern"] == 2


def test_cli_notes_from_midi(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify 'sbridge notes from-midi' decodes standard MIDI file to JSON (# req: ACT-01)."""
    midi_file = tmp_path / "melody.mid"
    write_midi_file(
        [Note(pos=0, length=96, key=62), Note(pos=96, length=96, key=65)], midi_file, ppq=96
    )

    code = cli_entry(["notes", "from-midi", str(midi_file), "--json"])
    assert code == ExitCode.OK

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 2
    assert data["ppq"] == 96
    assert len(data["notes"]) == 2


def test_cli_render_start_and_watch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify 'sbridge render' launches and watches job to completion (# req: RND-01, MCP-20)."""
    flp_file = tmp_path / "track.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    synth_wav = _create_synthetic_wav(tmp_path / "ref.wav")
    runner = MockCliRenderRunner(output_wav=synth_wav)
    set_default_runner(runner)

    code = cli_entry(
        [
            "render",
            str(flp_file),
            "--format",
            "wav",
            "--watch",
            "--json",
        ]
    )

    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["state"] == "done"
    assert len(data["output_files"]) == 1
    assert data["job_id"].startswith("rnd-")


def test_cli_render_status_and_cancel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify 'sbridge render status' and 'sbridge render cancel' (# req: RND-03)."""
    flp_file = tmp_path / "project.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    runner = MockCliRenderRunner(output_wav=_create_synthetic_wav(tmp_path / "out.wav"))
    set_default_runner(runner)

    # Start render
    cli_entry(["render", str(flp_file), "--json"])
    start_data = json.loads(capsys.readouterr().out)
    job_id = start_data["job_id"]

    # Poll status
    code_stat = cli_entry(["render", "status", job_id, "--json"])
    assert code_stat == ExitCode.OK
    stat_data = json.loads(capsys.readouterr().out)
    assert stat_data["job_id"] == job_id

    # Cancel job
    code_canc = cli_entry(["render", "cancel", job_id, "--json"])
    assert code_canc == ExitCode.OK
    canc_data = json.loads(capsys.readouterr().out)
    assert canc_data["status"] == "cancelled"


def test_cli_render_analyze(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify 'sbridge render analyze' validates audio file metrics (# req: RND-05)."""
    wav_file = _create_synthetic_wav(tmp_path / "master.wav", duration_s=1.2)

    code = cli_entry(["render", "analyze", str(wav_file), "--json"])
    assert code == ExitCode.OK

    data = json.loads(capsys.readouterr().out)
    assert data["is_valid"] is True
    assert data["validation_status"] == "passed"
    assert "metrics" in data
    assert data["metrics"]["duration_s"] >= 1.0


def test_cli_path_traversal_rejection(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify CLI commands enforce path containment security (# req: MCP §2.8)."""
    code_notes = cli_entry(["notes", "apply", "../forbidden.json", "--json"])
    assert code_notes != ExitCode.OK

    code_midi = cli_entry(
        ["notes", "from-midi", "\\\\unauthorized-server\\share\\evil.mid", "--json"]
    )
    assert code_midi != ExitCode.OK

    code_render = cli_entry(["render", "../outside.flp", "--json"])
    assert code_render != ExitCode.OK
