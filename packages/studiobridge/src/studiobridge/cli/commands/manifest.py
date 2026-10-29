"""CLI handler for manifest subcommands: check-drift, coverage, cards, and live-diff.

Implements CLI operations for API manifest verification, scheduled CI drift detection,
and reference card generation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from studiobridge.manifest.cards import generate_all_cards
from studiobridge.manifest.drift import (
    CoverageReport,
    check_api_coverage,
    compare_manifests,
    compare_with_introspection,
    load_baseline_manifest,
)
from studiobridge.manifest.schema import Manifest


def _load_manifest_from_arg(path_arg: str | None) -> Manifest:
    """Load manifest from file path or fallback to bundled baseline fixture."""
    if path_arg:
        p = Path(path_arg)
        if not p.is_file():
            raise FileNotFoundError(f"Manifest file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            return Manifest.from_dict(json.load(f))
    return load_baseline_manifest()


def handle_manifest(args: argparse.Namespace) -> int:
    """Handle sbridge manifest subcommands."""
    action = getattr(args, "manifest_action", None)
    is_json = getattr(args, "json", False)

    if not action:
        print(
            "Usage: sbridge manifest <check-drift|coverage|cards|live-diff> [options]",
            file=sys.stderr,
        )
        return 2

    # 1. sbridge manifest check-drift
    if action == "check-drift":
        baseline_path = getattr(args, "baseline", None)
        candidate_path = getattr(args, "current", getattr(args, "candidate", None))

        baseline_manifest = _load_manifest_from_arg(baseline_path)
        candidate_manifest = _load_manifest_from_arg(candidate_path)

        report = compare_manifests(baseline_manifest, candidate_manifest)

        if is_json:
            print(report.to_json().strip())
        else:
            print(report.format_text())

        fail_on_drift = getattr(args, "fail_on_drift", False)
        fail_on_breaking = getattr(args, "fail_on_breaking", False)

        if fail_on_drift and report.has_drift:
            return 1
        if fail_on_breaking and report.has_breaking:
            return 1

        return 0

    # 2. sbridge manifest coverage
    if action == "coverage":
        manifest_path = getattr(args, "manifest", None)
        try:
            manifest = _load_manifest_from_arg(manifest_path)
            report = check_api_coverage(manifest)
        except Exception as exc:
            report = CoverageReport(
                api_version=0,
                issues=[f"Manifest schema validation failed: {exc}"],
            )

        if is_json:
            print(report.to_json().strip())
        else:
            print(report.format_text())

        # CI failure criteria: must be 100% complete
        return 0 if report.is_complete else 1

    # 3. sbridge manifest cards
    if action == "cards":
        manifest_path = getattr(args, "manifest", None)
        out_dir = getattr(args, "out", None)
        manifest = _load_manifest_from_arg(manifest_path)

        cards = generate_all_cards(manifest, output_dir=out_dir)

        if is_json:
            result = {
                "api_version": manifest.api_version,
                "total_cards": len(cards),
                "output_dir": str(out_dir) if out_dir else None,
                "uris": sorted(cards.keys()),
            }
            print(json.dumps(result, indent=2))
        else:
            msg = f"Generated {len(cards)} API reference cards for {len(manifest.modules)} modules."
            if out_dir:
                msg += f" Saved Markdown cards to: {out_dir}"
            print(msg)

        return 0

    # 4. sbridge manifest live-diff
    if action == "live-diff":
        manifest_path = getattr(args, "manifest", None)
        introspect_path = getattr(args, "introspect", None)

        if not introspect_path:
            print("Error: --introspect <path> is required for live-diff", file=sys.stderr)
            return 2

        i_file = Path(introspect_path)
        if not i_file.is_file():
            print(f"Error: Introspect file not found: {i_file}", file=sys.stderr)
            return 1

        with i_file.open("r", encoding="utf-8") as f:
            introspect_data = json.load(f)

        manifest = _load_manifest_from_arg(manifest_path)
        report = compare_with_introspection(manifest, introspect_data)

        if is_json:
            print(report.to_json().strip())
        else:
            print(report.format_text())

        return 0

    print(f"Unknown manifest action: {action}", file=sys.stderr)
    return 2
