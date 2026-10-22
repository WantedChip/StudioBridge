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
from studiobridge.cli.commands.api import handle_api
from studiobridge.cli.commands.broker import handle_broker
from studiobridge.cli.commands.diag import handle_diag
from studiobridge.cli.commands.doctor import handle_doctor
from studiobridge.cli.commands.hello import handle_hello
from studiobridge.cli.commands.inspect import (
    handle_channels,
    handle_mixer,
    handle_patterns,
    handle_transport,
)
from studiobridge.cli.commands.manifest import handle_manifest
from studiobridge.cli.commands.mcp import handle_mcp
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

    # 9. sbridge manifest
    manifest_p = subparsers.add_parser(
        "manifest", help="API manifest inspection, drift detection & documentation cards"
    )
    manifest_sub = manifest_p.add_subparsers(
        dest="manifest_action", metavar="<check-drift|coverage|cards|live-diff>"
    )

    # 9.1 check-drift
    drift_p = manifest_sub.add_parser(
        "check-drift", help="Detect API differences between baseline and candidate manifests"
    )
    drift_p.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to baseline manifest JSON (default: api_v44.json)",
    )
    drift_p.add_argument(
        "--current",
        "--candidate",
        dest="current",
        type=str,
        default=None,
        help="Path to candidate manifest JSON",
    )
    drift_p.add_argument(
        "--fail-on-drift",
        action="store_true",
        default=False,
        help="Exit with code 1 if any drift is detected",
    )
    drift_p.add_argument(
        "--fail-on-breaking",
        action="store_true",
        default=False,
        help="Exit with code 1 if breaking changes detected",
    )
    drift_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate check without side-effects",
    )
    drift_p.set_defaults(handler=handle_manifest)

    # 9.2 coverage
    cov_p = manifest_sub.add_parser(
        "coverage",
        help="Verify 100% parameter and return type coverage across all functions",
    )
    cov_p.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest JSON (default: api_v44.json)",
    )
    cov_p.set_defaults(handler=handle_manifest)

    # 9.3 cards
    cards_p = manifest_sub.add_parser(
        "cards",
        help="Generate Markdown API reference cards for docs and MCP resources",
    )
    cards_p.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest JSON (default: api_v44.json)",
    )
    cards_p.add_argument(
        "--out",
        type=str,
        default=None,
        help="Directory to write Markdown cards into",
    )
    cards_p.set_defaults(handler=handle_manifest)

    # 9.4 live-diff
    ldiff_p = manifest_sub.add_parser(
        "live-diff",
        help="Compare manifest against live runtime introspection payload",
    )
    ldiff_p.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest JSON (default: api_v44.json)",
    )
    ldiff_p.add_argument(
        "--introspect",
        type=str,
        required=True,
        help="Path to runtime introspection JSON dump",
    )
    ldiff_p.set_defaults(handler=handle_manifest)

    for p in (manifest_p, drift_p, cov_p, cards_p, ldiff_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )

    manifest_p.set_defaults(handler=handle_manifest)

    # 10. sbridge mcp
    mcp_p = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) server over stdio")
    mcp_p.add_argument(
        "--toolsets",
        type=str,
        default=None,
        help=(
            "Comma-separated active toolsets (core,inspect,control,notes,safety,render,flp,unsafe)"
        ),
    )
    mcp_p.add_argument(
        "--stdio",
        action="store_true",
        default=True,
        help="Use stdio transport (default)",
    )
    mcp_p.add_argument(
        "--adapter",
        type=str,
        choices=["auto", "fallback", "sdk"],
        default="auto",
        help="MCP host adapter (auto, fallback, sdk)",
    )
    mcp_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate toolsets and exit without starting stdio loop",
    )
    mcp_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output formatted as machine-readable JSON",
    )
    mcp_p.set_defaults(handler=handle_mcp)

    # 11. sbridge api
    api_p = subparsers.add_parser(
        "api", help="FL Studio scripting API documentation search, describe, and export"
    )
    api_sub = api_p.add_subparsers(dest="api_action", metavar="<search|describe|list|export>")

    api_search_p = api_sub.add_parser("search", help="Search FL scripting API functions")
    api_search_p.add_argument("query", nargs="?", default="", help="Search query string")
    api_search_p.add_argument("--query", dest="named_query", type=str, default=None)
    api_search_p.add_argument("--module", type=str, default=None, help="Filter by API module")
    api_search_p.add_argument("--limit", type=int, default=20, help="Maximum results to return")
    api_search_p.add_argument(
        "--constants", action="store_true", default=False, help="Include module constants"
    )
    api_search_p.set_defaults(handler=handle_api)

    api_desc_p = api_sub.add_parser(
        "describe", help="Show signature, since-version, quirks, and examples for a function"
    )
    api_desc_p.add_argument("function", help="Function name (e.g. 'mixer.setTrackVolume')")
    api_desc_p.add_argument("--module", type=str, default=None, help="Module name if not prefixed")
    api_desc_p.set_defaults(handler=handle_api)

    api_list_p = api_sub.add_parser("list", help="List all API modules or functions in a module")
    api_list_p.add_argument("module", nargs="?", default=None, help="Optional module name")
    api_list_p.set_defaults(handler=handle_api)

    api_export_p = api_sub.add_parser(
        "export", help="Export API manifest in json, pyi, or md format"
    )
    api_export_p.add_argument(
        "--format", choices=["json", "pyi", "md"], default="json", help="Export format"
    )
    api_export_p.add_argument("--out", type=str, default=None, help="Output destination path")
    api_export_p.set_defaults(handler=handle_api)

    for p in (api_p, api_search_p, api_desc_p, api_list_p, api_export_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    api_p.set_defaults(handler=handle_api)

    # 12. sbridge transport
    trans_p = subparsers.add_parser(
        "transport", help="Inspect and query FL Studio playback transport"
    )
    trans_sub = trans_p.add_subparsers(dest="transport_action", metavar="<get>")
    trans_get_p = trans_sub.add_parser(
        "get", help="Get current playback status, tempo, and position"
    )
    trans_get_p.set_defaults(handler=handle_transport)

    for p in (trans_p, trans_get_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    trans_p.set_defaults(handler=handle_transport, transport_action="get")

    # 13. sbridge mixer
    mixer_p = subparsers.add_parser(
        "mixer", help="Inspect FL Studio mixer tracks, levels, and routing"
    )
    mixer_sub = mixer_p.add_subparsers(dest="mixer_action", metavar="<list|get>")

    mix_list_p = mixer_sub.add_parser("list", help="List mixer tracks with volume, pan, peaks")
    mix_list_p.add_argument(
        "--limit", type=int, default=40, help="Maximum tracks to list (default: 40)"
    )
    mix_list_p.add_argument(
        "--cursor", type=int, default=0, help="Starting track index (default: 0)"
    )
    mix_list_p.add_argument(
        "--fields", type=str, default=None, help="Comma-separated field list or 'all'"
    )
    mix_list_p.set_defaults(handler=handle_mixer)

    mix_get_p = mixer_sub.add_parser(
        "get", help="Get mixer track status and metering by index or name"
    )
    mix_get_p.add_argument("track", help="Track index (0-126) or name")
    mix_get_p.set_defaults(handler=handle_mixer)

    for p in (mixer_p, mix_list_p, mix_get_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    mixer_p.set_defaults(handler=handle_mixer, mixer_action="list")

    # 14. sbridge channels
    chan_p = subparsers.add_parser("channels", help="Inspect FL Studio generator channel rack")
    chan_sub = chan_p.add_subparsers(dest="channels_action", metavar="<list|get>")

    chan_list_p = chan_sub.add_parser("list", help="List channels with volume, pan, and step bits")
    chan_list_p.add_argument(
        "--limit", type=int, default=20, help="Maximum channels to list (default: 20)"
    )
    chan_list_p.add_argument(
        "--cursor", type=int, default=0, help="Starting channel index (default: 0)"
    )
    chan_list_p.add_argument(
        "--fields", type=str, default=None, help="Comma-separated field list or 'all'"
    )
    chan_list_p.set_defaults(handler=handle_channels)

    chan_get_p = chan_sub.add_parser("get", help="Get channel properties and step sequencer grid")
    chan_get_p.add_argument("channel", help="Channel index or name")
    chan_get_p.set_defaults(handler=handle_channels)

    for p in (chan_p, chan_list_p, chan_get_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    chan_p.set_defaults(handler=handle_channels, channels_action="list")

    # 15. sbridge patterns
    pat_p = subparsers.add_parser("patterns", help="Inspect FL Studio patterns")
    pat_sub = pat_p.add_subparsers(dest="patterns_action", metavar="<list>")

    pat_list_p = pat_sub.add_parser("list", help="List patterns with lengths and active indicator")
    pat_list_p.add_argument(
        "--limit", type=int, default=20, help="Maximum patterns to list (default: 20)"
    )
    pat_list_p.add_argument(
        "--cursor", type=int, default=1, help="Starting pattern number (default: 1)"
    )
    pat_list_p.add_argument(
        "--fields", type=str, default=None, help="Comma-separated field list or 'all'"
    )
    pat_list_p.set_defaults(handler=handle_patterns)

    for p in (pat_p, pat_list_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    pat_p.set_defaults(handler=handle_patterns, patterns_action="list")

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
