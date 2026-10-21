"""Unit tests for Verified writes, proof levels, and tolerance engine per 09_l1_sdk.md §3.1.

Tests verification semantics:
- tolerance_matches with numbers, unit types (Volume, Pan), booleans, strings
- resolve_proof_level mapping ("readback", "display_only", "none")
- verify_mutation return structure (verified=True/False, proof level, evidence, remedy)
- strict=True raising UnverifiedWriteError with expected, actual, remedy, details
- build_expect_guard generating wire-level precondition dictionary
- Wire precondition verification and PreconditionError on guard failure
"""

from __future__ import annotations

import pytest

from studiobridge import (
    DEFAULT_TOLERANCE,
    Pan,
    PreconditionError,
    Studio,
    UnverifiedWriteError,
    Verified,
    Volume,
    build_expect_guard,
    resolve_proof_level,
    tolerance_matches,
    verify_mutation,
)


def test_tolerance_matches_numbers() -> None:
    """Verify numeric comparisons with default (0.005) and custom tolerances."""
    # Exact float matches
    assert tolerance_matches(0.8, 0.8) is True
    assert tolerance_matches(1.0, 1.0) is True

    # Within default tolerance 0.005
    assert tolerance_matches(0.8, 0.803) is True
    assert tolerance_matches(0.8, 0.797) is True

    # Exceeding default tolerance
    assert tolerance_matches(0.8, 0.806) is False
    assert tolerance_matches(0.8, 0.794) is False

    # Custom tolerance
    assert tolerance_matches(100.0, 100.08, tol=0.1) is True
    assert tolerance_matches(100.0, 100.15, tol=0.1) is False

    # Integers
    assert tolerance_matches(42, 42) is True
    assert tolerance_matches(42, 43) is False


def test_tolerance_matches_units() -> None:
    """Verify tolerance comparison extracts raw floats from unit classes."""
    vol = Volume(0.8)
    assert tolerance_matches(vol, 0.8) is True
    assert tolerance_matches(0.8, vol) is True
    assert tolerance_matches(vol, 0.802) is True
    assert tolerance_matches(vol, 0.810) is False

    pan = Pan(0.5)
    assert tolerance_matches(pan, 0.5) is True
    assert tolerance_matches(0.5, pan) is True
    assert tolerance_matches(pan, 0.503) is True
    assert tolerance_matches(pan, 0.520) is False


def test_tolerance_matches_booleans_and_strings() -> None:
    """Verify boolean and string tolerance comparisons."""
    assert tolerance_matches(True, True) is True
    assert tolerance_matches(False, False) is True
    assert tolerance_matches(True, False) is False
    assert tolerance_matches(False, True) is False

    assert tolerance_matches("Kick", "Kick") is True
    assert tolerance_matches("Kick", "Snare") is False

    # None and mismatched types
    assert tolerance_matches(None, None) is True
    assert tolerance_matches(None, 0.0) is False
    assert tolerance_matches(0.0, None) is False


def test_resolve_proof_level() -> None:
    """Verify proof level resolution per V1-A3."""
    assert resolve_proof_level(has_readback=True, display_only=False) == "readback"
    assert resolve_proof_level(has_readback=True, display_only=True) == "display_only"
    assert resolve_proof_level(has_readback=False, display_only=False) == "none"
    assert resolve_proof_level(has_readback=False, display_only=True) == "display_only"


def test_verify_mutation_success() -> None:
    """Verify successful mutation produces Verified[T] with verified=True."""
    v = verify_mutation(
        "mixer.setTrackVolume",
        expected=0.8,
        actual=0.802,
        before=0.5,
        tol=DEFAULT_TOLERANCE,
        strict=False,
        fp="test_fp_123",
        remedy="Check fader limits.",
    )
    assert isinstance(v, Verified)
    assert v.requested == 0.8
    assert v.value == 0.802
    assert v.verified is True
    assert v.plane == "live"
    assert v.settled is True
    assert v.proof == "readback"
    assert v.fp == "test_fp_123"
    assert v.evidence["before"] == 0.5
    assert v.evidence["after"] == 0.802


def test_verify_mutation_failed_non_strict() -> None:
    """Verify failed mutation returns verified=False when strict=False."""
    v = verify_mutation(
        "mixer.setTrackVolume",
        expected=0.8,
        actual=0.5,
        before=0.5,
        tol=DEFAULT_TOLERANCE,
        strict=False,
        fp="test_fp_123",
        remedy="Check fader limits.",
    )
    assert isinstance(v, Verified)
    assert v.verified is False
    assert v.value == 0.5
    assert v.evidence["after"] == 0.5


def test_verify_mutation_strict_raises_unverified_write_error() -> None:
    """Verify strict=True raises UnverifiedWriteError on tolerance mismatch."""
    with pytest.raises(UnverifiedWriteError) as exc_info:
        verify_mutation(
            "mixer.setTrackVolume",
            expected=0.8,
            actual=0.5,
            before=0.5,
            tol=DEFAULT_TOLERANCE,
            strict=True,
            fp="test_fp_123",
            remedy="Ensure mixer track is not locked by automation.",
        )

    err = exc_info.value
    assert err.target_value == 0.8
    assert err.actual_value == 0.5
    assert err.remedy == "Ensure mixer track is not locked by automation."
    assert err.details["before"] == 0.5
    assert err.details["after"] == 0.5
    assert err.details["operation"] == "mixer.setTrackVolume"


def test_build_expect_guard() -> None:
    """Verify wire-level precondition dictionary builder."""
    guard = build_expect_guard(
        fn="mixer.setTrackVolume",
        getter="mixer.getTrackVolume",
        args=[1],
        expected_value=0.8,
        tol=0.01,
    )
    assert guard["fn"] == "mixer.getTrackVolume"
    assert guard["getter"] == "mixer.getTrackVolume"
    assert guard["a"] == [1]
    assert guard["args"] == [1]
    assert guard["eq"] == 0.8
    assert guard["value"] == 0.8
    assert guard["tol"] == 0.01


def test_expect_precondition_guard_live(studio: Studio) -> None:
    """Verify expect guard raises PreconditionError when initial read-back diverges."""
    fl = studio
    # Read initial master track volume
    current_vol = fl.mixer.get_volume(0)

    # Expect matching current volume succeeds (allow_protected=True on Master track 0)
    v = fl.mixer.set_volume(0, 0.75, expect=current_vol, allow_protected=True)
    assert isinstance(v, Verified)
    assert v.verified is True

    # Calling with expect diverging from current volume should raise PreconditionError
    wrong_expect = 0.123
    with pytest.raises(PreconditionError) as exc_info:
        fl.mixer.set_volume(0, 0.8, expect=wrong_expect, allow_protected=True)

    assert exc_info.value.code == "E_PRECONDITION"
