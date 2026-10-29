"""Installation engine, hardware probe, and setup doctor.

Exports public setup interfaces.
"""

from __future__ import annotations

from studiobridge.setup.diag import create_diagnostic_bundle, generate_env_info
from studiobridge.setup.doctor import CheckResult, Doctor, DoctorReport
from studiobridge.setup.installer import InstalledFileRecord, Installer, SetupReport
from studiobridge.setup.probe import (
    FlStudioProbe,
    HostProbe,
    MidiProbe,
    ProbeReport,
    StudioBridgeProbe,
    run_probe,
)

__all__ = [
    "CheckResult",
    "Doctor",
    "DoctorReport",
    "FlStudioProbe",
    "HostProbe",
    "InstalledFileRecord",
    "Installer",
    "MidiProbe",
    "ProbeReport",
    "SetupReport",
    "StudioBridgeProbe",
    "create_diagnostic_bundle",
    "generate_env_info",
    "run_probe",
]
