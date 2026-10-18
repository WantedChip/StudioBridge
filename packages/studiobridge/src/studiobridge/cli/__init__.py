"""StudioBridge command-line interface entry points."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from studiobridge.cli.main import ExitCode, build_parser, cli_entry


def main(argv: Sequence[str] | None = None) -> int:
    """CLI console script entry point for 'sbridge' and 'studiobridge-mcp'."""
    code = cli_entry(argv)
    if argv is None:
        sys.exit(code)
    return code


__all__ = ["ExitCode", "build_parser", "cli_entry", "main"]
