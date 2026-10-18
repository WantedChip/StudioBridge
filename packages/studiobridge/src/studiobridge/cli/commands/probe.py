"""Implementation of 'sbridge probe' command."""

from __future__ import annotations

import argparse
from pathlib import Path

from studiobridge.setup.probe import run_probe


def handle_probe(args: argparse.Namespace) -> int:
    """Execute 'sbridge probe' capability and environment collector."""
    is_json = getattr(args, "json", False)
    fl_dir_str = getattr(args, "fl_dir", None)
    fl_dir = Path(fl_dir_str) if fl_dir_str else None
    user_data_str = getattr(args, "user_data_dir", None)
    user_data = Path(user_data_str) if user_data_str else None

    report = run_probe(fl_dir=fl_dir, user_data_dir=user_data)

    if is_json:
        print(report.to_json())
    else:
        print(report.format_summary())

    return 0
