"""API drift detection, live runtime introspection comparison, and coverage checking.

Compares newly scraped/candidate manifests against stored baseline fixtures,
evaluates live runtime introspection against the manifest, and verifies 100%
typing coverage for API functions and arguments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.manifest.schema import (
    ALLOWED_PARAM_TYPES,
    ALLOWED_RET_TYPES,
    ArgDoc,
    FunctionDoc,
    Manifest,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_BASELINE_MANIFEST_PATH = FIXTURES_DIR / "api_v44.json"


def load_baseline_manifest(path: Path | str | None = None) -> Manifest:
    """Load baseline manifest fixture (defaults to bundled api_v44.json)."""
    target = Path(path) if path is not None else DEFAULT_BASELINE_MANIFEST_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Baseline manifest not found at: {target}")
    with target.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Manifest.from_dict(data)


@dataclass
class DriftChange:
    """Descriptor for an individual API difference between baseline and candidate manifests."""

    category: str  # function, parameter, return_type, constant, callback, flag, module
    change_type: str  # "added", "removed", "modified"
    target: str  # e.g. "mixer.setTrackVolume", "mixer.setTrackVolume.pickupMode", "flags.FPT_Save"
    is_breaking: bool
    description: str
    old_value: Any = None
    new_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert drift change descriptor to a dictionary."""
        d: dict[str, Any] = {
            "category": self.category,
            "change_type": self.change_type,
            "target": self.target,
            "is_breaking": self.is_breaking,
            "description": self.description,
        }
        if self.old_value is not None:
            d["old_value"] = self.old_value
        if self.new_value is not None:
            d["new_value"] = self.new_value
        return d


@dataclass
class DriftReport:
    """Report detailing detected API differences, breaking status, and statistics."""

    baseline_api_version: int
    candidate_api_version: int
    changes: list[DriftChange] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True if any changes were identified."""
        return len(self.changes) > 0

    @property
    def has_breaking(self) -> bool:
        """True if any breaking changes were identified."""
        return any(c.is_breaking for c in self.changes)

    @property
    def breaking_count(self) -> int:
        """Count of breaking changes."""
        return sum(1 for c in self.changes if c.is_breaking)

    @property
    def non_breaking_count(self) -> int:
        """Count of non-breaking changes."""
        return sum(1 for c in self.changes if not c.is_breaking)

    @property
    def breaking_changes(self) -> list[DriftChange]:
        """List of breaking changes."""
        return [c for c in self.changes if c.is_breaking]

    @property
    def non_breaking_changes(self) -> list[DriftChange]:
        """List of non-breaking changes."""
        return [c for c in self.changes if not c.is_breaking]

    def to_dict(self) -> dict[str, Any]:
        """Convert drift report to a dictionary."""
        return {
            "baseline_api_version": self.baseline_api_version,
            "candidate_api_version": self.candidate_api_version,
            "has_drift": self.has_drift,
            "has_breaking": self.has_breaking,
            "breaking_count": self.breaking_count,
            "non_breaking_count": self.non_breaking_count,
            "changes": [c.to_dict() for c in self.changes],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize drift report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def format_text(self) -> str:
        """Render human-readable plain text report."""
        lines = [
            f"API Drift Report: Baseline v{self.baseline_api_version} "
            f"-> Candidate v{self.candidate_api_version}",
            f"Total Changes: {len(self.changes)} "
            f"(Breaking: {self.breaking_count}, Non-breaking: {self.non_breaking_count})",
        ]
        if not self.has_drift:
            lines.append("No drift detected. Candidate manifest matches baseline.")
            return "\n".join(lines)

        if self.breaking_changes:
            lines.append("\n[BREAKING CHANGES]")
            for c in self.breaking_changes:
                lines.append(
                    f"  ! [{c.category.upper()} {c.change_type.upper()}] "
                    f"{c.target}: {c.description}"
                )

        if self.non_breaking_changes:
            lines.append("\n[NON-BREAKING CHANGES]")
            for c in self.non_breaking_changes:
                lines.append(
                    f"  + [{c.category.upper()} {c.change_type.upper()}] "
                    f"{c.target}: {c.description}"
                )

        return "\n".join(lines)

    def format_markdown(self) -> str:
        """Render formatted GitHub-flavored Markdown report."""
        lines = [
            f"# API Drift Report: v{self.baseline_api_version} -> v{self.candidate_api_version}",
            "",
            f"- **Drift Detected:** `{'Yes' if self.has_drift else 'No'}`",
            f"- **Breaking Changes:** `{self.breaking_count}`",
            f"- **Non-Breaking Changes:** `{self.non_breaking_count}`",
            "",
        ]
        if not self.has_drift:
            lines.append("No drift detected. Candidate manifest matches baseline perfectly.")
            return "\n".join(lines)

        if self.breaking_changes:
            lines.append("## Breaking Changes")
            lines.append("")
            lines.append("| Category | Target | Type | Description |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for c in self.breaking_changes:
                lines.append(
                    f"| `{c.category}` | `{c.target}` | `{c.change_type}` | {c.description} |"
                )
            lines.append("")

        if self.non_breaking_changes:
            lines.append("## Non-Breaking Changes")
            lines.append("")
            lines.append("| Category | Target | Type | Description |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for c in self.non_breaking_changes:
                lines.append(
                    f"| `{c.category}` | `{c.target}` | `{c.change_type}` | {c.description} |"
                )
            lines.append("")

        return "\n".join(lines)


@dataclass
class LiveDiffReport:
    """Report comparing live runtime introspection against manifest."""

    api_version: int
    build_hint: str = ""
    matching_functions: list[str] = field(default_factory=list)
    missing_in_runtime: list[str] = field(default_factory=list)
    undocumented_in_runtime: list[str] = field(default_factory=list)
    matching_constants: list[str] = field(default_factory=list)
    missing_constants: list[str] = field(default_factory=list)
    undocumented_constants: list[str] = field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        """True if there is any mismatch between manifest and live runtime introspection."""
        return bool(
            self.missing_in_runtime
            or self.undocumented_in_runtime
            or self.missing_constants
            or self.undocumented_constants
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert live diff report to dictionary."""
        return {
            "api_version": self.api_version,
            "build_hint": self.build_hint,
            "has_diff": self.has_diff,
            "counts": {
                "matching_functions": len(self.matching_functions),
                "missing_in_runtime": len(self.missing_in_runtime),
                "undocumented_in_runtime": len(self.undocumented_in_runtime),
                "matching_constants": len(self.matching_constants),
                "missing_constants": len(self.missing_constants),
                "undocumented_constants": len(self.undocumented_constants),
            },
            "missing_in_runtime": sorted(self.missing_in_runtime),
            "undocumented_in_runtime": sorted(self.undocumented_in_runtime),
            "missing_constants": sorted(self.missing_constants),
            "undocumented_constants": sorted(self.undocumented_constants),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize live diff report to JSON."""
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def format_text(self) -> str:
        """Render human-readable plain text report."""
        hint = self.build_hint or "unknown build"
        lines = [
            f"Live Introspection Diff: Manifest API v{self.api_version} vs Runtime ({hint})",
            f"Matching Functions: {len(self.matching_functions)}, "
            f"Missing: {len(self.missing_in_runtime)}, "
            f"Undocumented: {len(self.undocumented_in_runtime)}",
        ]
        if not self.has_diff:
            lines.append("Runtime introspection perfectly matches manifest.")
            return "\n".join(lines)

        if self.missing_in_runtime:
            lines.append("\n[MISSING IN RUNTIME]")
            for fn in sorted(self.missing_in_runtime):
                lines.append(f"  - {fn}")

        if self.undocumented_in_runtime:
            lines.append("\n[UNDOCUMENTED IN RUNTIME]")
            for fn in sorted(self.undocumented_in_runtime):
                lines.append(f"  + {fn}")

        if self.missing_constants:
            lines.append("\n[MISSING CONSTANTS]")
            for c in sorted(self.missing_constants):
                lines.append(f"  - {c}")

        if self.undocumented_constants:
            lines.append("\n[UNDOCUMENTED CONSTANTS]")
            for c in sorted(self.undocumented_constants):
                lines.append(f"  + {c}")

        return "\n".join(lines)

    def format_markdown(self) -> str:
        """Render formatted GitHub-flavored Markdown report."""
        lines = [
            f"# Live Introspection Diff: Manifest v{self.api_version}",
            "",
            f"- **Build Hint:** `{self.build_hint or 'unknown'}`",
            f"- **Matching Functions:** `{len(self.matching_functions)}`",
            f"- **Missing in Runtime:** `{len(self.missing_in_runtime)}`",
            f"- **Undocumented in Runtime:** `{len(self.undocumented_in_runtime)}`",
            "",
        ]
        if not self.has_diff:
            lines.append("Runtime introspection matches manifest with zero discrepancies.")
            return "\n".join(lines)

        if self.missing_in_runtime:
            lines.append("## Missing in Runtime (Documented but absent)")
            lines.append("")
            for fn in sorted(self.missing_in_runtime):
                lines.append(f"- `{fn}`")
            lines.append("")

        if self.undocumented_in_runtime:
            lines.append("## Undocumented in Runtime (Present in FL but unlisted)")
            lines.append("")
            for fn in sorted(self.undocumented_in_runtime):
                lines.append(f"- `{fn}`")
            lines.append("")

        return "\n".join(lines)


@dataclass
class CoverageReport:
    """Report detailing parameter and return typing coverage across all documented functions."""

    api_version: int
    total_functions: int = 0
    fully_typed_functions: int = 0
    untyped_functions: list[str] = field(default_factory=list)
    total_parameters: int = 0
    typed_parameters: int = 0
    untyped_parameters: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """True if 100% of functions and parameters have complete, valid type information."""
        return (
            self.total_functions > 0 and len(self.untyped_functions) == 0 and len(self.issues) == 0
        )

    @property
    def function_coverage_pct(self) -> float:
        """Percentage of fully typed functions."""
        if self.total_functions == 0:
            return 0.0
        return round(100.0 * self.fully_typed_functions / self.total_functions, 2)

    @property
    def parameter_coverage_pct(self) -> float:
        """Percentage of fully typed parameters."""
        if self.total_parameters == 0:
            return 100.0
        return round(100.0 * self.typed_parameters / self.total_parameters, 2)

    def to_dict(self) -> dict[str, Any]:
        """Convert coverage report to dictionary."""
        return {
            "api_version": self.api_version,
            "is_complete": self.is_complete,
            "total_functions": self.total_functions,
            "fully_typed_functions": self.fully_typed_functions,
            "function_coverage_pct": self.function_coverage_pct,
            "total_parameters": self.total_parameters,
            "typed_parameters": self.typed_parameters,
            "parameter_coverage_pct": self.parameter_coverage_pct,
            "untyped_functions": sorted(self.untyped_functions),
            "untyped_parameters": sorted(self.untyped_parameters),
            "issues": self.issues,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize coverage report to JSON."""
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def format_text(self) -> str:
        """Render plain text report."""
        status = "PASSED (100% Covered)" if self.is_complete else "FAILED"
        fn_stat = f"{self.fully_typed_functions}/{self.total_functions}"
        param_stat = f"{self.typed_parameters}/{self.total_parameters}"
        lines = [
            f"API Typing Coverage: API v{self.api_version} — {status}",
            f"Functions: {fn_stat} ({self.function_coverage_pct}%)",
            f"Parameters: {param_stat} ({self.parameter_coverage_pct}%)",
        ]
        if self.issues:
            lines.append("\n[COVERAGE ISSUES]")
            for issue in self.issues:
                lines.append(f"  - {issue}")
        return "\n".join(lines)

    def format_markdown(self) -> str:
        """Render GitHub-flavored Markdown report."""
        status = "PASSED (100%)" if self.is_complete else "FAILED"
        fn_stat = f"{self.fully_typed_functions}/{self.total_functions}"
        param_stat = f"{self.typed_parameters}/{self.total_parameters}"
        lines = [
            f"# API Coverage Report: v{self.api_version}",
            "",
            f"- **Status:** `{status}`",
            f"- **Function Coverage:** `{self.function_coverage_pct}%` ({fn_stat})",
            f"- **Parameter Coverage:** `{self.parameter_coverage_pct}%` ({param_stat})",
            "",
        ]
        if self.issues:
            lines.append("## Coverage Deficiencies")
            lines.append("")
            for issue in self.issues:
                lines.append(f"- {issue}")
            lines.append("")
        return "\n".join(lines)


def _compare_function_signatures(
    mod_name: str,
    fn_name: str,
    base_fn: FunctionDoc,
    cand_fn: FunctionDoc,
) -> list[DriftChange]:
    """Compare two FunctionDoc descriptors and classify breaking vs non-breaking changes."""
    changes: list[DriftChange] = []
    target_fn = f"{mod_name}.{fn_name}"

    # 1. Return type
    if base_fn.ret != cand_fn.ret:
        changes.append(
            DriftChange(
                category="return_type",
                change_type="modified",
                target=target_fn,
                is_breaking=True,
                description=f"Return type changed from '{base_fn.ret}' to '{cand_fn.ret}'",
                old_value=base_fn.ret,
                new_value=cand_fn.ret,
            )
        )

    # 2. Parameters
    base_args: dict[str, ArgDoc] = {a.name: a for a in base_fn.args}
    cand_args: dict[str, ArgDoc] = {a.name: a for a in cand_fn.args}

    # Removed parameters: Breaking
    for p_name in base_args:
        if p_name not in cand_args:
            changes.append(
                DriftChange(
                    category="parameter",
                    change_type="removed",
                    target=f"{target_fn}.{p_name}",
                    is_breaking=True,
                    description=f"Parameter '{p_name}' removed from '{target_fn}'",
                )
            )

    # Added parameters: Non-breaking if optional/has default, Breaking if required
    for p_name, cand_arg in cand_args.items():
        if p_name not in base_args:
            is_optional = cand_arg.optional or cand_arg.default is not None
            desc = (
                f"Optional parameter '{p_name}' added to '{target_fn}'"
                if is_optional
                else f"Required parameter '{p_name}' added to '{target_fn}'"
            )
            changes.append(
                DriftChange(
                    category="parameter",
                    change_type="added",
                    target=f"{target_fn}.{p_name}",
                    is_breaking=not is_optional,
                    description=desc,
                    new_value=cand_arg.to_dict(),
                )
            )

    # Modified common parameters
    for p_name, base_arg in base_args.items():
        if p_name in cand_args:
            cand_arg = cand_args[p_name]
            param_target = f"{target_fn}.{p_name}"

            # Type shift: Breaking
            if base_arg.type != cand_arg.type:
                changes.append(
                    DriftChange(
                        category="parameter",
                        change_type="modified",
                        target=param_target,
                        is_breaking=True,
                        description=(
                            f"Parameter '{p_name}' type changed from "
                            f"'{base_arg.type}' to '{cand_arg.type}'"
                        ),
                        old_value=base_arg.type,
                        new_value=cand_arg.type,
                    )
                )

            # Optionality shift: Becoming required is Breaking
            if base_arg.optional and not cand_arg.optional:
                changes.append(
                    DriftChange(
                        category="parameter",
                        change_type="modified",
                        target=param_target,
                        is_breaking=True,
                        description=f"Parameter '{p_name}' changed from optional to required",
                        old_value=True,
                        new_value=False,
                    )
                )
            elif not base_arg.optional and cand_arg.optional:
                changes.append(
                    DriftChange(
                        category="parameter",
                        change_type="modified",
                        target=param_target,
                        is_breaking=False,
                        description=f"Parameter '{p_name}' relaxed from required to optional",
                        old_value=False,
                        new_value=True,
                    )
                )

            # Range shift
            if base_arg.range != cand_arg.range:
                is_narrowed = False
                if base_arg.range is not None and cand_arg.range is not None:
                    if (
                        cand_arg.range[0] > base_arg.range[0]
                        or cand_arg.range[1] < base_arg.range[1]
                    ):
                        is_narrowed = True
                elif base_arg.range is None and cand_arg.range is not None:
                    is_narrowed = True

                changes.append(
                    DriftChange(
                        category="parameter",
                        change_type="modified",
                        target=param_target,
                        is_breaking=is_narrowed,
                        description=(
                            f"Parameter '{p_name}' range changed from "
                            f"{base_arg.range} to {cand_arg.range}"
                        ),
                        old_value=base_arg.range,
                        new_value=cand_arg.range,
                    )
                )

            # Default shift: Non-breaking
            if base_arg.default != cand_arg.default:
                changes.append(
                    DriftChange(
                        category="parameter",
                        change_type="modified",
                        target=param_target,
                        is_breaking=False,
                        description=(
                            f"Parameter '{p_name}' default value changed from "
                            f"{base_arg.default!r} to {cand_arg.default!r}"
                        ),
                        old_value=base_arg.default,
                        new_value=cand_arg.default,
                    )
                )

    # 3. Mutating / Protected / Verify / Plane
    if base_fn.mutating != cand_fn.mutating:
        changes.append(
            DriftChange(
                category="function",
                change_type="modified",
                target=target_fn,
                is_breaking=False,
                description=(
                    f"Mutating behavior changed from {base_fn.mutating} to {cand_fn.mutating}"
                ),
                old_value=base_fn.mutating,
                new_value=cand_fn.mutating,
            )
        )

    if not base_fn.protected and cand_fn.protected:
        changes.append(
            DriftChange(
                category="function",
                change_type="modified",
                target=target_fn,
                is_breaking=True,
                description=f"Function '{target_fn}' is now protected",
                old_value=False,
                new_value=True,
            )
        )
    elif base_fn.protected and not cand_fn.protected:
        changes.append(
            DriftChange(
                category="function",
                change_type="modified",
                target=target_fn,
                is_breaking=False,
                description=f"Function '{target_fn}' protection removed",
                old_value=True,
                new_value=False,
            )
        )

    if base_fn.plane != cand_fn.plane:
        changes.append(
            DriftChange(
                category="function",
                change_type="modified",
                target=target_fn,
                is_breaking=True,
                description=f"Execution plane changed from '{base_fn.plane}' to '{cand_fn.plane}'",
                old_value=base_fn.plane,
                new_value=cand_fn.plane,
            )
        )

    return changes


def compare_manifests(baseline: Manifest, candidate: Manifest) -> DriftReport:
    """Compare baseline manifest with candidate manifest to detect drift and classify changes."""
    report = DriftReport(
        baseline_api_version=baseline.api_version,
        candidate_api_version=candidate.api_version,
    )

    # 1. Compare modules and their functions & constants
    for mod_name, base_mod in baseline.modules.items():
        if mod_name not in candidate.modules:
            report.changes.append(
                DriftChange(
                    category="module",
                    change_type="removed",
                    target=mod_name,
                    is_breaking=True,
                    description=f"Module '{mod_name}' removed from API",
                )
            )
            for fname in base_mod.functions:
                report.changes.append(
                    DriftChange(
                        category="function",
                        change_type="removed",
                        target=f"{mod_name}.{fname}",
                        is_breaking=True,
                        description=f"Function '{mod_name}.{fname}' removed with module deletion",
                    )
                )
            for cname in base_mod.constants:
                report.changes.append(
                    DriftChange(
                        category="constant",
                        change_type="removed",
                        target=f"{mod_name}.{cname}",
                        is_breaking=True,
                        description=f"Constant '{mod_name}.{cname}' removed with module deletion",
                    )
                )
            continue

        cand_mod = candidate.modules[mod_name]

        # Functions
        for fname, base_fn in base_mod.functions.items():
            if fname not in cand_mod.functions:
                report.changes.append(
                    DriftChange(
                        category="function",
                        change_type="removed",
                        target=f"{mod_name}.{fname}",
                        is_breaking=True,
                        description=f"Function '{mod_name}.{fname}' removed from API",
                    )
                )
            else:
                cand_fn = cand_mod.functions[fname]
                report.changes.extend(
                    _compare_function_signatures(mod_name, fname, base_fn, cand_fn)
                )

        for fname, cand_fn in cand_mod.functions.items():
            if fname not in base_mod.functions:
                report.changes.append(
                    DriftChange(
                        category="function",
                        change_type="added",
                        target=f"{mod_name}.{fname}",
                        is_breaking=False,
                        description=f"Function '{mod_name}.{fname}' added to API",
                        new_value=cand_fn.to_dict(),
                    )
                )

        # Constants
        for cname, cval in base_mod.constants.items():
            if cname not in cand_mod.constants:
                report.changes.append(
                    DriftChange(
                        category="constant",
                        change_type="removed",
                        target=f"{mod_name}.{cname}",
                        is_breaking=True,
                        description=f"Constant '{mod_name}.{cname}' removed from module",
                        old_value=cval,
                    )
                )
            elif cval != cand_mod.constants[cname]:
                report.changes.append(
                    DriftChange(
                        category="constant",
                        change_type="modified",
                        target=f"{mod_name}.{cname}",
                        is_breaking=True,
                        description=(
                            f"Constant '{mod_name}.{cname}' value changed from "
                            f"{cval!r} to {cand_mod.constants[cname]!r}"
                        ),
                        old_value=cval,
                        new_value=cand_mod.constants[cname],
                    )
                )

        for cname, cval in cand_mod.constants.items():
            if cname not in base_mod.constants:
                report.changes.append(
                    DriftChange(
                        category="constant",
                        change_type="added",
                        target=f"{mod_name}.{cname}",
                        is_breaking=False,
                        description=f"Constant '{mod_name}.{cname}' added to module",
                        new_value=cval,
                    )
                )

    # Candidate modules not in baseline
    for mod_name, cand_mod in candidate.modules.items():
        if mod_name not in baseline.modules:
            report.changes.append(
                DriftChange(
                    category="module",
                    change_type="added",
                    target=mod_name,
                    is_breaking=False,
                    description=f"Module '{mod_name}' added to API",
                )
            )
            for fname, cand_fn in cand_mod.functions.items():
                report.changes.append(
                    DriftChange(
                        category="function",
                        change_type="added",
                        target=f"{mod_name}.{fname}",
                        is_breaking=False,
                        description=f"Function '{mod_name}.{fname}' added in module '{mod_name}'",
                        new_value=cand_fn.to_dict(),
                    )
                )
            for cname, cval in cand_mod.constants.items():
                report.changes.append(
                    DriftChange(
                        category="constant",
                        change_type="added",
                        target=f"{mod_name}.{cname}",
                        is_breaking=False,
                        description=f"Constant '{mod_name}.{cname}' added in module '{mod_name}'",
                        new_value=cval,
                    )
                )

    # 2. Callbacks
    for cb_name in baseline.callbacks:
        if cb_name not in candidate.callbacks:
            report.changes.append(
                DriftChange(
                    category="callback",
                    change_type="removed",
                    target=f"callbacks.{cb_name}",
                    is_breaking=True,
                    description=f"Callback '{cb_name}' removed from API",
                )
            )

    for cb_name, cand_cb in candidate.callbacks.items():
        if cb_name not in baseline.callbacks:
            report.changes.append(
                DriftChange(
                    category="callback",
                    change_type="added",
                    target=f"callbacks.{cb_name}",
                    is_breaking=False,
                    description=f"Callback '{cb_name}' added to API",
                    new_value=cand_cb.to_dict(),
                )
            )

    # 3. Flags
    for fname, fval in baseline.flags.items():
        if fname not in candidate.flags:
            report.changes.append(
                DriftChange(
                    category="flag",
                    change_type="removed",
                    target=f"flags.{fname}",
                    is_breaking=True,
                    description=f"Flag '{fname}' removed from API",
                    old_value=fval,
                )
            )
        elif fval != candidate.flags[fname]:
            report.changes.append(
                DriftChange(
                    category="flag",
                    change_type="modified",
                    target=f"flags.{fname}",
                    is_breaking=True,
                    description=(
                        f"Flag '{fname}' value changed from {fval!r} to {candidate.flags[fname]!r}"
                    ),
                    old_value=fval,
                    new_value=candidate.flags[fname],
                )
            )

    for fname, fval in candidate.flags.items():
        if fname not in baseline.flags:
            report.changes.append(
                DriftChange(
                    category="flag",
                    change_type="added",
                    target=f"flags.{fname}",
                    is_breaking=False,
                    description=f"Flag '{fname}' added to API",
                    new_value=fval,
                )
            )

    return report


def compare_manifest_files(baseline_path: Path | str, candidate_path: Path | str) -> DriftReport:
    """Compare two manifest JSON files on disk."""
    base_file = Path(baseline_path)
    cand_file = Path(candidate_path)
    if not base_file.is_file():
        raise FileNotFoundError(f"Baseline manifest file not found: {base_file}")
    if not cand_file.is_file():
        raise FileNotFoundError(f"Candidate manifest file not found: {cand_file}")

    with base_file.open("r", encoding="utf-8") as f:
        base_manifest = Manifest.from_dict(json.load(f))
    with cand_file.open("r", encoding="utf-8") as f:
        cand_manifest = Manifest.from_dict(json.load(f))

    return compare_manifests(base_manifest, cand_manifest)


def compare_with_introspection(
    manifest: Manifest, introspect_data: dict[str, Any]
) -> LiveDiffReport:
    """Compare manifest with live runtime introspection."""
    if not isinstance(introspect_data, dict):
        raise ValueError("Introspect data must be a dictionary")

    modules_data = introspect_data.get("modules", introspect_data)
    hint = introspect_data.get("build_hint") or introspect_data.get("fl_version")
    build_hint = str(hint or manifest.fl_version_hint)

    matching_funcs: list[str] = []
    missing_funcs: list[str] = []
    undocumented_funcs: list[str] = []

    matching_consts: list[str] = []
    missing_consts: list[str] = []
    undocumented_consts: list[str] = []

    if isinstance(modules_data, dict):
        # Scan manifest modules
        for mod_name, mod_doc in manifest.modules.items():
            if mod_name not in modules_data:
                for fname in mod_doc.functions:
                    missing_funcs.append(f"{mod_name}.{fname}")
                for cname in mod_doc.constants:
                    missing_consts.append(f"{mod_name}.{cname}")
                continue

            mod_info = modules_data[mod_name]
            introspect_funcs: set[str] = set()
            introspect_consts: set[str] = set()

            if isinstance(mod_info, list):
                introspect_funcs = {str(item) for item in mod_info}
            elif isinstance(mod_info, dict):
                funcs = mod_info.get("functions", [])
                if isinstance(funcs, list):
                    introspect_funcs = {str(f) for f in funcs}
                elif isinstance(funcs, dict):
                    introspect_funcs = set(funcs.keys())

                consts = mod_info.get("constants", {})
                if isinstance(consts, (dict, list)):
                    introspect_consts = set(consts)

            # Compare functions in this module
            for fname in mod_doc.functions:
                target = f"{mod_name}.{fname}"
                if fname in introspect_funcs:
                    matching_funcs.append(target)
                else:
                    missing_funcs.append(target)

            for fname in introspect_funcs:
                if fname not in mod_doc.functions:
                    undocumented_funcs.append(f"{mod_name}.{fname}")

            # Compare constants in this module
            for cname in mod_doc.constants:
                target = f"{mod_name}.{cname}"
                if cname in introspect_consts:
                    matching_consts.append(target)
                else:
                    missing_consts.append(target)

            for cname in introspect_consts:
                if cname not in mod_doc.constants:
                    undocumented_consts.append(f"{mod_name}.{cname}")

        # Scan any modules present in runtime introspection but absent from manifest
        for mod_name, mod_info in modules_data.items():
            if mod_name not in manifest.modules:
                if isinstance(mod_info, list):
                    for fname in mod_info:
                        undocumented_funcs.append(f"{mod_name}.{fname}")
                elif isinstance(mod_info, dict):
                    funcs = mod_info.get("functions", [])
                    if isinstance(funcs, (list, dict)):
                        for fname in funcs:
                            undocumented_funcs.append(f"{mod_name}.{fname}")
                    consts = mod_info.get("constants", {})
                    if isinstance(consts, (dict, list)):
                        for cname in consts:
                            undocumented_consts.append(f"{mod_name}.{cname}")

    return LiveDiffReport(
        api_version=manifest.api_version,
        build_hint=build_hint,
        matching_functions=sorted(matching_funcs),
        missing_in_runtime=sorted(missing_funcs),
        undocumented_in_runtime=sorted(undocumented_funcs),
        matching_constants=sorted(matching_consts),
        missing_constants=sorted(missing_consts),
        undocumented_constants=sorted(undocumented_consts),
    )


def check_api_coverage(manifest: Manifest) -> CoverageReport:
    """Verify 100% parameter and return type coverage across all functions.

    Fails/reports if any function or argument has missing, invalid, or unresolved type info.
    """
    report = CoverageReport(api_version=manifest.api_version)

    for mod_name in sorted(manifest.modules.keys()):
        mod_doc = manifest.modules[mod_name]
        for fn_name in sorted(mod_doc.functions.keys()):
            fn_doc = mod_doc.functions[fn_name]
            target_fn = f"{mod_name}.{fn_name}"
            report.total_functions += 1
            fn_has_untyped = False

            # 1. Validate Return Type
            if (
                not fn_doc.ret
                or fn_doc.ret not in ALLOWED_RET_TYPES
                or fn_doc.ret in {"any", "unknown", "unresolved"}
            ):
                report.issues.append(
                    f"Function '{target_fn}' has missing or unresolved return type: {fn_doc.ret!r}"
                )
                fn_has_untyped = True

            # 2. Validate Parameters
            for arg in fn_doc.args:
                report.total_parameters += 1
                param_target = f"{target_fn}.{arg.name}"

                if (
                    not arg.type
                    or arg.type not in ALLOWED_PARAM_TYPES
                    or arg.type in {"any", "unknown", "unresolved", "none"}
                ):
                    report.issues.append(
                        f"Argument '{arg.name}' in function '{target_fn}' has "
                        f"invalid parameter type: {arg.type!r}"
                    )
                    report.untyped_parameters.append(param_target)
                    fn_has_untyped = True
                else:
                    report.typed_parameters += 1

            if fn_has_untyped:
                report.untyped_functions.append(target_fn)
            else:
                report.fully_typed_functions += 1

    return report
