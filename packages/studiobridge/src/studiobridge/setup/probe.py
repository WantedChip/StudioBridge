"""Capability and environment probe collector [PRB-01, PRB-02].

Gathers host hardware facts, OS build, Python runtime, FL Studio installation,
and MIDI port endpoints into a structured capability snapshot.
"""

from __future__ import annotations

import contextlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studiobridge._version import __version__
from studiobridge.core.paths import (
    DEFAULT_DEVICE_NAME,
    find_fl_install_dirs,
    find_fl_user_data_dir,
    get_app_data_dir,
    get_default_fl_user_data_dir,
    get_fl_hardware_dir,
)
from studiobridge.ports.base import MidiPort
from studiobridge.ports.wms import WmsDetector


@dataclass(slots=True)
class HostProbe:
    """Operating system and processor runtime environment."""

    os: str
    os_release: str
    os_version: str
    os_build: int | None
    machine: str
    python_version: str
    python_implementation: str
    python_arch: str
    is_emulated: bool


@dataclass(slots=True)
class FlStudioProbe:
    """FL Studio installation and execution state."""

    installs: list[str] = field(default_factory=list)
    user_data_dir: str | None = None
    hardware_dir: str | None = None
    is_running: bool = False
    pids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class MidiProbe:
    """MIDI subsystem and loopback endpoint topology."""

    wms_status: str
    wms_service_running: bool
    wms_loopback_available: bool
    input_ports: list[str] = field(default_factory=list)
    output_ports: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StudioBridgeProbe:
    """StudioBridge software installation and local services."""

    version: str
    app_data_dir: str
    secret_exists: bool
    device_script_installed: bool
    device_script_build_id: str | None
    broker_running: bool
    broker_port: int | None


@dataclass(slots=True)
class ProbeReport:
    """Unified environment and capability probe payload."""

    timestamp: str
    host: HostProbe
    fl_studio: FlStudioProbe
    midi: MidiProbe
    studiobridge: StudioBridgeProbe

    def to_dict(self) -> dict[str, Any]:
        """Convert probe report to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize probe report to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    def format_summary(self) -> str:
        """Format report into human-readable text."""
        os_desc = f"{self.host.os} {self.host.os_release} (build {self.host.os_build or 'unknown'})"
        arch_desc = (
            f"{self.host.machine} (Python {self.host.python_arch}, "
            f"emulated: {self.host.is_emulated})"
        )
        fl_run = f"Yes (PID {self.fl_studio.pids})" if self.fl_studio.is_running else "No"
        script_desc = "Installed" if self.studiobridge.device_script_installed else "Not installed"
        broker_desc = (
            f"Active (port {self.studiobridge.broker_port})"
            if self.studiobridge.broker_running
            else "Stopped"
        )

        lines = [
            f"StudioBridge Capability Probe ({self.timestamp})",
            "=" * 60,
            f"Host OS:        {os_desc}",
            f"Architecture:   {arch_desc}",
            f"Python:         {self.host.python_implementation} {self.host.python_version}",
            "-" * 60,
            f"FL Installed:   {len(self.fl_studio.installs)} installation(s) detected",
            f"User Data Dir:  {self.fl_studio.user_data_dir or 'Not found'}",
            f"FL Running:     {fl_run}",
            "-" * 60,
            f"WMS State:      {self.midi.wms_status} (running: {self.midi.wms_service_running})",
            f"MIDI Inputs:    {len(self.midi.input_ports)} ports",
            f"MIDI Outputs:   {len(self.midi.output_ports)} ports",
            "-" * 60,
            f"StudioBridge:   v{self.studiobridge.version}",
            f"Device Script:  {script_desc}",
            f"Broker Daemon:  {broker_desc}",
            "=" * 60,
        ]
        return "\n".join(lines)


def run_probe(
    *,
    fl_dir: Path | None = None,
    user_data_dir: Path | None = None,
    app_data_dir: Path | None = None,
    device_name: str = DEFAULT_DEVICE_NAME,
    port_backend: MidiPort | None = None,
) -> ProbeReport:
    """Inspect local machine and gather complete capability snapshot."""
    now = datetime.now(timezone.utc).isoformat()

    # 1. Host probe
    os_build = WmsDetector.detect_build()
    machine = platform.machine()
    py_arch = platform.architecture()[0]
    is_emulated = bool(
        "arm" in machine.lower() and "64" in py_arch and not sys.version.lower().startswith("arm")
    )
    host_info = HostProbe(
        os=platform.system(),
        os_release=platform.release(),
        os_version=platform.version(),
        os_build=os_build,
        machine=machine,
        python_version=sys.version.split()[0],
        python_implementation=platform.python_implementation(),
        python_arch=py_arch,
        is_emulated=is_emulated,
    )

    # 2. FL Studio probe
    installs = [str(p) for p in ([fl_dir] if fl_dir else find_fl_install_dirs())]
    resolved_user_data = user_data_dir or find_fl_user_data_dir() or get_default_fl_user_data_dir()
    hardware_dir = get_fl_hardware_dir(resolved_user_data, device_name)

    # Process check
    is_running = False
    pids: list[int] = []
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            import subprocess

            res = subprocess.run(
                ["tasklist", "/fi", "IMAGENAME eq FL64.exe", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            for line in res.stdout.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and "FL64.exe" in parts[0]:
                    with contextlib.suppress(ValueError):
                        pids.append(int(parts[1]))
            is_running = len(pids) > 0

    fl_info = FlStudioProbe(
        installs=installs,
        user_data_dir=str(resolved_user_data) if resolved_user_data.exists() else None,
        hardware_dir=str(hardware_dir) if hardware_dir.exists() else None,
        is_running=is_running,
        pids=pids,
    )

    # 3. MIDI probe
    diag = WmsDetector.detect()
    inputs: list[str] = []
    outputs: list[str] = []
    if port_backend:
        try:
            for p in port_backend.list_ports():
                if p.direction == "in":
                    inputs.append(p.name)
                elif p.direction == "out":
                    outputs.append(p.name)
        except Exception:
            pass

    midi_info = MidiProbe(
        wms_status=diag.status,
        wms_service_running=diag.service_running,
        wms_loopback_available=diag.has_custom_loopback or diag.has_default_loopback,
        input_ports=inputs,
        output_ports=outputs,
    )

    # 4. StudioBridge probe
    app_data = app_data_dir or get_app_data_dir()
    secret_file = app_data / "secret"
    script_file = hardware_dir / f"device_{device_name}.py"
    build_id: str | None = None
    if script_file.exists():
        try:
            for line in script_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("BUILD_ID ="):
                    build_id = line.split("=")[1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass

    broker_meta_path = app_data / "broker.json"
    broker_running = False
    broker_port: int | None = None
    if broker_meta_path.exists():
        try:
            meta = json.loads(broker_meta_path.read_text(encoding="utf-8"))
            broker_port = int(meta.get("port", 0))
            broker_running = broker_port > 0
        except Exception:
            pass

    sb_info = StudioBridgeProbe(
        version=__version__,
        app_data_dir=str(app_data),
        secret_exists=secret_file.exists(),
        device_script_installed=script_file.exists(),
        device_script_build_id=build_id,
        broker_running=broker_running,
        broker_port=broker_port,
    )

    return ProbeReport(
        timestamp=now,
        host=host_info,
        fl_studio=fl_info,
        midi=midi_info,
        studiobridge=sb_info,
    )
