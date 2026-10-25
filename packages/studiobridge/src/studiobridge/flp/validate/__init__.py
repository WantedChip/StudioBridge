"""Structural invariant validation, static risk assessment, and FL-load verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from studiobridge.flp.validate.fl_load import (
    FlLoadHarness,
    FlLoadOutcome,
    FlLoadResult,
    LiveVerificationResult,
    verify_live_project_load,
)
from studiobridge.flp.validate.invariants import (
    check_invariants,
    validate_invariants,
)
from studiobridge.flp.validate.risk import (
    ProjectRiskReport,
    RiskCategory,
    RiskFactor,
    RiskLevel,
    calculate_project_risk,
)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Comprehensive validation report including invariants, risk scoring, and FL-load status.

    Attributes:
        invariants: List of structural invariant violation descriptions (empty if valid).
        risk: Static project risk assessment report.
        fl_load: Optional headless FL-load verification result if tested.
        live_verification: Optional live bridge verification result if tested.
    """

    invariants: list[str]
    risk: ProjectRiskReport
    fl_load: FlLoadResult | None = None
    live_verification: LiveVerificationResult | None = None

    @property
    def is_valid(self) -> bool:
        """True if zero structural invariant violations were found."""
        return len(self.invariants) == 0

    @property
    def is_safe_to_load(self) -> bool:
        """True if structural invariants pass and risk score is acceptable."""
        return self.is_valid and self.risk.is_safe_to_load

    def __iter__(self):
        """Yield invariant violation strings for backward compatibility."""
        return iter(self.invariants)

    def __len__(self) -> int:
        """Return number of invariant violations."""
        return len(self.invariants)

    def __bool__(self) -> bool:
        """Truthiness evaluates to invariant validity."""
        return self.is_valid

    def to_dict(self) -> dict[str, Any]:
        """Convert validation report to dictionary representation."""
        return {
            "is_valid": self.is_valid,
            "is_safe_to_load": self.is_safe_to_load,
            "invariants": list(self.invariants),
            "risk": self.risk.to_dict(),
            "fl_load": self.fl_load.to_dict() if self.fl_load else None,
            "live_verification": (
                self.live_verification.to_dict() if self.live_verification else None
            ),
        }


__all__ = [
    "FlLoadHarness",
    "FlLoadOutcome",
    "FlLoadResult",
    "LiveVerificationResult",
    "ProjectRiskReport",
    "RiskCategory",
    "RiskFactor",
    "RiskLevel",
    "ValidationReport",
    "calculate_project_risk",
    "check_invariants",
    "validate_invariants",
    "verify_live_project_load",
]
