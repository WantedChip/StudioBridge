"""Windows MIDI Services (WMS) detection, diagnostics, and loopback verification [PORT-20..28]."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Literal

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPort

MICROSOFT_MIDI_RELEASES_URL = "https://github.com/microsoft/MIDI/releases"
WINDOWS_UPDATE_GUIDANCE = "Windows Settings -> Windows Update"


@dataclass(slots=True)
class WmsDiagnostics:
    """Comprehensive diagnostic status of Windows MIDI Services stack."""

    os_build: int | None
    is_windows: bool
    is_win11_24h2_plus: bool
    service_installed: bool
    service_running: bool
    midi_cli_path: str | None
    midi_cli_version: str | None
    loopback_ports: list[str] = field(default_factory=list)
    has_custom_loopback: bool = False
    has_default_loopback: bool = False
    has_loopmidi: bool = False
    status: Literal[
        "ready",
        "service_stopped",
        "missing_loopback",
        "missing_runtime",
        "unsupported_os",
        "missing_service",
    ] = "ready"
    remedy: str = ""
    guidance_urls: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """Return True if WMS or virtual loopback is ready for StudioBridge."""
        return self.status == "ready"


class WmsDetector:
    """Detects and diagnoses Windows MIDI Services (WMS) and virtual loopback setup.

    Implements discovery rules per [PORT-21]..[PORT-28].
    """

    @classmethod
    def detect_build(cls) -> int | None:
        """Query host Windows build number via sys.getwindowsversion()."""
        if sys.platform != "win32":
            return None
        try:
            return getattr(sys.getwindowsversion(), "build", None)
        except Exception:
            return None

    @classmethod
    def query_service(cls) -> tuple[bool, bool]:
        """Query midisrv service state via sc.exe [PORT-21].

        Returns:
            Tuple of (service_installed, service_running).
        """
        if sys.platform != "win32":
            return False, False

        sc_path = shutil.which("sc.exe") or "sc.exe"
        try:
            res = subprocess.run(
                [sc_path, "query", "midisrv"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            out = res.stdout.upper()
            if res.returncode == 0 or "STATE" in out:
                is_running = "RUNNING" in out or "STATE              : 4" in out
                return True, is_running
            return False, False
        except Exception:
            return False, False

    @classmethod
    def find_midi_cli(cls) -> tuple[str | None, str | None]:
        """Find midi.exe CLI tools and query version [PORT-21].

        Returns:
            Tuple of (cli_path, version_string).
        """
        if sys.platform != "win32":
            return None, None

        cli_path = shutil.which("midi") or shutil.which("midi.exe")
        if not cli_path:
            return None, None

        version_str: str | None = None
        try:
            res = subprocess.run(
                [cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                version_str = res.stdout.strip()
        except Exception:
            pass

        return cli_path, version_str

    @classmethod
    def detect_loopmidi(cls) -> bool:
        """Check whether loopMIDI is installed on the machine [PORT-30]."""
        if sys.platform != "win32":
            return False
        loopmidi_cli = shutil.which("loopMIDI.exe") or shutil.which("loopMIDI")
        if loopmidi_cli:
            return True
        # Check standard program files path
        prog_files = os.environ.get(
            "PROGRAMFILES(X86)",
            os.environ.get("PROGRAMFILES", "C:\\Program Files"),
        )
        loopmidi_path = os.path.join(prog_files, "Tobias Erichsen", "loopMIDI", "loopMIDI.exe")
        return os.path.exists(loopmidi_path)

    @classmethod
    def restart_service(cls) -> tuple[bool, str]:
        """Attempt to restart midisrv service [PORT-25].

        Requires administrative privileges.
        Returns:
            Tuple of (success, message).
        """
        if sys.platform != "win32":
            return False, "midisrv is only available on Windows."

        sc_path = shutil.which("sc.exe") or "sc.exe"
        try:
            # First try sc start midisrv
            res = subprocess.run(
                [sc_path, "start", "midisrv"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 or "ALREADY_RUNNING" in res.stdout.upper():
                return True, "midisrv service started successfully."

            # If stopped or failed, check error
            err_msg = res.stderr or res.stdout
            if "ACCESS_DENIED" in err_msg.upper() or res.returncode == 5:
                return False, (
                    "Administrative privileges required to start midisrv. "
                    "Run 'net start midisrv' from an elevated Command Prompt / PowerShell."
                )
            return False, f"Failed to start midisrv: {err_msg.strip()}"
        except Exception as exc:
            return False, f"Error starting midisrv: {exc}"

    @classmethod
    def detect(
        cls,
        port_backend: MidiPort | None = None,
        *,
        root_name: str = "StudioBridge",
    ) -> WmsDiagnostics:
        """Perform comprehensive diagnostic scan of Windows MIDI Services [PORT-26]."""
        is_windows = sys.platform == "win32"
        build = cls.detect_build()
        is_win11_24h2 = bool(build and build >= 26100)
        svc_installed, svc_running = cls.query_service()
        midi_path, midi_ver = cls.find_midi_cli()
        has_loopmidi = cls.detect_loopmidi()

        # Enumerate visible ports if backend provided
        loopback_ports: list[str] = []
        has_custom = False
        has_default = False

        if port_backend is not None:
            try:
                ports = port_backend.list_ports()
                port_names = {p.name for p in ports}
                loopback_ports = sorted(port_names)

                # Check custom pair
                side_a = f"{root_name} (A)"
                side_b = f"{root_name} (B)"
                if (side_a in port_names or f"{root_name} A" in port_names) and (
                    side_b in port_names or f"{root_name} B" in port_names
                ):
                    has_custom = True

                # Check default loopback
                if (
                    "Default App Loopback (A)" in port_names
                    and "Default App Loopback (B)" in port_names
                ):
                    has_default = True
            except Exception:
                pass

        # Evaluate status and guidance per [PORT-26]
        guidance_urls = [MICROSOFT_MIDI_RELEASES_URL, WINDOWS_UPDATE_GUIDANCE]
        status: Literal[
            "ready",
            "service_stopped",
            "missing_loopback",
            "missing_runtime",
            "unsupported_os",
            "missing_service",
        ] = "ready"
        remedy = ""

        if not is_windows:
            status = "unsupported_os"
            remedy = (
                "Windows MIDI Services requires Windows 11. Use FakeMidiPort for local testing."
            )
        elif not is_win11_24h2:
            status = "unsupported_os"
            remedy = (
                f"Windows build {build} is older than 26100 (Windows 11 24H2+). "
                "Update Windows via Windows Update or use loopMIDI as an x64 fallback."
            )
        elif not svc_installed:
            status = "missing_service"
            remedy = (
                "Windows MIDI Services ('midisrv') is not installed. "
                f"Install latest preview from {MICROSOFT_MIDI_RELEASES_URL}."
            )
        elif not svc_running:
            status = "service_stopped"
            remedy = (
                "Windows MIDI Services ('midisrv') is stopped. "
                "Start service with 'sc start midisrv' or 'net start midisrv' as Administrator."
            )
        elif not has_custom and not has_default:
            status = "missing_loopback"
            remedy = (
                f"No virtual loopback endpoint pair detected. Create a loopback pair named "
                f"'{root_name}' using Windows MIDI Settings app or loopMIDI."
            )
        else:
            status = "ready"
            if has_default and not has_custom:
                remedy = (
                    "Using shared 'Default App Loopback' pair [PORT-28]. "
                    f"For dedicated isolation, configure a private pair named '{root_name}'."
                )
            else:
                remedy = (
                    f"Windows MIDI Services is running with active loopback pair '{root_name}'."
                )

        return WmsDiagnostics(
            os_build=build,
            is_windows=is_windows,
            is_win11_24h2_plus=is_win11_24h2,
            service_installed=svc_installed,
            service_running=svc_running,
            midi_cli_path=midi_path,
            midi_cli_version=midi_ver,
            loopback_ports=loopback_ports,
            has_custom_loopback=has_custom,
            has_default_loopback=has_default,
            has_loopmidi=has_loopmidi,
            status=status,
            remedy=remedy,
            guidance_urls=guidance_urls,
        )

    @classmethod
    def verify_endpoints(
        cls,
        port_backend: MidiPort,
        root_name: str = "StudioBridge",
        *,
        timeout: float = 2.0,
    ) -> bool:
        """Verify loopback communication by sending and receiving a probe SysEx [PORT-24].

        Enumerates ports, confirms Side A and Side B presence, opens them,
        and performs a duplex test message round-trip.
        """
        from studiobridge.ports.discovery import PortResolver

        resolver = PortResolver(port_backend)
        try:
            in_info, out_info = resolver.resolve_pair(root_name)
        except PortError:
            return False

        received_event = threading.Event()
        received_data: list[bytes] = []

        def _on_rx(msg: bytes) -> None:
            received_data.append(msg)
            received_event.set()

        test_payload = b"\xf0\x7d\x53\x42\x01\x00\x00\x00\x00\xf7"

        try:
            port_backend.open(in_info.name, out_info.name)
            port_backend.on_sysex(_on_rx)
            port_backend.send_sysex(test_payload)
            success = received_event.wait(timeout=timeout)
            return bool(success and received_data and received_data[0] == test_payload)
        except Exception:
            return False
        finally:
            with contextlib.suppress(Exception):
                port_backend.close()
