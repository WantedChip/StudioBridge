"""StudioBridge command-line interface entry points."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from studiobridge.cli.commands.notes import handle_notes
from studiobridge.cli.commands.render import handle_render
from studiobridge.cli.main import ExitCode, build_parser, cli_entry


def main(argv: Sequence[str] | None = None) -> int:
    """CLI console script entry point for 'sbridge' and 'studiobridge-mcp'."""
    effective_argv = list(argv) if argv is not None else list(sys.argv[1:])
    prog = sys.argv[0] if sys.argv else ""
    if "studiobridge-mcp" in prog and (not effective_argv or effective_argv[0] != "mcp"):
        effective_argv = ["mcp", *effective_argv]
    code = cli_entry(effective_argv)
    if argv is None:
        sys.exit(code)
    return code


__all__ = [
    "ExitCode",
    "build_parser",
    "cli_entry",
    "handle_notes",
    "handle_render",
    "main",
]
