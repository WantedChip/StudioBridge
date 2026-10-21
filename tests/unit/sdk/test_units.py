"""Unit tests for musical and engineering units per 09_l1_sdk.md §3.3.

Tests strongly-typed domain units:
- Db and Percent representations
- Volume normalized fader scaling, decibel / percentage conversions, and clamping
- Pan normalized -1.0..1.0, direction indicators, and L-R percentage helpers
- Tempo BPM, ms/sec per beat, and ms per bar conversions
- Ticks, Beats, Bars PPQ-aware time structures, arithmetic, and converters
- Color representations (RGB, hex "#RRGGBB", FL palette indices) and FL integer encoding
"""

from __future__ import annotations

import pytest

from studiobridge import (
    FL_PALETTE,
    RGB,
    Bars,
    Beats,
    Color,
    Db,
    Pan,
    Percent,
    Tempo,
    Ticks,
    Volume,
    from_ticks,
    to_ticks,
)


def test_db_representation() -> None:
    """Verify Db dataclass, float conversion, and unity / mute factories."""
    d0 = Db(0.0)
    assert float(d0) == 0.0
    assert repr(d0) == "Db(0.0)"

    d_neg = Db(-6.02)
    assert float(d_neg) == -6.02
    assert repr(d_neg) == "Db(-6.0)"

    assert Db.unity() == Db(0.0)
    assert Db.mute() == Db(-100.0)


def test_percent_representation() -> None:
    """Verify Percent dataclass, float conversion, and unity / zero factories."""
    p100 = Percent(100.0)
    assert float(p100) == 100.0
    assert repr(p100) == "Percent(100.0%)"

    p50 = Percent(50.0)
    assert float(p50) == 50.0

    assert Percent.unity() == Percent(100.0)
    assert Percent.zero() == Percent(0.0)


def test_volume_conversions() -> None:
    """Verify Volume normalized fader position, dB, and percent conversions."""
    # Unity gain (0.8 raw = 0 dB)
    v_unity = Volume.unity()
    assert v_unity.raw == 0.8
    assert float(v_unity) == 0.8
    assert abs(v_unity.to_db().value - 0.0) < 0.001
    assert abs(v_unity.to_percent().value - 80.0) < 0.001

    # Mute (0.0 raw = -100 dB)
    v_mute = Volume.mute()
    assert v_mute.raw == 0.0
    assert v_mute.to_db().value == -100.0
    assert v_mute.to_percent().value == 0.0

    # Max (1.0 raw = 100%)
    v_max = Volume(1.0)
    assert v_max.raw == 1.0
    assert v_max.to_percent().value == 100.0
    assert v_max.to_db().value > 0.0  # Approx +1.94 dB

    # From Db
    v_from_db0 = Volume.from_db(0.0)
    assert abs(v_from_db0.raw - 0.8) < 0.001

    v_from_db_neg6 = Volume.from_db(-6.0206)
    assert abs(v_from_db_neg6.raw - 0.4) < 0.002

    v_from_db_mute = Volume.from_db(-100.0)
    assert v_from_db_mute.raw == 0.0

    # From Percent
    v_from_pct = Volume.from_percent(50.0)
    assert abs(v_from_pct.raw - 0.5) < 0.001

    # Constructor flexibility
    assert Volume(Db(0.0)).raw == 0.8
    assert Volume(Percent(80.0)).raw == 0.8
    assert Volume(v_unity).raw == 0.8

    # Clamping
    assert Volume(-0.5).raw == 0.0
    assert Volume(1.5).raw == 1.0

    # Equality and comparison
    assert Volume(0.8) == Volume(0.8)
    assert Volume(0.5) < Volume(0.8)


def test_pan_units_and_helpers() -> None:
    """Verify Pan normalized positions, percentages, and direction indicators."""
    center = Pan.center()
    assert center.raw == 0.0
    assert center.direction == "center"
    assert center.to_percent() == 0.0
    assert float(center) == 0.0

    left = Pan.left()
    assert left.raw == -1.0
    assert left.direction == "left"
    assert left.to_percent() == -100.0
    assert left.lr_percent == ("L", 100.0)

    right = Pan.right()
    assert right.raw == 1.0
    assert right.direction == "right"
    assert right.to_percent() == 100.0
    assert right.lr_percent == ("R", 100.0)

    # From Percent
    assert Pan.from_percent(-50.0).raw == -0.5
    assert Pan.from_percent(50.0).raw == 0.5

    # From L-R
    assert Pan.from_lr("L", 50.0).raw == -0.5
    assert Pan.from_lr("R", 25.0).raw == 0.25
    assert Pan.from_lr("C").raw == 0.0

    with pytest.raises(ValueError):
        Pan.from_lr("X", 50.0)

    # Clamping
    assert Pan(-2.0).raw == -1.0
    assert Pan(2.0).raw == 1.0

    # Equality and comparison
    assert Pan(0.0) == Pan.center()
    assert Pan(-0.5) < Pan(0.5)


def test_tempo_unit() -> None:
    """Verify Tempo BPM scaling, durations, and bounds clamping."""
    t120 = Tempo(120.0)
    assert t120.bpm == 120.0
    assert float(t120) == 120.0
    assert int(t120) == 120
    assert repr(t120) == "Tempo(120.00 BPM)"

    # Duration per beat: 60 / 120 = 0.5 s = 500 ms
    assert t120.to_seconds_per_beat() == 0.5
    assert t120.to_ms_per_beat() == 500.0

    # Duration per 4-beat bar: 4 * 500 = 2000 ms
    assert t120.to_ms_per_bar(beats_per_bar=4) == 2000.0
    assert t120.to_ms_per_bar(beats_per_bar=3) == 1500.0

    # Clamping to [10.0, 522.0]
    assert Tempo(5.0).bpm == 10.0
    assert Tempo(600.0).bpm == 522.0

    # Comparison
    assert Tempo(120.0) == Tempo(120.0)
    assert Tempo(100.0) < Tempo(140.0)


def test_musical_time_ticks_beats_bars() -> None:
    """Verify Ticks, Beats, and Bars PPQ-aware conversions and arithmetic."""
    ppq = 96
    beats_per_bar = 4

    # Ticks
    t96 = Ticks(96)
    assert int(t96) == 96
    assert t96.to_ticks(ppq) == 96
    assert t96.to_beats(ppq) == 1.0
    assert t96.to_bars(ppq, beats_per_bar) == 0.25

    # Beats
    b4 = Beats(4.0)
    assert float(b4) == 4.0
    assert b4.to_ticks(ppq) == 4 * 96
    assert b4.to_beats(ppq) == 4.0
    assert b4.to_bars(ppq, beats_per_bar) == 1.0

    # Bars
    bar2 = Bars(2.0)
    assert float(bar2) == 2.0
    assert bar2.to_bars() == 2.0
    assert bar2.to_beats(beats_per_bar) == 8.0
    assert bar2.to_ticks(ppq, beats_per_bar) == 2 * 4 * 96

    # Top-level converters
    assert to_ticks(Bars(1.0), ppq=ppq, beats_per_bar=beats_per_bar) == 384
    assert to_ticks(Beats(2.0), ppq=ppq) == 192
    assert to_ticks(Ticks(96), ppq=ppq) == 96

    assert from_ticks(384, Bars, ppq=ppq, beats_per_bar=beats_per_bar) == Bars(1.0)
    assert from_ticks(192, Beats, ppq=ppq) == Beats(2.0)
    assert from_ticks(96, Ticks, ppq=ppq) == Ticks(96)

    with pytest.raises(ValueError):
        from_ticks(10, str)  # type: ignore

    # Arithmetic
    t_sum = Ticks(96) + Ticks(48)
    assert t_sum == Ticks(144)
    assert Ticks(144) - Ticks(48) == Ticks(96)
    assert Ticks(96) * 2 == Ticks(192)
    assert Ticks(96) / 2 == Ticks(48)


def test_color_representation() -> None:
    """Verify Color constructors (RGB, hex, palette), conversions, and FL integer encoding."""
    # From RGB
    c_red = Color.from_rgb(255, 0, 0)
    assert c_red.rgb == RGB(255, 0, 0)
    assert c_red.to_hex() == "#FF0000"
    assert c_red.to_fl_int() == ((255 << 16) | (0 << 8) | 0)
    assert int(c_red) == c_red.to_fl_int()
    assert str(c_red) == "#FF0000"

    # From Hex
    c_hex = Color.from_hex("#00FF00")
    assert c_hex.rgb == RGB(0, 255, 0)
    assert c_hex.to_hex() == "#00FF00"

    c_hex_short = Color.from_hex("0000FF")
    assert c_hex_short.rgb == RGB(0, 0, 255)

    with pytest.raises(ValueError):
        Color.from_hex("invalid_hex")

    with pytest.raises(ValueError):
        Color.from_hex("#12345")

    # From FL Palette index (0..15)
    assert len(FL_PALETTE) == 16
    c_pal0 = Color.from_fl_palette(0)
    assert c_pal0.to_fl_int() == FL_PALETTE[0]
    assert c_pal0.palette_index == 0

    with pytest.raises(ValueError):
        Color.from_fl_palette(16)

    with pytest.raises(ValueError):
        Color.from_fl_palette(-1)

    # General constructor
    assert Color((255, 255, 255)).rgb == RGB(255, 255, 255)
    assert Color("#AABBCC").to_hex() == "#AABBCC"
    assert Color(RGB(10, 20, 30)).rgb == RGB(10, 20, 30)

    # Equality
    assert Color.from_hex("#FF0000") == Color.from_rgb(255, 0, 0)
    assert Color.from_hex("#FF0000") != Color.from_hex("#00FF00")
