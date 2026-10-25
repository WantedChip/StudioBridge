"""Unit tests for SDK notes namespace (fl.notes).

Per spec 06_l0d_pianoroll_actuation_render.md §4, §6, §7 and 10_l2_interfaces.md §2.4.
# req: ACT-01, ACT-02
"""

from __future__ import annotations

from pathlib import Path

import anyio

from studiobridge import (
    AsyncStudio,
    Note,
    Studio,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.pianoroll.midi import read_midi_notes
from studiobridge.pianoroll.oracle import MockNoteOracleParser
from studiobridge.pianoroll.orchestrator import NoteApplyResult
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.notes import AsyncNotes, SyncNotes


def test_sync_notes_mounted_on_studio(studio: Studio) -> None:
    """Verify notes namespace is mounted on synchronous Studio client (# req: ACT-01)."""
    assert hasattr(studio, "notes")
    assert isinstance(studio.notes, SyncNotes)


def test_sync_notes_apply_step_grid(studio: Studio) -> None:
    """Verify fl.notes.apply_step_grid() sets 16-step grid (# req: ACT-01, ACT-02)."""
    fl = studio
    steps = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]

    res = fl.notes.apply_step_grid(channel=0, steps=steps)
    assert isinstance(res, NoteApplyResult)
    assert res.applied is True
    assert res.trigger == "step_grid"
    assert res.status == "applied"
    assert res.verified == "step_grid"
    assert res.notes_count == 8

    # Verify readback from channel rack
    grid_bits = fl.channels.get_step_grid(0)
    assert grid_bits == steps


def test_sync_notes_export_midi(studio: Studio, tmp_path: Path) -> None:
    """Verify fl.notes.export_midi() creates valid Standard MIDI file (.mid) (# req: ACT-01)."""
    fl = studio
    notes = [
        Note(pos=0, length=96, key=60),
        Note(pos=96, length=96, key=64),
        Note(pos=192, length=96, key=67),
    ]
    out_path = tmp_path / "sdk_notes.mid"
    written = fl.notes.export_midi(notes, path=out_path)
    assert written == out_path
    assert out_path.exists()

    ppq, read_back = read_midi_notes(out_path)
    assert ppq == 96
    assert len(read_back) == 3
    assert [n.key for n in read_back] == [60, 64, 67]


def test_sync_notes_apply_t3_pending(studio: Studio) -> None:
    """Verify fl.notes.apply() returns honest pending (T3) when unfocused (# req: ACT-02)."""
    fl = studio
    notes = [Note(pos=0, length=96, key=60)]

    res = fl.notes.apply(notes, dry_run=False)
    assert isinstance(res, NoteApplyResult)
    assert res.applied == "pending"
    assert res.trigger == "T3"
    assert res.status == "pending"
    assert res.verified == "none"
    assert len(res.instructions) >= 4


def test_sync_notes_verify_oracle(studio: Studio) -> None:
    """Verify fl.notes.verify_oracle() runs oracle verification report (# req: ACT-02)."""
    fl = studio
    notes = [Note(pos=0, length=96, key=60)]
    parser = MockNoteOracleParser(canned_notes=notes)

    rep = fl.notes.verify_oracle(notes, parser=parser)
    assert rep.matched is True
    assert rep.verified == "oracle"
    assert rep.expected_count == 1
    assert rep.actual_count == 1


def test_async_notes_interface(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    sdk_secret: str,
) -> None:
    """Verify AsyncStudio has AsyncNotes and executes async methods (# req: ACT-01, ACT-02)."""
    port_sdk, _ = running_emulator

    async def run() -> None:
        async with AsyncStudio.connect(
            embedded=True, port=port_sdk, secret=sdk_secret, mode="write"
        ) as fl:
            assert hasattr(fl, "notes")
            assert isinstance(fl.notes, AsyncNotes)

            # 1. Step grid
            steps = [1 if i % 2 == 0 else 0 for i in range(16)]
            res_grid = await fl.notes.apply_step_grid(channel=0, steps=steps)
            assert res_grid.applied is True
            assert res_grid.trigger == "step_grid"
            assert res_grid.notes_count == 8

            # 2. Step grid fallback via apply
            res_fallback = await fl.notes.apply(
                [Note(pos=0, length=24, key=36)],
                fallback="step_grid",
                channel=0,
            )
            assert res_fallback.applied is True
            assert res_fallback.trigger == "step_grid"

            # 3. Honest status T3
            res_t3 = await fl.notes.apply(
                [Note(pos=0, length=96, key=60)],
                dry_run=False,
            )
            assert res_t3.applied == "pending"
            assert res_t3.trigger == "T3"

    anyio.run(run)
