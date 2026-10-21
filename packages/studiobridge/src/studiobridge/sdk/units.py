"""Musical and engineering unit conversions per spec 09_l1_sdk.md §3.3.

Provides strongly-typed domain units and conversions:
- Volume: accepts raw 0.0..1.0, Db(float), or Percent(float)
- Db: Decibel representation
- Percent: Percentage representation
- Pan: normalized -1.0..1.0 with percentage and L-R helpers
- Tempo: BPM with beat/bar duration conversions
- Ticks, Beats, Bars: PPQ-aware musical time types
- Color: RGB, hex ("#RRGGBB"), and FL palette index representation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, NamedTuple, TypeVar

T = TypeVar("T")

DEFAULT_PPQ: int = 96
DEFAULT_BEATS_PER_BAR: int = 4

# FL Studio fader unity gain: 0 dB corresponds to 0.8 normalized raw fader position
UNITY_RAW_VOLUME: float = 0.8
MIN_DECIBELS: float = -100.0


@dataclass(frozen=True, slots=True)
class Db:
    """Decibel representation for audio gain (e.g. Db(-6.0), Db(0.0))."""

    value: float

    def __float__(self) -> float:
        return float(self.value)

    @classmethod
    def unity(cls) -> Db:
        """Create 0 dB unity gain representation."""
        return cls(0.0)

    @classmethod
    def mute(cls) -> Db:
        """Create mute representation (-100 dB)."""
        return cls(MIN_DECIBELS)

    def __repr__(self) -> str:
        return f"Db({self.value:.1f})"


@dataclass(frozen=True, slots=True)
class Percent:
    """Percentage representation (e.g. Percent(80.0) = 80%)."""

    value: float

    def __float__(self) -> float:
        return float(self.value)

    @classmethod
    def unity(cls) -> Percent:
        """Create 100% representation."""
        return cls(100.0)

    @classmethod
    def zero(cls) -> Percent:
        """Create 0% representation."""
        return cls(0.0)

    def __repr__(self) -> str:
        return f"Percent({self.value:.1f}%)"


class Volume:
    """Volume unit supporting raw 0.0..1.0, Db, and Percent conversions per 09 §3.3.

    Conversion curve adheres to FL Studio mixer fader behavior where:
    - 0.8 raw corresponds to 0.0 dB (unity gain)
    - 0.0 raw corresponds to -inf dB (clamped to -100 dB)
    - 1.0 raw corresponds to ~+1.94 dB (or fader maximum)
    """

    __slots__ = ("_raw",)

    def __init__(self, value: float | Db | Percent | Volume = UNITY_RAW_VOLUME) -> None:
        if isinstance(value, Db):
            self._raw = self._db_to_raw(value.value)
        elif isinstance(value, Percent):
            self._raw = self._percent_to_raw(value.value)
        elif isinstance(value, Volume):
            self._raw = value.raw
        else:
            self._raw = max(0.0, min(1.0, float(value)))

    @property
    def raw(self) -> float:
        """Normalized raw fader position between 0.0 and 1.0."""
        return self._raw

    def to_db(self) -> Db:
        """Convert normalized volume to decibels."""
        if self._raw <= 0.0:
            return Db(MIN_DECIBELS)
        db_val = 20.0 * math.log10(self._raw / UNITY_RAW_VOLUME)
        return Db(round(db_val, 2))

    def to_percent(self) -> Percent:
        """Convert normalized volume to percentage (0% to 100%)."""
        return Percent(round(self._raw * 100.0, 2))

    @classmethod
    def from_raw(cls, raw: float) -> Volume:
        """Instantiate Volume from normalized raw float (0.0 to 1.0)."""
        return cls(raw)

    @classmethod
    def unity(cls) -> Volume:
        """Create unity volume (0.8 raw, 0.0 dB)."""
        return cls(UNITY_RAW_VOLUME)

    @classmethod
    def mute(cls) -> Volume:
        """Create mute volume (0.0 raw, -100 dB)."""
        return cls(0.0)

    @classmethod
    def from_db(cls, db: float | Db) -> Volume:
        """Instantiate Volume from decibel value."""
        db_val = float(db)
        return cls(cls._db_to_raw(db_val))

    @classmethod
    def from_percent(cls, percent: float | Percent) -> Volume:
        """Instantiate Volume from percentage (0.0 to 100.0)."""
        pct_val = float(percent)
        return cls(cls._percent_to_raw(pct_val))

    @staticmethod
    def _db_to_raw(db: float) -> float:
        if db <= MIN_DECIBELS:
            return 0.0
        raw_val = UNITY_RAW_VOLUME * (10.0 ** (db / 20.0))
        return max(0.0, min(1.0, raw_val))

    @staticmethod
    def _percent_to_raw(pct: float) -> float:
        return max(0.0, min(1.0, pct / 100.0))

    def __float__(self) -> float:
        return self._raw

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Volume):
            return self._raw < other._raw
        if isinstance(other, (int, float)):
            return self._raw < float(other)
        return NotImplemented

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Volume):
            return math.isclose(self._raw, other._raw, abs_tol=1e-5)
        if isinstance(other, (int, float)):
            return math.isclose(self._raw, float(other), abs_tol=1e-5)
        if isinstance(other, Db):
            return math.isclose(self._raw, self._db_to_raw(other.value), abs_tol=1e-3)
        if isinstance(other, Percent):
            return math.isclose(self._raw, self._percent_to_raw(other.value), abs_tol=1e-3)
        return False

    def __repr__(self) -> str:
        return f"Volume({self._raw:.3f}, {self.to_db()!r}, {self.to_percent()!r})"


class Pan:
    """Stereo pan position normalized to -1.0 (Left) .. 1.0 (Right).

    Includes helpers for percentages (-100% to +100%) and L-R balance.
    """

    __slots__ = ("_value",)

    def __init__(self, value: float = 0.0) -> None:
        self._value = max(-1.0, min(1.0, float(value)))

    @property
    def value(self) -> float:
        """Pan position from -1.0 (full left) to 1.0 (full right)."""
        return self._value

    @property
    def raw(self) -> float:
        """Alias for value."""
        return self._value

    @property
    def is_center(self) -> bool:
        """Whether pan is centered (0.0)."""
        return math.isclose(self._value, 0.0, abs_tol=1e-4)

    @property
    def is_left(self) -> bool:
        """Whether pan is panned to the left (< 0.0)."""
        return self._value < -1e-4

    @property
    def is_right(self) -> bool:
        """Whether pan is panned to the right (> 0.0)."""
        return self._value > 1e-4

    @property
    def direction(self) -> str:
        """Directional string ('left', 'center', or 'right')."""
        if self.is_left:
            return "left"
        if self.is_right:
            return "right"
        return "center"

    @property
    def lr_percent(self) -> tuple[str, float]:
        """Return tuple of ('L'/'R'/'C', percentage) matching FL display."""
        if self.is_left:
            return ("L", abs(self.to_percent()))
        if self.is_right:
            return ("R", abs(self.to_percent()))
        return ("C", 0.0)

    def to_percent(self) -> float:
        """Convert pan to percentage from -100.0 (full left) to 100.0 (full right)."""
        return round(self._value * 100.0, 2)

    @classmethod
    def center(cls) -> Pan:
        """Create centered pan (0.0)."""
        return cls(0.0)

    @classmethod
    def left(cls, amount: float = 1.0) -> Pan:
        """Create left-panned value (e.g. amount=1.0 -> -1.0)."""
        return cls(-abs(amount))

    @classmethod
    def right(cls, amount: float = 1.0) -> Pan:
        """Create right-panned value (e.g. amount=1.0 -> 1.0)."""
        return cls(abs(amount))

    @classmethod
    def from_percent(cls, percent: float) -> Pan:
        """Instantiate Pan from percentage (-100.0 to 100.0)."""
        return cls(percent / 100.0)

    @classmethod
    def from_lr(cls, direction: str, amount: float = 1.0) -> Pan:
        """Instantiate Pan from direction ('left'/'l', 'right'/'r', 'center'/'c')."""
        d = direction.strip().lower()
        raw_amt = abs(float(amount))
        amt = raw_amt / 100.0 if raw_amt > 1.0 else raw_amt
        if d in {"l", "left"}:
            return cls(-amt)
        if d in {"r", "right"}:
            return cls(amt)
        if d in {"c", "center"}:
            return cls(0.0)
        raise ValueError(f"Invalid pan direction: {direction!r} (expected L, R, or C)")

    def __float__(self) -> float:
        return self._value

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Pan):
            return self._value < other._value
        if isinstance(other, (int, float)):
            return self._value < float(other)
        return NotImplemented

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Pan):
            return math.isclose(self._value, other._value, abs_tol=1e-5)
        if isinstance(other, (int, float)):
            return math.isclose(self._value, float(other), abs_tol=1e-5)
        return False

    def __repr__(self) -> str:
        return f"Pan({self._value:.2f}, {self.direction}, {self.to_percent():.0f}%)"


class Tempo:
    """Project tempo in beats per minute (BPM).

    Provides helpers for beat and bar duration calculations.
    """

    __slots__ = ("_bpm",)

    def __init__(self, bpm: float = 120.0) -> None:
        self._bpm = max(10.0, min(522.0, float(bpm)))

    @property
    def bpm(self) -> float:
        """Beats per minute."""
        return self._bpm

    def to_seconds_per_beat(self) -> float:
        """Duration of a single quarter-note beat in seconds."""
        return 60.0 / self._bpm

    def to_ms_per_beat(self) -> float:
        """Duration of a single quarter-note beat in milliseconds."""
        return (60.0 / self._bpm) * 1000.0

    def to_ms_per_bar(self, beats_per_bar: int = DEFAULT_BEATS_PER_BAR) -> float:
        """Duration of a musical measure/bar in milliseconds."""
        return self.to_ms_per_beat() * beats_per_bar

    def __float__(self) -> float:
        return self._bpm

    def __int__(self) -> int:
        return int(round(self._bpm))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Tempo):
            return self._bpm < other._bpm
        if isinstance(other, (int, float)):
            return self._bpm < float(other)
        return NotImplemented

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Tempo):
            return math.isclose(self._bpm, other._bpm, abs_tol=1e-3)
        if isinstance(other, (int, float)):
            return math.isclose(self._bpm, float(other), abs_tol=1e-3)
        return False

    def __repr__(self) -> str:
        return f"Tempo({self._bpm:.2f} BPM)"


# -----------------------------------------------------------------------------
# PPQ-Aware Musical Time: Ticks, Beats, Bars
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ticks:
    """PPQ pulses (ticks) musical time representation."""

    value: int

    def to_ticks(self, ppq: int = DEFAULT_PPQ) -> int:
        """Return raw tick count."""
        return self.value

    def to_beats(self, ppq: int = DEFAULT_PPQ) -> float:
        """Convert ticks to beats (quarter notes) at given PPQ."""
        if ppq <= 0:
            raise ValueError(f"PPQ must be positive, got {ppq}")
        return self.value / float(ppq)

    def to_bars(
        self,
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> float:
        """Convert ticks to bars at given PPQ and time signature."""
        if ppq <= 0 or beats_per_bar <= 0:
            raise ValueError("PPQ and beats_per_bar must be positive")
        return self.value / float(ppq * beats_per_bar)

    @classmethod
    def from_ticks(cls, ticks: int, ppq: int = DEFAULT_PPQ) -> Ticks:
        return cls(int(ticks))

    @classmethod
    def from_beats(cls, beats: float, ppq: int = DEFAULT_PPQ) -> Ticks:
        return cls(int(round(float(beats) * ppq)))

    @classmethod
    def from_bars(
        cls,
        bars: float,
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> Ticks:
        return cls(int(round(float(bars) * beats_per_bar * ppq)))

    def __int__(self) -> int:
        return self.value

    def __add__(self, other: Any) -> Ticks:
        if isinstance(other, Ticks):
            return Ticks(self.value + other.value)
        if isinstance(other, int):
            return Ticks(self.value + other)
        return NotImplemented

    def __sub__(self, other: Any) -> Ticks:
        if isinstance(other, Ticks):
            return Ticks(self.value - other.value)
        if isinstance(other, int):
            return Ticks(self.value - other)
        return NotImplemented

    def __mul__(self, other: Any) -> Ticks:
        if isinstance(other, int):
            return Ticks(self.value * other)
        return NotImplemented

    def __truediv__(self, other: Any) -> Ticks:
        if isinstance(other, (int, float)):
            return Ticks(int(round(self.value / other)))
        return NotImplemented


@dataclass(frozen=True, slots=True)
class Beats:
    """Musical beats (quarter notes) representation."""

    value: float

    def to_ticks(self, ppq: int = DEFAULT_PPQ) -> int:
        """Convert beats to ticks at given PPQ."""
        return int(round(self.value * ppq))

    def to_beats(self, ppq: int = DEFAULT_PPQ) -> float:
        """Return beat count."""
        return self.value

    def to_bars(
        self,
        ppq_or_beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
        beats_per_bar: int | None = None,
    ) -> float:
        """Convert beats to bars."""
        bpb = beats_per_bar if beats_per_bar is not None else ppq_or_beats_per_bar
        if bpb <= 0:
            raise ValueError(f"beats_per_bar must be positive, got {bpb}")
        return self.value / float(bpb)

    @classmethod
    def from_ticks(cls, ticks: int, ppq: int = DEFAULT_PPQ) -> Beats:
        if ppq <= 0:
            raise ValueError(f"PPQ must be positive, got {ppq}")
        return cls(ticks / float(ppq))

    @classmethod
    def from_beats(cls, beats: float, ppq: int = DEFAULT_PPQ) -> Beats:
        return cls(float(beats))

    @classmethod
    def from_bars(cls, bars: float, beats_per_bar: int = DEFAULT_BEATS_PER_BAR) -> Beats:
        return cls(float(bars) * beats_per_bar)

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class Bars:
    """Musical measures/bars representation."""

    value: float

    def to_ticks(
        self,
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> int:
        """Convert bars to ticks at given PPQ and time signature."""
        return int(round(self.value * beats_per_bar * ppq))

    def to_beats(self, beats_per_bar: int = DEFAULT_BEATS_PER_BAR) -> float:
        """Convert bars to beats."""
        return self.value * float(beats_per_bar)

    def to_bars(
        self,
        ppq_or_beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
        beats_per_bar: int | None = None,
    ) -> float:
        """Return bar count."""
        return self.value

    @classmethod
    def from_ticks(
        cls,
        ticks: int,
        ppq: int = DEFAULT_PPQ,
        beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
    ) -> Bars:
        if ppq <= 0 or beats_per_bar <= 0:
            raise ValueError("PPQ and beats_per_bar must be positive")
        return cls(ticks / float(ppq * beats_per_bar))

    @classmethod
    def from_beats(cls, beats: float, beats_per_bar: int = DEFAULT_BEATS_PER_BAR) -> Bars:
        if beats_per_bar <= 0:
            raise ValueError(f"beats_per_bar must be positive, got {beats_per_bar}")
        return cls(float(beats) / float(beats_per_bar))

    @classmethod
    def from_bars(cls, bars: float) -> Bars:
        return cls(float(bars))

    def __float__(self) -> float:
        return self.value


def to_ticks(
    val: int | float | Ticks | Beats | Bars,
    ppq: int = DEFAULT_PPQ,
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
) -> int:
    """Convert any musical time value to ticks."""
    if isinstance(val, Ticks):
        return val.value
    if isinstance(val, Beats):
        return val.to_ticks(ppq=ppq)
    if isinstance(val, Bars):
        return val.to_ticks(ppq=ppq, beats_per_bar=beats_per_bar)
    return int(val)


def from_ticks(
    ticks: int,
    unit: type[T],
    ppq: int = DEFAULT_PPQ,
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR,
) -> Any:
    """Convert raw ticks to specified unit type (Ticks, Beats, or Bars)."""
    if unit is Ticks:
        return Ticks(ticks)
    if unit is Beats:
        return Beats.from_ticks(ticks, ppq=ppq)
    if unit is Bars:
        return Bars.from_ticks(ticks, ppq=ppq, beats_per_bar=beats_per_bar)
    raise ValueError(f"Unsupported unit type: {unit}")


# -----------------------------------------------------------------------------
# Color, RGB, Hex & Palette Support
# -----------------------------------------------------------------------------


class RGB(NamedTuple):
    """24-bit RGB color components (0..255)."""

    r: int
    g: int
    b: int


# Standard FL Studio 16-color palette
FL_PALETTE: tuple[int, ...] = (
    0x505961,  # 0: Charcoal
    0xD34343,  # 1: Red
    0xDE7336,  # 2: Orange
    0xE29D36,  # 3: Amber
    0xDAC43E,  # 4: Yellow
    0x8CC63F,  # 5: Lime
    0x39B54A,  # 6: Green
    0x00A99D,  # 7: Teal
    0x00AEEF,  # 8: Cyan
    0x2E3192,  # 9: Blue
    0x662D91,  # 10: Purple
    0x92278F,  # 11: Magenta
    0xED145B,  # 12: Pink
    0x808080,  # 13: Medium Gray
    0x333333,  # 14: Dark Gray
    0xCCCCCC,  # 15: Light Gray
)


class Color:
    """Color supporting RGB(r, g, b), hex strings ('#RRGGBB'), and FL palette indices."""

    __slots__ = ("_r", "_g", "_b", "_palette_index")

    def __init__(
        self,
        value: int | str | tuple[int, int, int] | RGB | Color = 0,
    ) -> None:
        self._palette_index: int | None = None

        if isinstance(value, Color):
            self._r = value.r
            self._g = value.g
            self._b = value.b
            self._palette_index = value.palette_index
        elif isinstance(value, (RGB, tuple)) and len(value) == 3:
            self._r = max(0, min(255, int(value[0])))
            self._g = max(0, min(255, int(value[1])))
            self._b = max(0, min(255, int(value[2])))
        elif isinstance(value, str):
            r, g, b = self._parse_hex(value)
            self._r, self._g, self._b = r, g, b
        elif isinstance(value, int):
            self._r = (value >> 16) & 0xFF
            self._g = (value >> 8) & 0xFF
            self._b = value & 0xFF
            # Check if value matches palette index (0..15)
            if 0 <= value < len(FL_PALETTE):
                self._palette_index = value
        else:
            raise TypeError(f"Cannot initialize Color from {type(value).__name__}: {value!r}")

    @property
    def r(self) -> int:
        return self._r

    @property
    def g(self) -> int:
        return self._g

    @property
    def b(self) -> int:
        return self._b

    @property
    def rgb(self) -> RGB:
        return RGB(self._r, self._g, self._b)

    @property
    def hex(self) -> str:
        return f"#{self._r:02X}{self._g:02X}{self._b:02X}"

    def to_hex(self) -> str:
        """Return hex representation (e.g. '#FF0000')."""
        return self.hex

    @property
    def palette_index(self) -> int | None:
        return self._palette_index

    def to_fl_int(self) -> int:
        """Convert to packed 24-bit RGB integer (0xRRGGBB)."""
        return (self._r << 16) | (self._g << 8) | self._b

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> Color:
        return cls(RGB(r, g, b))

    @classmethod
    def from_hex(cls, hex_str: str) -> Color:
        return cls(hex_str)

    @classmethod
    def from_palette(cls, index: int) -> Color:
        """Instantiate Color from FL standard palette index (0..15)."""
        idx = int(index)
        if not (0 <= idx < len(FL_PALETTE)):
            raise ValueError(
                f"FL palette index must be between 0 and {len(FL_PALETTE) - 1}, got {index}"
            )
        c = cls(FL_PALETTE[idx])
        c._palette_index = idx
        return c

    @classmethod
    def from_fl_palette(cls, index: int) -> Color:
        """Alias for from_palette."""
        return cls.from_palette(index)

    @classmethod
    def from_fl_int(cls, val: int) -> Color:
        return cls(val)

    @staticmethod
    def _parse_hex(s: str) -> tuple[int, int, int]:
        clean = s.strip().lstrip("#")
        if len(clean) == 3:
            r = int(clean[0] * 2, 16)
            g = int(clean[1] * 2, 16)
            b = int(clean[2] * 2, 16)
            return r, g, b
        if len(clean) == 6:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
            return r, g, b
        raise ValueError(f"Invalid hex color string: {s!r}")

    def __int__(self) -> int:
        return self.to_fl_int()

    def __str__(self) -> str:
        return self.hex

    def __repr__(self) -> str:
        return f"Color({self.hex}, RGB({self._r}, {self._g}, {self._b}))"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Color):
            return self.to_fl_int() == other.to_fl_int()
        if isinstance(other, int):
            return self.to_fl_int() == other
        if isinstance(other, str):
            try:
                return self.hex.upper() == Color(other).hex.upper()
            except ValueError:
                return False
        if isinstance(other, (tuple, RGB)):
            return self.rgb == other
        return False


__all__ = [
    "Bars",
    "Beats",
    "Color",
    "DEFAULT_BEATS_PER_BAR",
    "DEFAULT_PPQ",
    "Db",
    "FL_PALETTE",
    "Pan",
    "Percent",
    "RGB",
    "Tempo",
    "Ticks",
    "Volume",
    "from_ticks",
    "to_ticks",
]
