"""Implementation of 'sbridge diag' command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from studiobridge.setup.diag import create_diagnostic_bundle


def handle_diag(args: argparse.Namespace) -> int:
    """Execute 'sbridge diag' to generate a sanitized diagnostic zip archive."""
    is_json = getattr(args, "json", False)
    out_str = getattr(args, "out", None)
    out_path = Path(out_str) if out_str else None
    skip_live = getattr(args, "skip_live", True)

    try:
        bundle_path = create_diagnostic_bundle(out_path=out_path, skip_live=skip_live)
        size = bundle_path.stat().st_size

        if is_json:
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "bundle_path": str(bundle_path),
                        "size_bytes": size,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Created sanitized diagnostics bundle: {bundle_path} ({size} bytes)")
        return 0

    except Exception as exc:
        if is_json:
            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error creating diagnostic bundle: {exc}", file=sys.stderr)
        return 1
