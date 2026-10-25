"""Types, note representations, and musical unit conversions for piano-roll scripts.

Per spec 06_l0d_pianoroll_actuation_render.md §1–§3 and [PR-01]..[PR-06].
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

DEFAULT_PPQ: Final[int] = 96
DEFAULT_BEATS_PER_BAR: Final[int] = 4
MAX_PAYLOAD_BYTES: Final[int] = 200 * 1024  # 204,800 bytes per [PR-02]

ApplyMode = Literal["append", "replace_all", "replace_range"]
VALID_APPLY_MODES: Final[frozenset[str]] = frozenset({"append", "replace_all", "replace_range"})

NOTE_NAMES: Final[tuple[str, ...]] = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)

# Common musical subdivision ratios in beats (quarter notes)
SUBDIVISION_BEAT_RATIOS: Final[dict[str, float]] = {
    "1/1": 4.0,  # whole note (in 4/4)
    "whole": 4.0,
    "bar": 4.0,
    "1/2": 2.0,  # half note
    "half": 2.0,
    "1/4": 1.0,  # quarter note (1 beat)
    "quarter": 1.0,
    "beat": 1.0,
    "1/8": 0.5,  # eighth note
    "eighth": 0.5,
    "1/16": 0.25,  # sixteenth note (1 step)
    "sixteenth": 0.25,
    "step": 0.25,
    "1/32": 0.125,  # thirty-second note
    "1/64": 0.0625,  # sixty-fourth note
    # Triplets
    "1/2t": 4.0 / 3.0,
    "1/4t": 2.0 / 3.0,
    "1/8t": 1.0 / 3.0,
    "1/16t": 0.5 / 3.0,
    "1/32t": 0.25 / 3.0,
    # Dotted
    "1/1d": 6.0,
    "1/2d": 3.0,
    "1/4d": 1.5,
    "1/8d": 0.75,
    "1/16d": 0.375,
    "1/32d": 0.1875,
}


def note_name_to_midi(name: str) -> int:
    """Convert note name (e.g. 'C5', 'A#4', 'Db3') to MIDI key number (0..127).

    FL Studio piano roll standard: Middle C (MIDI 60) is C5.
    """
    s = name.strip()
    if not s:
        raise ValueError("Note name cannot be empty")

    letter = s[0].upper()
    if letter not in ("C", "D", "E", "F", "G", "A", "B"):
        raise ValueError(f"Invalid note letter: {letter!r} in {name!r}")

    idx = 1
    accidental = 0
    if idx < len(s) and s[idx] in ("#", "b", "B"):
        accidental = 1 if s[idx] == "#" else -1
        idx += 1

    octave_str = s[idx:]
    if not octave_str:
        raise ValueError(f"Missing octave in note name: {name!r}")
    try:
        octave = int(octave_str)
    except ValueError as e:
        raise ValueError(f"Invalid octave {octave_str!r} in note name: {name!r}") from e

    base_semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    midi_num = (octave * 12) + base_semitones[letter] + accidental
    if not (0 <= midi_num <= 127):
        raise ValueError(f"Note name {name!r} resolves to out-of-range MIDI number {midi_num}")

    return midi_num


def midi_to_note_name(note: int) -> str:
    """Convert MIDI key number (0..127) to note name (e.g. 60 -> 'C5')."""
    if not (0 <= note <= 127):
        raise ValueError(f"MIDI note must be 0..127, got {note}")
    octave = note // 12
    semitone = note % 12
    return f"{NOTE_NAMES[semitone]}{octave}"


def subdivision_to_ticks(
    subdivision: Any,
    ppq: int = DEFAULT_PPQ,
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
) -> int:
    """Convert musical subdivision or value to ticks at given PPQ ([PR-05])."""
    if ppq <= 0:
        raise ValueError(f"PPQ must be positive, got {ppq}")

    if isinstance(subdivision, int):
        return subdivision

    if isinstance(subdivision, float):
        return int(round(subdivision))

    # Duck-typing support for PPQ-aware unit types (Ticks, Beats, Bars)
    to_ticks_fn = getattr(subdivision, "to_ticks", None)
    if callable(to_ticks_fn):
        res = to_ticks_fn(ppq=ppq)
        if isinstance(res, (int, float)):
            return int(round(res))

    sub = str(subdivision).strip().lower()
    if sub in SUBDIVISION_BEAT_RATIOS:
        ratio = SUBDIVISION_BEAT_RATIOS[sub]
        return int(round(ratio * ppq))

    # Parse fraction 'num/den' (fraction of a 4/4 bar)
    if "/" in sub:
        parts = sub.split("/")
        if len(parts) == 2:
            try:
                num = float(parts[0])
                den = float(parts[1])
                if den != 0.0:
                    beats = (num / den) * float(beats_per_bar)
                    return int(round(beats * ppq))
            except ValueError:
                pass

    try:
        return int(round(float(sub)))
    except ValueError as e:
        raise ValueError(f"Unrecognized musical subdivision: {subdivision!r}") from e


def ticks_to_subdivision(ticks: int, ppq: int = DEFAULT_PPQ) -> str:
    """Convert tick count to nearest standard subdivision name if exact."""
    if ppq <= 0:
        raise ValueError(f"PPQ must be positive, got {ppq}")

    # Check exact matches against SUBDIVISION_BEAT_RATIOS
    for name, ratio in SUBDIVISION_BEAT_RATIOS.items():
        if "/" in name and not name.endswith(("t", "d")) and int(round(ratio * ppq)) == ticks:
            return name

    # Fallback to beat or tick string
    beats = ticks / float(ppq)
    return f"{beats:.3f} beats"


def normalize_velocity(v: Any) -> float:
    """Normalize velocity to float 0.0..1.0.

    - External MIDI values (0..127) are scaled by 1/127.
    - Floats (0.0..1.0) are clamped and preserved.
    """
    raw_attr = getattr(v, "raw", None)
    if raw_attr is not None:
        v = raw_attr
    else:
        val_attr = getattr(v, "value", None)
        if val_attr is not None:
            v = val_attr

    if isinstance(v, int):
        clamped = max(0, min(127, v))
        return round(clamped / 127.0, 6)

    val = float(v)
    if val > 1.0:
        return round(max(0.0, min(1.0, val / 127.0)), 6)
    return round(max(0.0, min(1.0, val)), 6)


def normalize_pan(p: Any) -> float:
    """Normalize pan to float -1.0..1.0.

    - External MIDI values (0..127, center 64) scaled to -1.0..1.0.
    - Floats (-1.0..1.0) clamped and preserved.
    """
    val_attr = getattr(p, "value", None)
    if val_attr is not None:
        p = val_attr
    else:
        raw_attr = getattr(p, "raw", None)
        if raw_attr is not None:
            p = raw_attr

    if isinstance(p, int) and not isinstance(p, bool):
        if p == 64:
            return 0.0
        if p < 64:
            return round((p - 64) / 64.0, 6)
        return round((p - 64) / 63.0, 6)

    return round(max(-1.0, min(1.0, float(p))), 6)


def normalize_release(r: Any) -> float:
    """Normalize note release velocity to float 0.0..1.0 (default 0.5 neutral)."""
    val_attr = getattr(r, "value", None)
    if val_attr is not None:
        r = val_attr

    if isinstance(r, int):
        clamped = max(0, min(127, r))
        return round(clamped / 127.0, 6)

    val = float(r)
    if val > 1.0:
        return round(max(0.0, min(1.0, val / 127.0)), 6)
    return round(max(0.0, min(1.0, val)), 6)


def normalize_filter(f: Any) -> float:
    """Normalize filter cutoff or resonance to float 0.0..1.0 (default 0.5 neutral)."""
    val_attr = getattr(f, "value", None)
    if val_attr is not None:
        f = val_attr

    if isinstance(f, int):
        clamped = max(0, min(127, f))
        return round(clamped / 127.0, 6)

    val = float(f)
    if val > 1.0:
        return round(max(0.0, min(1.0, val / 127.0)), 6)
    return round(max(0.0, min(1.0, val)), 6)


def normalize_color(c: Any) -> int:
    """Normalize FL Studio note color group / channel to integer 0..15."""
    pal_idx = getattr(c, "palette_index", None)
    if pal_idx is not None:
        c = pal_idx
    else:
        val_attr = getattr(c, "value", None)
        if val_attr is not None:
            c = val_attr
    return max(0, min(15, int(c)))


@dataclass(frozen=True, slots=True)
class Note:
    """Complete 11-parameter piano roll note per spec 06_l0d §3.

    Fields:
    1. pos: start position in project PPQ ticks
    2. length: note duration in project PPQ ticks
    3. key: MIDI note number (0..127)
    4. velocity: normalized velocity (0.0..1.0)
    5. pan: normalized pan (-1.0..1.0)
    6. release: normalized release velocity (0.0..1.0)
    7. color: note color group / MIDI channel (0..15)
    8. group: note grouping ID (int >= 0)
    9. fcut: normalized filter cutoff offset (0.0..1.0, 0.5 = neutral)
    10. fres: normalized filter resonance offset (0.0..1.0, 0.5 = neutral)
    11. slide: pitch slide flag (bool)
    """

    pos: int
    length: int
    key: int
    velocity: float = 0.787402  # ~100 / 127
    pan: float = 0.0
    release: float = 0.5
    color: int = 0
    group: int = 0
    fcut: float = 0.5
    fres: float = 0.5
    slide: bool = False

    def __post_init__(self) -> None:
        if self.pos < 0:
            raise ValueError(f"Note pos must be non-negative, got {self.pos}")
        if self.length <= 0:
            raise ValueError(f"Note length must be positive, got {self.length}")
        if not (0 <= self.key <= 127):
            raise ValueError(f"Note key must be in 0..127, got {self.key}")
        if not (0.0 <= self.velocity <= 1.0):
            raise ValueError(f"Note velocity must be in 0.0..1.0, got {self.velocity}")
        if not (-1.0 <= self.pan <= 1.0):
            raise ValueError(f"Note pan must be in -1.0..1.0, got {self.pan}")
        if not (0.0 <= self.release <= 1.0):
            raise ValueError(f"Note release must be in 0.0..1.0, got {self.release}")
        if not (0 <= self.color <= 15):
            raise ValueError(f"Note color must be in 0..15, got {self.color}")
        if self.group < 0:
            raise ValueError(f"Note group must be >= 0, got {self.group}")
        if not (0.0 <= self.fcut <= 1.0):
            raise ValueError(f"Note fcut must be in 0.0..1.0, got {self.fcut}")
        if not (0.0 <= self.fres <= 1.0):
            raise ValueError(f"Note fres must be in 0.0..1.0, got {self.fres}")

    @property
    def pos_ticks(self) -> int:
        return self.pos

    @property
    def len_ticks(self) -> int:
        return self.length

    @property
    def midi_note(self) -> int:
        return self.key

    @property
    def note(self) -> int:
        return self.key

    @property
    def vel(self) -> float:
        return self.velocity

    @property
    def rel(self) -> float:
        return self.release

    @property
    def pitch_name(self) -> str:
        return midi_to_note_name(self.key)

    def to_tuple(self) -> tuple[int, int, int, float, float, float, int, int, float, float, bool]:
        """Serialize note as canonical 11-parameter tuple per 06_l0d §3."""
        return (
            self.pos,
            self.length,
            self.key,
            round(self.velocity, 6),
            round(self.pan, 6),
            round(self.release, 6),
            self.color,
            self.group,
            round(self.fcut, 6),
            round(self.fres, 6),
            self.slide,
        )

    @classmethod
    def from_tuple(cls, t: Sequence[Any]) -> Note:
        """Construct Note from a 3- to 11-element tuple."""
        if len(t) < 3:
            raise ValueError(
                f"Note tuple requires at least 3 elements (pos, len, key), got {len(t)}"
            )

        pos = int(t[0])
        length = int(t[1])
        key = int(t[2])
        vel = normalize_velocity(t[3]) if len(t) > 3 else 0.787402
        pan = normalize_pan(t[4]) if len(t) > 4 else 0.0
        rel = normalize_release(t[5]) if len(t) > 5 else 0.5
        col = normalize_color(t[6]) if len(t) > 6 else 0
        grp = max(0, int(t[7])) if len(t) > 7 else 0
        fcut = normalize_filter(t[8]) if len(t) > 8 else 0.5
        fres = normalize_filter(t[9]) if len(t) > 9 else 0.5
        slide = bool(t[10]) if len(t) > 10 else False

        return cls(
            pos=pos,
            length=length,
            key=key,
            velocity=vel,
            pan=pan,
            release=rel,
            color=col,
            group=grp,
            fcut=fcut,
            fres=fres,
            slide=slide,
        )

    @classmethod
    def from_midi(
        cls,
        pos: int | str | Any,
        length: int | str | Any,
        key: int | str,
        velocity: int | float | Any = 100,
        pan: int | float | Any = 64,
        release: int | float | Any = 64,
        color: int | Any = 0,
        group: int = 0,
        fcut: int | float | Any = 64,
        fres: int | float | Any = 64,
        slide: bool = False,
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> Note:
        """Construct Note with automatic external MIDI scaling and musical subdivision parsing."""
        pos_ticks = subdivision_to_ticks(pos, ppq=ppq, beats_per_bar=beats_per_bar)
        len_ticks = subdivision_to_ticks(length, ppq=ppq, beats_per_bar=beats_per_bar)
        if len_ticks <= 0:
            raise ValueError(f"Note length in ticks must be positive, got {len_ticks}")

        midi_key = note_name_to_midi(key) if isinstance(key, str) else int(key)

        return cls(
            pos=pos_ticks,
            length=len_ticks,
            key=midi_key,
            velocity=normalize_velocity(velocity),
            pan=normalize_pan(pan),
            release=normalize_release(release),
            color=normalize_color(color),
            group=max(0, int(group)),
            fcut=normalize_filter(fcut),
            fres=normalize_filter(fres),
            slide=bool(slide),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize note as dictionary."""
        return {
            "pos": self.pos,
            "length": self.length,
            "key": self.key,
            "pitch_name": self.pitch_name,
            "velocity": round(self.velocity, 6),
            "pan": round(self.pan, 6),
            "release": round(self.release, 6),
            "color": self.color,
            "group": self.group,
            "fcut": round(self.fcut, 6),
            "fres": round(self.fres, 6),
            "slide": self.slide,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> Note:
        """Construct Note from dictionary mapping."""
        pos_raw = data.get("pos", data.get("pos_ticks", 0))
        len_raw = data.get("length", data.get("len_ticks", ppq))
        key_raw = data.get("key", data.get("midi_note", data.get("note", 60)))
        vel_raw = data.get("velocity", data.get("vel", 100))
        pan_raw = data.get("pan", 64)
        rel_raw = data.get("release", data.get("rel", 64))
        col_raw = data.get("color", 0)
        grp_raw = data.get("group", 0)
        fcut_raw = data.get("fcut", 64)
        fres_raw = data.get("fres", 64)
        slide_raw = data.get("slide", False)

        return cls.from_midi(
            pos=pos_raw,
            length=len_raw,
            key=key_raw,
            velocity=vel_raw,
            pan=pan_raw,
            release=rel_raw,
            color=col_raw,
            group=grp_raw,
            fcut=fcut_raw,
            fres=fres_raw,
            slide=slide_raw,
            ppq=ppq,
            beats_per_bar=beats_per_bar,
        )


@dataclass(frozen=True, slots=True)
class PyscriptJob:
    """Represents a single generated .pyscript job payload."""

    job_id: str
    script_content: str
    mode: str
    notes: tuple[Note, ...]
    part_index: int = 1
    total_parts: int = 1
    time_range: tuple[int, int] | None = None
    byte_size: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "byte_size", len(self.script_content.encode("utf-8")))

    @property
    def note_count(self) -> int:
        """Number of notes baked into this script."""
        return len(self.notes)

    @property
    def is_chunked(self) -> bool:
        """Whether this job is part of a multi-job chunked batch."""
        return self.total_parts > 1
