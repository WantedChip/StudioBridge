"""Numeric tolerance comparison, proof level reporting, and verified mutation engine.

Implements verified writes, tolerance comparison engine against declared per-parameter
tolerances (defaulting to 0.005 per spec 09_l1_sdk.md §3), and proof levels
("readback", "display_only", "none" per V1-A3).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from studiobridge.core.errors import UnverifiedWriteError
from studiobridge.sdk.types import Verified

if TYPE_CHECKING:
    from studiobridge.sdk.journal import MutationJournal

T = TypeVar("T")

# Default numeric tolerance for floating-point comparisons per 09_l1_sdk.md §3
DEFAULT_TOLERANCE: float = 0.005

# Declared per-parameter and per-function tolerances from empirical quirks overlay
DEFAULT_QUIRK_TOLERANCES: dict[str, float] = {
    "mixer.setTrackVolume": 0.01,
    "mixer.setTrackPan": 0.01,
    "channels.setChannelVolume": 0.01,
    "channels.setChannelPan": 0.01,
    "transport.setSongPos": 0.01,
    "transport.setTempo": 0.005,
    "plugins.setParamValue": 0.01,
}

ProofLevel = Literal["readback", "display_only", "none"]


def get_declared_tolerance(fn: str) -> float:
    """Retrieve declared tolerance for a given function or return default 0.005."""
    return DEFAULT_QUIRK_TOLERANCES.get(fn, DEFAULT_TOLERANCE)


def tolerance_matches(
    expected: Any,
    actual: Any,
    tol: float = DEFAULT_TOLERANCE,
) -> bool:
    """Compare two values for equality, applying numeric tolerance to floats.

    Args:
        expected: Requested target value.
        actual: Value read back from host state.
        tol: Permissible absolute tolerance margin.

    Returns:
        True if values match within tolerance, False otherwise.
    """
    if expected is None or actual is None:
        return expected is actual

    # Boolean comparisons must not be coerced to float (since bool is a subclass of int)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(expected) == bool(actual)

    # Floating-point / numeric comparison
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        try:
            return math.isclose(float(actual), float(expected), abs_tol=float(tol))
        except (ValueError, TypeError, OverflowError):
            return False

    # Extract float representation from unit objects if present
    exp_raw = getattr(expected, "raw", None)
    if exp_raw is not None and isinstance(actual, (int, float)):
        return tolerance_matches(exp_raw, actual, tol=tol)
    act_raw = getattr(actual, "raw", None)
    if act_raw is not None and isinstance(expected, (int, float)):
        return tolerance_matches(expected, act_raw, tol=tol)

    # String comparison
    if isinstance(expected, str) and isinstance(actual, str):
        return expected == actual

    return bool(actual == expected)


def resolve_proof_level(
    *,
    has_readback: bool = True,
    display_only: bool = False,
    actual: Any = None,
) -> ProofLevel:
    """Resolve proof level reporting how a write was confirmed per V1-A3.

    - "readback": Full numeric or state readback verified from FL Studio.
    - "display_only": Confirmation was obtained only via UI text / display update.
    - "none": No post-write readback was performed.
    """
    if display_only:
        return "display_only"
    if not has_readback:
        return "none"
    return "readback"


def verify_mutation(
    fn: str,
    requested: Any = None,
    actual: Any = None,
    *,
    expected: Any = None,
    before: Any = None,
    tol: float | None = None,
    strict: bool = False,
    display_only: bool = False,
    has_readback: bool = True,
    plane: Literal["live", "offline", "render", "actuation"] = "live",
    settled: bool = True,
    fp: str | None = None,
    evidence: dict[str, Any] | None = None,
    remedy: str | None = None,
    journal: MutationJournal | None = None,
    target: Any = None,
) -> Verified[Any]:
    """Verify a state mutation against requested target and construct Verified[T].

    Args:
        fn: Qualified operation name (e.g. "mixer.setTrackVolume").
        requested: Requested target value originally sent by caller.
        actual: Value read back from FL Studio after write.
        expected: Optional alias for requested.
        before: Value read before write, if available.
        tol: Explicit numeric tolerance float. If None, declared quirk or 0.005 is used.
        strict: If True, raises UnverifiedWriteError on mismatch.
        display_only: If True, indicates confirmation is UI text only per V1-A3.
        has_readback: If False, indicates no readback was possible.
        plane: Control plane ("live", "offline", "render", "actuation").
        settled: Whether verification was performed after next idle tick.
        fp: Session fingerprint pinned during the write.
        evidence: Optional extra context dictionary to merge.
        remedy: Suggested agent action in case of failure.
        journal: Optional MutationJournal instance to automatically record the write.
        target: Optional explicit target identifier for the journal.

    Returns:
        Verified[T] result object containing value, verified flag, proof level, and evidence.

    Raises:
        UnverifiedWriteError: When strict=True and readback fails to match within tolerance.
    """
    req_val = expected if requested is None and expected is not None else requested
    applied_tol = tol if tol is not None else get_declared_tolerance(fn)
    proof: ProofLevel = resolve_proof_level(
        has_readback=has_readback,
        display_only=display_only,
        actual=actual,
    )

    if proof == "none":
        verified = req_val is None
    elif proof == "display_only":
        verified = str(actual) == str(req_val) if req_val is not None else True
    else:
        verified = tolerance_matches(req_val, actual, tol=applied_tol)

    evidence_dict: dict[str, Any] = {
        "fn": fn,
        "operation": fn,
        "before": before,
        "after": actual,
        "tolerance": applied_tol,
        "tol": applied_tol,
    }
    if evidence:
        evidence_dict.update(evidence)

    # Automatically record verified write in mutation journal if provided
    if journal is not None:
        target_desc = target
        if target_desc is None:
            if evidence:
                if "track" in evidence and "slot" in evidence:
                    target_desc = f"mixer.track.{evidence['track']}.slot.{evidence['slot']}"
                elif "track" in evidence:
                    target_desc = f"mixer.track.{evidence['track']}"
                elif "channel" in evidence:
                    target_desc = f"channel.{evidence['channel']}"
                elif "pattern" in evidence:
                    target_desc = f"pattern.{evidence['pattern']}"
                elif "playlist_track" in evidence:
                    target_desc = f"playlist.track.{evidence['playlist_track']}"
            if target_desc is None:
                target_desc = fn

        journal.record(
            op=fn,
            target=target_desc,
            before=before,
            after=actual,
            proof=proof,
            verified=verified,
            details=evidence_dict,
        )

    if strict and not verified:
        msg = (
            f"Failed to verify write for {fn}: requested {req_val!r}, "
            f"read-back got {actual!r} (tol={applied_tol})"
        )
        raise UnverifiedWriteError(
            msg,
            target_value=req_val,
            actual_value=actual,
            details=evidence_dict,
            remedy=remedy or f"Check whether parameter {fn} is automated, locked, or clamped.",
        )

    return Verified(
        value=actual,
        requested=req_val,
        verified=verified,
        plane=plane,
        settled=settled,
        proof=proof,
        fp=fp,
        evidence=evidence_dict,
    )


def build_expect_guard(
    fn: str,
    getter: str,
    args: list[Any],
    expected_value: Any,
    tol: float | None = None,
) -> dict[str, Any]:
    """Construct an opts.expect precondition guard dictionary per V1-A2.

    Args:
        fn: Mutating function name.
        getter: Paired getter function name.
        args: Positional argument list for getter.
        expected_value: Expected pre-mutation value.
        tol: Permissible tolerance for floating point comparisons.

    Returns:
        Dictionary formatted for wire opts.expect.
    """
    applied_tol = tol if tol is not None else get_declared_tolerance(fn)
    exp_val = float(expected_value) if hasattr(expected_value, "raw") else expected_value
    guard: dict[str, Any] = {
        "fn": getter,
        "getter": getter,
        "a": list(args),
        "args": list(args),
        "eq": exp_val,
        "value": exp_val,
    }
    if isinstance(exp_val, (int, float)) and not isinstance(exp_val, bool):
        guard["tol"] = applied_tol
    return guard


__all__ = [
    "DEFAULT_QUIRK_TOLERANCES",
    "DEFAULT_TOLERANCE",
    "ProofLevel",
    "build_expect_guard",
    "get_declared_tolerance",
    "resolve_proof_level",
    "tolerance_matches",
    "verify_mutation",
]
