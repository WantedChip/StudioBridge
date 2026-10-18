"""Implementation of 'sbridge doctor' command."""

from __future__ import annotations

import argparse
from pathlib import Path

from studiobridge.setup.doctor import Doctor
from studiobridge.setup.installer import Installer


def handle_doctor(args: argparse.Namespace) -> int:
    """Execute 'sbridge doctor' diagnostic health checks."""
    is_json = getattr(args, "json", False)
    do_fix = getattr(args, "fix", False)
    skip_live = getattr(args, "skip_live", False)
    fl_dir_str = getattr(args, "fl_dir", None)
    fl_dir = Path(fl_dir_str) if fl_dir_str else None

    # Run doctor
    doctor = Doctor(fl_dir=fl_dir, skip_live=skip_live)
    report = doctor.run()

    if do_fix:
        # Check if D-DEV-01 or D-SEC-01 failed and auto-repair if safe
        needs_install = any(
            c.id in ("D-DEV-01", "D-SEC-01") and c.status == "fail" for c in report.checks
        )
        if needs_install:
            installer = Installer(fl_dir=fl_dir)
            installer.install(repair=True)
            # Re-run doctor to verify fix
            report = doctor.run()

    if is_json:
        print(report.to_json())
    else:
        print(report.format_table())

    # Return exit code 10 if errors found, 0 if healthy
    return 10 if report.has_errors else 0
