"""StudioBridge command-line interface parser and dispatcher.

Defines subcommands, standard exit codes, and machine-readable --json support
per spec 10_l2_interfaces.md §3.
"""

from __future__ import annotations

import argparse
import enum
import json
import sys
from collections.abc import Sequence

from studiobridge._version import __version__
from studiobridge.cli.commands.broker import handle_broker
from studiobridge.cli.commands.diag import handle_diag
from studiobridge.cli.commands.doctor import handle_doctor
from studiobridge.cli.commands.hello import handle_hello
from studiobridge.cli.commands.ports import handle_ports
from studiobridge.cli.commands.probe import handle_probe
from studiobridge.cli.commands.setup import handle_setup
from studiobridge.cli.commands.status import handle_status
from studiobridge.core.errors import StudioBridgeError


class ExitCode(enum.IntEnum):
    """Standard CLI exit codes per spec 10_l2_interfaces.md §3."""

    OK = 0
    ERROR = 1
    USAGE = 2
    UNAVAILABLE = 3
    CONNECTION = 4
    VERIFICATION = 5
    SAFETY = 6
    OFFLINE_FLP = 7
    RENDER = 8
    DOCTOR_ERRORS = 10


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="sbridge",
        description="StudioBridge — AI agent & developer bridge to Image-Line FL Studio",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output formatted as machine-readable JSON",
    )

    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        metavar="<command>",
    )

    # 1. sbridge hello
    hello_p = subparsers.add_parser("hello", help="Handshake with running broker or emulator")
    hello_p.add_argument("--timeout", type=float, default=5.0, help="Handshake timeout in seconds")
    hello_p.add_argument(
        "--emulator", action="store_true", default=False, help="Test via internal mock FL emulator"
    )
    hello_p.set_defaults(handler=handle_hello)

    # 2. sbridge doctor
    doc_p = subparsers.add_parser("doctor", help="Run diagnostic health checks")
    doc_p.add_argument(
        "--fix", action="store_true", default=False, help="Apply safe automatic remedies"
    )
    doc_p.add_argument(
        "--skip-live", action="store_true", default=False, help="Skip live FL Studio checks"
    )
    doc_p.add_argument(
        "--fl-dir", type=str, default=None, help="Override FL Studio installation directory"
    )
    doc_p.set_defaults(handler=handle_doctor)

    # 3. sbridge probe
    probe_p = subparsers.add_parser("probe", help="Inspect host environment and capabilities")
    probe_p.add_argument(
        "--fl-dir", type=str, default=None, help="Override FL Studio installation directory"
    )
    probe_p.add_argument(
        "--user-data-dir", type=str, default=None, help="Override FL Studio user data directory"
    )
    probe_p.set_defaults(handler=handle_probe)

    # 4. sbridge setup
    setup_p = subparsers.add_parser(
        "setup", help="Install, repair, or uninstall controller scripts"
    )
    setup_p.add_argument(
        "-y", "--yes", action="store_true", default=False, help="Non-interactive setup"
    )
    setup_p.add_argument(
        "--dry-run", action="store_true", default=False, help="Simulate without modifying files"
    )
    setup_p.add_argument(
        "--repair",
        action="store_true",
        default=False,
        help="Repair assets while preserving wire secret",
    )
    setup_p.add_argument(
        "--uninstall", action="store_true", default=False, help="Remove installed device scripts"
    )
    setup_p.add_argument(
        "--rotate-secret", action="store_true", default=False, help="Rotate wire HMAC secret"
    )
    setup_p.add_argument(
        "--fl-dir", type=str, default=None, help="Override FL Studio installation directory"
    )
    setup_p.add_argument(
        "--user-data-dir", type=str, default=None, help="Override FL Studio user data directory"
    )
    setup_p.add_argument(
        "--unsafe-device", action="store_true", default=False, help="Build with UNSAFE=1"
    )
    setup_p.set_defaults(handler=handle_setup)

    # 5. sbridge status
    status_p = subparsers.add_parser("status", help="Print live bridge status and lease holder")
    status_p.set_defaults(handler=handle_status)

    # 6. sbridge ports
    ports_p = subparsers.add_parser("ports", help="List and test MIDI loopback endpoints")
    ports_sub = ports_p.add_subparsers(dest="ports_action", metavar="<list|test>")

    ports_list_p = ports_sub.add_parser("list", help="List available MIDI ports")
    ports_list_p.set_defaults(handler=handle_ports)

    ports_test_p = ports_sub.add_parser("test", help="Test loopback port roundtrip transmission")
    ports_test_p.add_argument(
        "--port-a", type=str, default="StudioBridge (A)", help="Output port name"
    )
    ports_test_p.add_argument(
        "--port-b", type=str, default="StudioBridge (B)", help="Input port name"
    )
    ports_test_p.add_argument("--timeout", type=float, default=2.0, help="Timeout in seconds")
    ports_test_p.set_defaults(handler=handle_ports)

    # Default action for ports
    ports_p.set_defaults(handler=handle_ports, ports_action="list")

    # 7. sbridge broker
    broker_p = subparsers.add_parser("broker", help="Control background broker daemon")
    broker_sub = broker_p.add_subparsers(dest="broker_action", metavar="<start|stop|status>")

    b_start = broker_sub.add_parser("start", help="Start background broker daemon")
    b_start.add_argument("--host", type=str, default="127.0.0.1", help="Bind IP address")
    b_start.add_argument(
        "--port", type=int, default=None, help="TCP port (default: OS assigned ephemeral)"
    )
    b_start.add_argument("--timeout", type=float, default=8.0, help="Startup timeout in seconds")
    b_start.set_defaults(handler=handle_broker)

    b_stop = broker_sub.add_parser("stop", help="Stop running broker daemon")
    b_stop.set_defaults(handler=handle_broker)

    b_status = broker_sub.add_parser("status", help="Check broker daemon status")
    b_status.set_defaults(handler=handle_broker)

    # Default action for broker
    broker_p.set_defaults(handler=handle_broker, broker_action="status")

    # 8. sbridge diag
    diag_p = subparsers.add_parser("diag", help="Generate redacted diagnostics zip bundle")
    diag_p.add_argument("--out", type=str, default=None, help="Output zip file path")
    diag_p.add_argument(
        "--skip-live", action="store_true", default=True, help="Skip live checks in bundle"
    )
    diag_p.set_defaults(handler=handle_diag)

    return parser


def cli_entry(argv: Sequence[str] | None = None) -> int:
    """Main CLI execution entry point returning integer exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler") or args.command is None:
        parser.print_help()
        return ExitCode.USAGE

    try:
        code = args.handler(args)
        return int(code)
    except StudioBridgeError as err:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": err.code,
                        "message": str(err),
                        "details": err.details,
                        "remedy": err.remedy,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error [{err.code}]: {err}", file=sys.stderr)
            if err.remedy:
                print(f"Remedy: {err.remedy}", file=sys.stderr)
        return ExitCode.ERROR
    except Exception as exc:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_INTERNAL",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Fatal error: {exc}", file=sys.stderr)
        return ExitCode.ERROR
