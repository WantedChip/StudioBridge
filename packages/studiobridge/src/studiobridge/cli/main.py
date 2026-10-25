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
from studiobridge.cli.commands.agent import handle_agent
from studiobridge.cli.commands.api import handle_api
from studiobridge.cli.commands.broker import handle_broker
from studiobridge.cli.commands.control import (
    handle_channels_set,
    handle_mixer_set,
    handle_patterns_control,
    handle_transport_control,
)
from studiobridge.cli.commands.diag import handle_diag
from studiobridge.cli.commands.doctor import handle_doctor
from studiobridge.cli.commands.flp import handle_flp
from studiobridge.cli.commands.hello import handle_hello
from studiobridge.cli.commands.inspect import (
    handle_channels,
    handle_mixer,
    handle_patterns,
    handle_transport,
)
from studiobridge.cli.commands.manifest import handle_manifest
from studiobridge.cli.commands.mcp import handle_mcp
from studiobridge.cli.commands.notes import handle_notes
from studiobridge.cli.commands.ports import handle_ports
from studiobridge.cli.commands.probe import handle_probe
from studiobridge.cli.commands.render import handle_render
from studiobridge.cli.commands.safety import (
    handle_batch,
    handle_call,
    handle_safety,
)
from studiobridge.cli.commands.setup import handle_setup
from studiobridge.cli.commands.skill import handle_skill
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
        "--check",
        action="store_true",
        default=False,
        help="Verify MCP server startup and active tools, then exit",
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
        "transport", help="Inspect and control FL Studio playback transport"
    )
    trans_sub = trans_p.add_subparsers(
        dest="transport_action", metavar="<get|play|stop|record|tempo|pos>"
    )
    trans_get_p = trans_sub.add_parser(
        "get", help="Get current playback status, tempo, and position"
    )
    trans_get_p.set_defaults(handler=handle_transport, transport_action="get")

    trans_play_p = trans_sub.add_parser("play", help="Start or resume playback")
    trans_play_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    trans_play_p.set_defaults(handler=handle_transport_control, transport_action="play")

    trans_stop_p = trans_sub.add_parser("stop", help="Stop playback")
    trans_stop_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    trans_stop_p.set_defaults(handler=handle_transport_control, transport_action="stop")

    trans_rec_p = trans_sub.add_parser("record", help="Toggle or engage recording mode")
    trans_rec_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    trans_rec_p.set_defaults(handler=handle_transport_control, transport_action="record")

    trans_tempo_p = trans_sub.add_parser("tempo", help="Set project tempo in BPM")
    trans_tempo_p.add_argument("bpm", type=float, help="Target tempo in BPM")
    trans_tempo_p.add_argument(
        "--allow-protected",
        action="store_true",
        default=False,
        help="Allow adjusting protected tempo",
    )
    trans_tempo_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    trans_tempo_p.set_defaults(handler=handle_transport_control, transport_action="tempo")

    trans_pos_p = trans_sub.add_parser("pos", help="Set song position (ticks or normalized)")
    trans_pos_p.add_argument("ticks", type=float, help="Position in ticks or normalized 0.0-1.0")
    trans_pos_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    trans_pos_p.set_defaults(handler=handle_transport_control, transport_action="pos")

    for p in (
        trans_p,
        trans_get_p,
        trans_play_p,
        trans_stop_p,
        trans_rec_p,
        trans_tempo_p,
        trans_pos_p,
    ):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    trans_p.set_defaults(handler=handle_transport, transport_action="get")

    # 13. sbridge mixer
    mixer_p = subparsers.add_parser(
        "mixer", help="Inspect and adjust FL Studio mixer tracks, levels, and routing"
    )
    mixer_sub = mixer_p.add_subparsers(dest="mixer_action", metavar="<list|get|set>")

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

    mix_set_p = mixer_sub.add_parser(
        "set", help="Set mixer track properties (volume, pan, mute, solo, name)"
    )
    mix_set_p.add_argument("track", help="Track index (0-126) or name")
    mix_set_p.add_argument(
        "--vol", "--volume", dest="volume", type=float, default=None, help="Volume (0.0-1.0 or dB)"
    )
    mix_set_p.add_argument("--pan", type=float, default=None, help="Pan (-1.0 to 1.0)")
    mix_set_p.add_argument(
        "--mute", action=argparse.BooleanOptionalAction, default=None, help="Mute state"
    )
    mix_set_p.add_argument(
        "--solo", action=argparse.BooleanOptionalAction, default=None, help="Solo state"
    )
    mix_set_p.add_argument("--name", type=str, default=None, help="Track name")
    mix_set_p.add_argument(
        "--allow-protected",
        action="store_true",
        default=False,
        help="Allow modifying protected master track (track 0)",
    )
    mix_set_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    mix_set_p.set_defaults(handler=handle_mixer_set, mixer_action="set")

    for p in (mixer_p, mix_list_p, mix_get_p, mix_set_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    mixer_p.set_defaults(handler=handle_mixer, mixer_action="list")

    # 14. sbridge channels
    chan_p = subparsers.add_parser(
        "channels", help="Inspect and modify FL Studio generator channel rack"
    )
    chan_sub = chan_p.add_subparsers(dest="channels_action", metavar="<list|get|set>")

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

    chan_set_p = chan_sub.add_parser(
        "set", help="Set channel properties (volume, pan, name, mute, solo, steps)"
    )
    chan_set_p.add_argument("channel", help="Channel index or name")
    chan_set_p.add_argument(
        "--vol", "--volume", dest="volume", type=float, default=None, help="Volume (0.0-1.0)"
    )
    chan_set_p.add_argument("--pan", type=float, default=None, help="Pan (-1.0 to 1.0)")
    chan_set_p.add_argument("--name", type=str, default=None, help="Channel name")
    chan_set_p.add_argument(
        "--mute", action=argparse.BooleanOptionalAction, default=None, help="Mute state"
    )
    chan_set_p.add_argument(
        "--solo", action=argparse.BooleanOptionalAction, default=None, help="Solo state"
    )
    chan_set_p.add_argument(
        "--steps", type=str, default=None, help="Comma-separated 16-step grid (e.g. 1,0,0,0,1...)"
    )
    chan_set_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    chan_set_p.set_defaults(handler=handle_channels_set, channels_action="set")

    for p in (chan_p, chan_list_p, chan_get_p, chan_set_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    chan_p.set_defaults(handler=handle_channels, channels_action="list")

    # 15. sbridge patterns
    pat_p = subparsers.add_parser("patterns", help="Inspect and edit FL Studio patterns")
    pat_sub = pat_p.add_subparsers(dest="patterns_action", metavar="<list|select|rename>")

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

    pat_sel_p = pat_sub.add_parser("select", help="Select active pattern by number")
    pat_sel_p.add_argument("pattern", type=int, help="Pattern number (1-based)")
    pat_sel_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    pat_sel_p.set_defaults(handler=handle_patterns_control, patterns_action="select")

    pat_ren_p = pat_sub.add_parser("rename", help="Rename pattern")
    pat_ren_p.add_argument("pattern", type=int, help="Pattern number (1-based)")
    pat_ren_p.add_argument("name", type=str, help="New pattern name")
    pat_ren_p.add_argument("--confirm-token", type=str, default=None, help="Confirmation token")
    pat_ren_p.set_defaults(handler=handle_patterns_control, patterns_action="rename")

    for p in (pat_p, pat_list_p, pat_sel_p, pat_ren_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    pat_p.set_defaults(handler=handle_patterns, patterns_action="list")

    # 16. sbridge safety
    safety_p = subparsers.add_parser(
        "safety", help="Session safety modes, checkpoints, rollback, and journal"
    )
    safety_sub = safety_p.add_subparsers(
        dest="safety_action", metavar="<mode|checkpoint|rollback|journal>"
    )

    sm_p = safety_sub.add_parser("mode", help="Switch session safety mode (read_only|write|unsafe)")
    sm_p.add_argument("mode", choices=["read_only", "write", "unsafe"], help="Target safety mode")
    sm_p.add_argument("--reason", type=str, default=None, help="Rationale for mode change")
    sm_p.add_argument(
        "--confirm-token", type=str, default=None, help="Confirmation challenge token"
    )
    sm_p.set_defaults(handler=handle_safety, safety_action="mode")

    sc_p = safety_sub.add_parser("checkpoint", help="Record named rollback checkpoint")
    sc_p.add_argument("name", nargs="?", default="checkpoint", help="Checkpoint name")
    sc_p.set_defaults(handler=handle_safety, safety_action="checkpoint")

    sr_p = safety_sub.add_parser("rollback", help="Revert session mutations toward checkpoint")
    sr_p.add_argument("checkpoint_id", nargs="?", default=None, help="Checkpoint ID or name")
    sr_p.add_argument(
        "--confirm-token", type=str, default=None, help="Confirmation challenge token"
    )
    sr_p.set_defaults(handler=handle_safety, safety_action="rollback")

    sj_p = safety_sub.add_parser("journal", help="Inspect session mutation audit journal")
    sj_p.add_argument("--limit", type=int, default=50, help="Maximum entries to list (default: 50)")
    sj_p.add_argument("--since", type=float, default=None, help="Minimum epoch timestamp")
    sj_p.add_argument("--op", type=str, default=None, help="Operation name filter")
    sj_p.set_defaults(handler=handle_safety, safety_action="journal")

    for p in (safety_p, sm_p, sc_p, sr_p, sj_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    safety_p.set_defaults(handler=handle_safety, safety_action="mode")

    # 17. sbridge call
    call_p = subparsers.add_parser(
        "call", help="Execute raw allowlisted FL Studio Python API function"
    )
    call_p.add_argument("function", help="Function name (e.g. 'mixer.setTrackVolume')")
    call_p.add_argument("args", nargs="*", help="Function arguments (positional or key=value)")
    call_p.add_argument(
        "--verify", action="store_true", default=True, help="Verify write with read-back"
    )
    call_p.add_argument(
        "--allow-protected",
        action="store_true",
        default=False,
        help="Allow modifying protected targets",
    )
    call_p.add_argument(
        "--confirm-token", type=str, default=None, help="Confirmation challenge token"
    )
    call_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output formatted as machine-readable JSON",
    )
    call_p.set_defaults(handler=handle_call)

    # 18. sbridge batch
    batch_p = subparsers.add_parser("batch", help="Execute batch mutations with rollback on error")
    batch_p.add_argument("file", help="Path to batch JSON/NDJSON file, or '-' for stdin")
    batch_p.add_argument(
        "--allow-protected",
        action="store_true",
        default=False,
        help="Allow modifying protected targets",
    )
    batch_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output formatted as machine-readable JSON",
    )
    batch_p.set_defaults(handler=handle_batch)

    # 19. sbridge agent
    agent_p = subparsers.add_parser(
        "agent", help="Manage AI coding agent configurations and templates"
    )
    agent_sub = agent_p.add_subparsers(dest="agent_action", metavar="<list|install|snippet>")

    agent_list_p = agent_sub.add_parser(
        "list", help="List detected AI coding agents and installation status"
    )
    agent_list_p.set_defaults(handler=handle_agent, agent_action="list")

    agent_install_p = agent_sub.add_parser(
        "install", help="Install StudioBridge MCP server in target agent configuration"
    )
    agent_install_p.add_argument(
        "agent",
        help="Target agent identifier (e.g. 'cursor', 'claude-desktop', 'codex', 'all')",
    )
    agent_install_p.add_argument(
        "--scope",
        choices=["user", "project"],
        default=None,
        help="Target configuration scope",
    )
    agent_install_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview configuration diff without modifying files",
    )
    agent_install_p.add_argument(
        "--npm",
        action="store_true",
        default=False,
        help="Use npm launcher ('cmd /c npx' on Windows)",
    )
    agent_install_p.add_argument(
        "--uvx",
        action="store_true",
        default=False,
        help="Use uvx launcher (default)",
    )
    agent_install_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-apply configuration even if already present",
    )
    agent_install_p.set_defaults(handler=handle_agent, agent_action="install")

    agent_snippet_p = agent_sub.add_parser(
        "snippet", help="Print copy-pasteable MCP server configuration snippet"
    )
    agent_snippet_p.add_argument(
        "agent", help="Target agent identifier (e.g. 'cursor', 'codex', 'generic')"
    )
    agent_snippet_p.add_argument(
        "--npm", action="store_true", default=False, help="Use npm launcher"
    )
    agent_snippet_p.add_argument(
        "--uvx", action="store_true", default=False, help="Use uvx launcher (default)"
    )
    agent_snippet_p.set_defaults(handler=handle_agent, agent_action="snippet")

    for p in (agent_p, agent_list_p, agent_install_p, agent_snippet_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    agent_p.set_defaults(handler=handle_agent, agent_action="list")

    # 20. sbridge skill
    skill_p = subparsers.add_parser(
        "skill", help="Manage StudioBridge agent skills and rules (SKILL.md, AGENTS.md)"
    )
    skill_sub = skill_p.add_subparsers(dest="skill_action", metavar="<install|list|info>")

    skill_install_p = skill_sub.add_parser(
        "install", help="Install StudioBridge skill bundle to project or user agent directory"
    )
    skill_install_p.add_argument(
        "--agent",
        default=".agents",
        help=(
            "Target agent identifier "
            "(e.g. '.agents', 'claude', 'cursor', 'codex', 'gemini', 'opencode', 'all')"
        ),
    )
    skill_install_p.add_argument(
        "--scope",
        choices=["user", "project"],
        default="project",
        help="Target configuration scope (project or user)",
    )
    skill_install_p.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Custom destination directory for skill installation",
    )
    skill_install_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview installation changes without modifying files",
    )
    skill_install_p.add_argument(
        "--rules",
        dest="rules",
        action="store_true",
        default=True,
        help="Install/update AGENTS.md rules snippet (default: enabled)",
    )
    skill_install_p.add_argument(
        "--no-rules",
        dest="rules",
        action="store_false",
        help="Do not install/update AGENTS.md rules snippet",
    )
    skill_install_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-copy files even if already up to date",
    )
    skill_install_p.set_defaults(handler=handle_skill, skill_action="install")

    skill_list_p = skill_sub.add_parser("list", help="List installed StudioBridge skill locations")
    skill_list_p.add_argument(
        "--scope",
        choices=["user", "project", "all"],
        default="all",
        help="Filter installations by scope",
    )
    skill_list_p.set_defaults(handler=handle_skill, skill_action="list")

    skill_info_p = skill_sub.add_parser(
        "info", help="Show metadata, files, and AGENTS rules snippet for StudioBridge skill"
    )
    skill_info_p.set_defaults(handler=handle_skill, skill_action="info")

    for p in (skill_p, skill_install_p, skill_list_p, skill_info_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    skill_p.set_defaults(handler=handle_skill, skill_action="info")

    # 21. sbridge notes
    notes_p = subparsers.add_parser("notes", help="Piano roll note operations and MIDI translation")
    notes_sub = notes_p.add_subparsers(dest="notes_action", metavar="<apply|from-midi|read>")

    n_apply_p = notes_sub.add_parser("apply", help="Apply note definitions to FL Studio piano roll")
    n_apply_p.add_argument("file", help="Path to JSON notes file (.json) or MIDI file (.mid)")
    n_apply_p.add_argument(
        "--target", help="Target channel and pattern (e.g. 'channel:0,pattern:1')"
    )
    n_apply_p.add_argument(
        "--channel", type=int, default=None, help="Target channel index (0-based)"
    )
    n_apply_p.add_argument(
        "--pattern", type=int, default=None, help="Target pattern index (1-based)"
    )
    n_apply_p.add_argument(
        "--mode",
        choices=["append", "replace", "replace_all", "replace_range"],
        default="append",
        help="Apply mode (append|replace)",
    )
    n_apply_p.add_argument(
        "--range", help="Tick range for replace_range mode (e.g. '0:384' or '0,384')"
    )
    n_apply_p.add_argument("--ppq", type=int, default=None, help="Project PPQ tick resolution")
    n_apply_p.add_argument(
        "--verify",
        choices=["none", "oracle", "covert"],
        default="none",
        help="Verification method",
    )
    n_apply_p.add_argument(
        "--fallback",
        choices=["none", "step_grid", "midi"],
        default="none",
        help="Fallback actuation path",
    )
    n_apply_p.add_argument(
        "--allow-focus-steal",
        action="store_true",
        default=None,
        help="Allow focus steal if in background",
    )
    n_apply_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Override user-idle guard check",
    )
    n_apply_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate actuation without sending hotkey",
    )
    n_apply_p.set_defaults(handler=handle_notes, notes_action="apply")

    n_midi_p = notes_sub.add_parser(
        "from-midi", help="Convert MIDI file to structured note payload"
    )
    n_midi_p.add_argument("file", help="Path to standard MIDI file (.mid)")
    n_midi_p.add_argument("--ppq", type=int, default=96, help="Target PPQ resolution")
    n_midi_p.set_defaults(handler=handle_notes, notes_action="from-midi")

    n_read_p = notes_sub.add_parser("read", help="Read notes from saved project file or MIDI file")
    n_read_p.add_argument("file", help="Path to saved .flp or .mid file")
    n_read_p.add_argument("--pattern", type=int, default=1, help="Pattern index")
    n_read_p.add_argument("--channel", type=int, default=0, help="Channel index")
    n_read_p.set_defaults(handler=handle_notes, notes_action="read")

    for p in (notes_p, n_apply_p, n_midi_p, n_read_p):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    notes_p.set_defaults(handler=handle_notes)

    # 22. sbridge render
    render_p = subparsers.add_parser(
        "render", help="Render FL Studio project headlessly or inspect jobs"
    )
    render_p.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Path to FL Studio project (.flp) or action (status|cancel|analyze)",
    )
    render_p.add_argument(
        "job_or_file",
        nargs="?",
        default=None,
        help="Target job ID (for status/cancel) or audio file (for analyze)",
    )
    render_p.add_argument(
        "--format",
        default="wav",
        help="Export format(s): wav, mp3, flac, ogg (comma-separated)",
    )
    render_p.add_argument(
        "--out",
        "--out-dir",
        dest="out",
        default=None,
        help="Output destination directory",
    )
    render_p.add_argument(
        "--policy",
        choices=["require_closed", "close_gracefully", "force_kill"],
        default="require_closed",
        help="Instance collision policy",
    )
    render_p.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="Total render timeout in seconds",
    )
    render_p.add_argument(
        "--idle-timeout",
        type=float,
        default=120.0,
        help="Idle timeout in seconds with no output growth",
    )
    render_p.add_argument(
        "--watch",
        action="store_true",
        default=False,
        help="Poll and watch render progress until complete",
    )
    render_p.add_argument(
        "--min-duration",
        type=float,
        default=0.5,
        help="Minimum duration in seconds (for analyze)",
    )
    render_p.add_argument(
        "--max-silence",
        type=float,
        default=0.98,
        help="Maximum allowed silence ratio (for analyze)",
    )
    render_p.add_argument(
        "--allow-clipping",
        action="store_true",
        default=True,
        help="Allow clipped samples without failing validation (for analyze)",
    )
    render_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit output formatted as machine-readable JSON",
    )
    render_p.set_defaults(handler=handle_render)

    # 23. sbridge flp
    flp_p = subparsers.add_parser(
        "flp", help="Offline FL Studio project file (.flp) inspection, diffing, and validation"
    )
    flp_sub = flp_p.add_subparsers(
        dest="flp_action", metavar="<inspect|diff|roundtrip|edit|new|template>"
    )

    flp_inspect_p = flp_sub.add_parser(
        "inspect", help="Inspect .flp project structure, metadata, and tracks"
    )
    flp_inspect_p.add_argument("file", help="Path to FL Studio project file (.flp)")
    flp_inspect_p.set_defaults(handler=handle_flp, flp_action="inspect")

    flp_diff_p = flp_sub.add_parser(
        "diff", help="Semantic diff between two FL Studio project files"
    )
    flp_diff_p.add_argument("file_a", help="Path to first .flp file")
    flp_diff_p.add_argument("file_b", help="Path to second .flp file")
    flp_diff_p.set_defaults(handler=handle_flp, flp_action="diff")

    flp_roundtrip_p = flp_sub.add_parser(
        "roundtrip", help="Verify lossless byte-identical re-serialization"
    )
    flp_roundtrip_p.add_argument("file", help="Path to FL Studio project file (.flp)")
    flp_roundtrip_p.set_defaults(handler=handle_flp, flp_action="roundtrip")

    flp_edit_p = flp_sub.add_parser(
        "edit", help="Apply validated mutations and atomic saves to an .flp project"
    )
    flp_edit_p.add_argument("file", help="Path to FL Studio project file (.flp)")
    flp_edit_p.add_argument("--out", help="Destination output file path")
    flp_edit_p.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="Allow in-place overwrite with timestamped backup",
    )
    flp_edit_p.add_argument("--tempo", type=float, help="Set project tempo in BPM")
    flp_edit_p.add_argument("--title", help="Set project title")
    flp_edit_p.add_argument("--author", help="Set project author")
    flp_edit_p.add_argument("--comments", help="Set project comments")
    flp_edit_p.add_argument(
        "--rename-channel",
        action="append",
        metavar="INDEX:NAME",
        help="Rename channel (e.g. '0:Kick')",
    )
    flp_edit_p.add_argument(
        "--channel-volume",
        action="append",
        metavar="INDEX:VOL",
        help="Set channel volume (e.g. '0:0.8')",
    )
    flp_edit_p.add_argument(
        "--channel-pan",
        action="append",
        metavar="INDEX:PAN",
        help="Set channel pan (e.g. '0:-0.5')",
    )
    flp_edit_p.add_argument(
        "--rename-pattern",
        action="append",
        metavar="NUM:NAME",
        help="Rename pattern (e.g. '1:Drums')",
    )
    flp_edit_p.add_argument(
        "--clear-pattern",
        action="append",
        type=int,
        metavar="NUM",
        help="Clear notes in pattern",
    )
    flp_edit_p.add_argument(
        "--rename-track",
        action="append",
        metavar="INDEX:NAME",
        help="Rename mixer track (e.g. '1:Drums')",
    )
    flp_edit_p.add_argument(
        "--track-volume",
        action="append",
        metavar="INDEX:VOL",
        help="Set mixer track volume (e.g. '1:0.75')",
    )
    flp_edit_p.add_argument(
        "--track-mute",
        action="append",
        type=int,
        metavar="INDEX",
        help="Mute mixer track",
    )
    flp_edit_p.add_argument(
        "--track-solo",
        action="append",
        type=int,
        metavar="INDEX",
        help="Solo mixer track",
    )
    flp_edit_p.add_argument(
        "--add-marker",
        action="append",
        metavar="NAME:TICKS",
        help="Add timeline marker (e.g. 'Verse:384')",
    )
    flp_edit_p.add_argument(
        "--force-unknown-version",
        action="store_true",
        default=False,
        help="Allow writing on unverified or newer FL Studio versions",
    )
    flp_edit_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate mutations and invariants without writing output file",
    )
    flp_edit_p.set_defaults(handler=handle_flp, flp_action="edit")

    flp_new_p = flp_sub.add_parser(
        "new", help="Instantiate a fresh valid project file from a template"
    )
    flp_new_p.add_argument("output", help="Destination output .flp file path")
    flp_new_p.add_argument(
        "--template",
        "-t",
        default="minimal",
        help="Template name (default: minimal)",
    )
    flp_new_p.add_argument("--title", help="Set project title")
    flp_new_p.add_argument("--author", help="Set project author")
    flp_new_p.add_argument("--comments", help="Set project comments")
    flp_new_p.add_argument("--tempo", type=float, help="Set project tempo in BPM")
    flp_new_p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite output file if it exists",
    )
    flp_new_p.set_defaults(handler=handle_flp, flp_action="new", flp_template_action="new")

    flp_template_p = flp_sub.add_parser(
        "template", help="Manage and inspect FLP seed templates and fragments"
    )
    flp_tpl_sub = flp_template_p.add_subparsers(dest="flp_template_action", metavar="<list|add>")

    flp_tpl_list_p = flp_tpl_sub.add_parser(
        "list", help="List available seed templates and stock fragments"
    )
    flp_tpl_list_p.set_defaults(
        handler=handle_flp, flp_action="template", flp_template_action="list"
    )

    flp_tpl_add_p = flp_tpl_sub.add_parser(
        "add", help="Extract and record a fragment from an FLP project"
    )
    flp_tpl_add_p.add_argument("file", help="Path to source FL Studio project (.flp)")
    flp_tpl_add_p.add_argument("--select", required=True, help="Fragment selector (e.g. channel:3)")
    flp_tpl_add_p.add_argument("--name", help="Custom fragment name")
    flp_tpl_add_p.add_argument("--kind", help="Fragment kind (sampler, plugin, audio_clip, layer)")
    flp_tpl_add_p.add_argument("--author", help="Provenance author name")
    flp_tpl_add_p.set_defaults(handler=handle_flp, flp_action="template", flp_template_action="add")

    for p in (
        flp_p,
        flp_inspect_p,
        flp_diff_p,
        flp_roundtrip_p,
        flp_edit_p,
        flp_new_p,
        flp_template_p,
        flp_tpl_list_p,
        flp_tpl_add_p,
    ):
        p.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Emit output formatted as machine-readable JSON",
        )
    flp_p.set_defaults(handler=handle_flp)

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
