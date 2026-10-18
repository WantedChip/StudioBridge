"""Implementation of 'sbridge setup' command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from studiobridge.setup.installer import Installer


def handle_setup(args: argparse.Namespace) -> int:
    """Execute 'sbridge setup' installation, repair, or uninstallation workflow."""
    is_json = getattr(args, "json", False)
    dry_run = getattr(args, "dry_run", False)
    repair = getattr(args, "repair", False)
    uninstall = getattr(args, "uninstall", False)
    rotate_secret = getattr(args, "rotate_secret", False)
    unsafe_device = getattr(args, "unsafe_device", False)

    fl_dir_str = getattr(args, "fl_dir", None)
    fl_dir = Path(fl_dir_str) if fl_dir_str else None
    user_data_str = getattr(args, "user_data_dir", None)
    user_data = Path(user_data_str) if user_data_str else None

    installer = Installer(
        fl_dir=fl_dir,
        user_data_dir=user_data,
        unsafe_device=unsafe_device,
    )

    try:
        if uninstall:
            report = installer.uninstall(dry_run=dry_run)
        else:
            report = installer.install(
                dry_run=dry_run,
                repair=repair,
                rotate_secret=rotate_secret,
            )

        if is_json:
            print(report.to_json())
        else:
            action_title = report.action.upper()
            print(f"StudioBridge Setup [{action_title}]")
            print("=" * 60)
            print(f"Status:        {'Success' if report.success else 'Failed'}")
            print(f"Message:       {report.message}")
            count = len(report.files if not uninstall else report.uninstalled_files)
            print(f"Files:         {count} items")
            if not uninstall and not dry_run:
                print("-" * 60)
                print("FL Studio MIDI Configuration Guidance:")
                print("1. Open FL Studio -> Options -> MIDI Settings (or press F10).")
                print(
                    f"2. Under Output, select '{report.port_root} (A)' and assign a port "
                    "number (e.g. 10)."
                )
                print(
                    f"3. Under Input, select '{report.port_root} (A)', assign the SAME port "
                    "number (10),"
                )
                print(
                    f"   set Controller type to '{report.device_name}', and enable "
                    "'Send master sync'."
                )
                print("4. In the Scripting tab, click 'Reload script' to initialize the bridge.")
                print("5. Verify the connection by running 'sbridge hello'.")
            print("=" * 60)

        return 0 if report.success else 1

    except Exception as exc:
        if is_json:
            import json

            print(json.dumps({"status": "error", "message": str(exc)}, indent=2))
        else:
            print(f"Error during setup: {exc}", file=sys.stderr)
        return 1
