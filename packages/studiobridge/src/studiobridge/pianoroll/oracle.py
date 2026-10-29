"""Project oracle verification for piano-roll note application.

Project oracle verification for piano-roll note application [ACT-02]:
Verifies piano-roll note application by triggering project save-new-version
and comparing extracted notes against expected note definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from studiobridge.pianoroll.midi import read_midi_notes
from studiobridge.pianoroll.types import Note

# FPT_SaveNew command number from studiobridge.fl.consts
FPT_SAVE_NEW: int = 93


@dataclass(frozen=True, slots=True)
class OracleReport:
    """Result of oracle verification comparison per [ACT-02]."""

    verified: Literal["oracle", "none"]
    matched: bool
    expected_count: int
    actual_count: int
    matched_notes_count: int
    flp_path: Path | None = None
    mismatches: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class NoteOracleParser(ABC):
    """Abstract interface for parsing notes from project files."""

    @abstractmethod
    def parse_notes(
        self,
        flp_path: Path | str,
        *,
        pattern: int = 1,
        channel: int = 0,
    ) -> list[Note]:
        """Extract notes from project file for a specific pattern and channel."""
        ...


class MockNoteOracleParser(NoteOracleParser):
    """Mockable oracle parser for testing and offline environments."""

    def __init__(
        self,
        canned_notes: Sequence[Note] | None = None,
        pattern_channel_map: dict[tuple[int, int], list[Note]] | None = None,
    ) -> None:
        self.canned_notes: list[Note] = list(canned_notes) if canned_notes is not None else []
        self.pattern_channel_map: dict[tuple[int, int], list[Note]] = (
            dict(pattern_channel_map) if pattern_channel_map is not None else {}
        )

    def set_notes(
        self,
        pattern: int,
        channel: int,
        notes: Sequence[Note],
    ) -> None:
        """Register expected/actual notes for a specific (pattern, channel) pair."""
        self.pattern_channel_map[(pattern, channel)] = list(notes)

    def parse_notes(
        self,
        flp_path: Path | str,
        *,
        pattern: int = 1,
        channel: int = 0,
    ) -> list[Note]:
        """Return registered or canned notes, or parse from MIDI if path is .mid."""
        p = Path(flp_path)
        if p.suffix.lower() == ".mid" and p.exists():
            _, notes = read_midi_notes(p)
            return notes

        key = (pattern, channel)
        if key in self.pattern_channel_map:
            return list(self.pattern_channel_map[key])
        return list(self.canned_notes)


class OracleVerifier:
    """Note verification engine using project saves and oracle parsers."""

    def __init__(
        self,
        parser: NoteOracleParser | None = None,
        pitch_tolerance: int = 0,
        time_tolerance_ticks: int = 0,
        velocity_tolerance: float = 0.05,
    ) -> None:
        self.parser: NoteOracleParser = parser or MockNoteOracleParser()
        self.pitch_tolerance = pitch_tolerance
        self.time_tolerance_ticks = time_tolerance_ticks
        self.velocity_tolerance = velocity_tolerance

    async def trigger_save_new_version(self, session: Any) -> bool:
        """Trigger project save-new-version via live session."""
        if hasattr(session, "project") and hasattr(session.project, "save_new_version"):
            res = await session.project.save_new_version()
            return bool(getattr(res, "verified", True))
        elif hasattr(session, "call"):
            try:
                await session.call("project.saveNewVersion", {})
                return True
            except Exception:
                await session.call(
                    "transport.globalTransport",
                    {"command": FPT_SAVE_NEW, "value": 1},
                )
                return True
        return False

    def compare_notes(
        self,
        expected: Sequence[Note],
        actual: Sequence[Note],
    ) -> tuple[bool, list[str]]:
        """Compare expected and actual notes for pitch, position, length, and velocity."""
        mismatches: list[str] = []
        if len(expected) != len(actual):
            mismatches.append(f"Note count mismatch: expected {len(expected)}, found {len(actual)}")

        sorted_exp = sorted(expected, key=lambda n: (n.pos, n.key, n.length))
        sorted_act = sorted(actual, key=lambda n: (n.pos, n.key, n.length))

        for idx, (exp, act) in enumerate(zip(sorted_exp, sorted_act, strict=False)):
            if abs(exp.key - act.key) > self.pitch_tolerance:
                mismatches.append(
                    f"Note #{idx} pitch mismatch: expected key {exp.key}, got {act.key}"
                )
            if abs(exp.pos - act.pos) > self.time_tolerance_ticks:
                mismatches.append(
                    f"Note #{idx} position mismatch: expected pos {exp.pos}, got {act.pos}"
                )
            if abs(exp.length - act.length) > self.time_tolerance_ticks:
                mismatches.append(
                    f"Note #{idx} length mismatch: expected len {exp.length}, got {act.length}"
                )
            if abs(exp.velocity - act.velocity) > self.velocity_tolerance:
                mismatches.append(
                    f"Note #{idx} velocity mismatch: expected vel "
                    f"{exp.velocity:.3f}, got {act.velocity:.3f}"
                )

        matched = len(mismatches) == 0
        return matched, mismatches

    async def verify(
        self,
        expected_notes: Sequence[Note],
        *,
        session: Any | None = None,
        flp_path: Path | str | None = None,
        pattern: int = 1,
        channel: int = 0,
        trigger_save: bool = True,
    ) -> OracleReport:
        """Run oracle verification on applied notes."""
        if trigger_save and session is not None:
            await self.trigger_save_new_version(session)

        resolved_path = Path(flp_path) if flp_path else Path("project_save_new.flp")

        actual_notes = self.parser.parse_notes(
            resolved_path,
            pattern=pattern,
            channel=channel,
        )

        matched, mismatches = self.compare_notes(expected_notes, actual_notes)
        verified_level: Literal["oracle", "none"] = "oracle" if matched else "none"

        return OracleReport(
            verified=verified_level,
            matched=matched,
            expected_count=len(expected_notes),
            actual_count=len(actual_notes),
            matched_notes_count=min(len(expected_notes), len(actual_notes)) if matched else 0,
            flp_path=resolved_path if flp_path else None,
            mismatches=mismatches,
            details={
                "pitch_tolerance": self.pitch_tolerance,
                "time_tolerance_ticks": self.time_tolerance_ticks,
                "velocity_tolerance": self.velocity_tolerance,
            },
        )
