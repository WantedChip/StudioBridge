"""Claude Desktop MCPB bundle launcher for StudioBridge.

Launches the StudioBridge Model Context Protocol server over stdio for Claude
Desktop and other desktop bundle host environments.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence


def _tokenize_command(cmd_line: str) -> list[str]:
    """Tokenize a command line string into arguments, preserving backslashes."""
    result: list[str] = []
    current: list[str] = []
    in_double = False
    in_single = False

    for ch in cmd_line:
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch.isspace() and not in_double and not in_single:
            if current:
                result.append("".join(current))
                current = []
        else:
            current.append(ch)

    if current:
        result.append("".join(current))
    return result


def _get_target_args(argv: Sequence[str]) -> list[str]:
    """Normalize CLI arguments ensuring the 'mcp' command is targeted by default."""
    args = list(argv)
    known_commands = {
        "mcp",
        "hello",
        "doctor",
        "diag",
        "probe",
        "install",
        "serve",
        "notes",
        "render",
        "flp",
    }
    if not args:
        return ["mcp"]
    if args[0] in known_commands:
        return args
    if args[0].startswith("-"):
        return ["mcp", *args]
    return args


def launch(argv: Sequence[str] | None = None) -> int:
    """Launch the StudioBridge MCP server using the best available Python runtime."""
    raw_args = list(argv) if argv is not None else list(sys.argv[1:])
    target_args = _get_target_args(raw_args)

    # 1. Custom command override via environment variable
    custom_cmd = os.environ.get("SBRIDGE_PY_CMD")
    if custom_cmd:
        parts = _tokenize_command(custom_cmd)
        cmd = [*parts, *target_args]
        res = subprocess.run(cmd, check=False)
        return res.returncode

    # 2. Direct Python import if studiobridge is installed in the current environment
    try:
        from studiobridge.cli import main as sbridge_main

        return sbridge_main(target_args)
    except ImportError:
        pass

    # 3. Prefer uvx if uv is available on PATH
    uvx_path = shutil.which("uvx")
    if uvx_path:
        cmd = [uvx_path, "studiobridge", *target_args]
        res = subprocess.run(cmd, check=False)
        return res.returncode

    # 4. Fallback to pipx if available on PATH
    pipx_path = shutil.which("pipx")
    if pipx_path:
        cmd = [pipx_path, "run", "studiobridge", *target_args]
        res = subprocess.run(cmd, check=False)
        return res.returncode

    # 5. Fallback to standard Python executable searching for module execution
    for py_candidate in ("python", "python3", "py"):
        candidate_path = shutil.which(py_candidate)
        if candidate_path:
            cmd = [candidate_path, "-m", "studiobridge.cli", *target_args]
            res = subprocess.run(cmd, check=False)
            if res.returncode == 0:
                return 0

    # 6. Diagnostics to stderr only (never corrupt stdout in MCP mode)
    sys.stderr.write(
        "Error: StudioBridge is not installed in the local environment and neither 'uvx' nor "
        "'pipx' was found on PATH.\n"
        "Please install 'uv' (https://docs.astral.sh/uv/) or install StudioBridge via:\n"
        "  pip install studiobridge\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(launch())
