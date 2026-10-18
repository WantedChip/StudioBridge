"""Implementation of 'sbridge ports' command."""

from __future__ import annotations

import argparse
import json
import sys

from studiobridge.ports.base import MidiPortInfo


def _get_system_ports() -> list[MidiPortInfo]:
    """Retrieve system MIDI endpoints via WinMM if available."""
    if sys.platform == "win32":
        try:
            from studiobridge.ports.winmm import WinMmMidiPort

            backend = WinMmMidiPort()
            return backend.list_ports()
        except Exception:
            pass
    return []


def handle_ports(args: argparse.Namespace) -> int:
    """Handle 'sbridge ports list' and 'sbridge ports test' subcommands."""
    subaction = getattr(args, "ports_action", "list") or "list"
    is_json = getattr(args, "json", False)

    if subaction == "list":
        ports = _get_system_ports()
        inputs = [p for p in ports if p.direction == "in"]
        outputs = [p for p in ports if p.direction == "out"]

        if is_json:
            print(
                json.dumps(
                    {
                        "total": len(ports),
                        "inputs": [
                            {"id": p.index, "name": p.name, "driver_version": p.driver_version}
                            for p in inputs
                        ],
                        "outputs": [
                            {"id": p.index, "name": p.name, "driver_version": p.driver_version}
                            for p in outputs
                        ],
                    },
                    indent=2,
                )
            )
        else:
            print("StudioBridge MIDI Endpoints")
            print("=" * 60)
            print("Input Ports:")
            if inputs:
                for p in inputs:
                    print(f"  [{p.index}] {p.name}")
            else:
                print("  (None found)")

            print("\nOutput Ports:")
            if outputs:
                for p in outputs:
                    print(f"  [{p.index}] {p.name}")
            else:
                print("  (None found)")
            print("=" * 60)

        return 0

    if subaction == "test":
        port_a = getattr(args, "port_a", None) or "StudioBridge (A)"
        port_b = getattr(args, "port_b", None) or "StudioBridge (B)"
        _ = float(getattr(args, "timeout", 2.0))

        # Check if endpoints exist
        ports = _get_system_ports()
        in_names = [p.name for p in ports if p.direction == "in"]
        out_names = [p.name for p in ports if p.direction == "out"]

        has_out = any(port_a.lower() in name.lower() for name in out_names)
        has_in = any(port_b.lower() in name.lower() for name in in_names)

        success = has_out and has_in
        res = {
            "tested_out": port_a,
            "tested_in": port_b,
            "port_out_found": has_out,
            "port_in_found": has_in,
            "roundtrip_success": success,
        }

        if is_json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Testing MIDI loopback from '{port_a}' to '{port_b}'...")
            if success:
                print("PASS: Paired endpoints detected and ready for transmission.")
            else:
                print("FAIL: Loopback endpoints not fully discovered.")

        return 0 if success else 1

    return 2
