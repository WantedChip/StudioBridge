"""Unit tests for the hardware spike harness and probe files."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _import_test_ports_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "spikes" / "S3" / "test_ports.py"
    spec = importlib.util.spec_from_file_location("s3_test_ports", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_spikes_directory_structure() -> None:
    """Verify all required spike directories and documents exist."""
    # req: TST-05
    repo_root = Path(__file__).resolve().parents[2]
    spikes_dir = repo_root / "spikes"
    assert spikes_dir.is_dir()

    expected_files = [
        spikes_dir / "REPORT_TEMPLATE.md",
        spikes_dir / "README.md",
        spikes_dir / "S0" / "capture_env.ps1",
        spikes_dir / "S1" / "device_SBProbe.py",
        spikes_dir / "S1" / "_sbp_dummy.py",
        spikes_dir / "S1" / "SBProbePR.pyscript",
        spikes_dir / "S2" / "device_SBEcho.py",
        spikes_dir / "S3" / "test_ports.py",
        spikes_dir / "S4" / "diff_settings.ps1",
    ]

    for file_path in expected_files:
        assert file_path.is_file(), f"Missing expected spike harness file: {file_path}"
        assert file_path.stat().st_size > 0, f"File is empty: {file_path}"


def test_report_template_sections() -> None:
    """Verify REPORT_TEMPLATE.md matches required structure."""
    # req: TST-05
    repo_root = Path(__file__).resolve().parents[2]
    template_path = repo_root / "spikes" / "REPORT_TEMPLATE.md"
    content = template_path.read_text(encoding="utf-8")

    required_headers = [
        "Question",
        "Procedure Actually Followed",
        "Raw Results",
        "Interpretation",
        "Decision Unlocked",
        "Surprises",
        "Follow-ups",
        "Requirement IDs Updated",
    ]
    for header in required_headers:
        assert header in content, f"REPORT_TEMPLATE.md missing required section: '{header}'"


def test_s1_probe_controller_script_contract() -> None:
    """Verify S1 device_SBProbe.py adheres to FL Studio controller script contracts."""
    # req: TST-05, DEV-01
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "spikes" / "S1" / "device_SBProbe.py"
    code = script_path.read_text(encoding="utf-8")

    assert "# name=SBProbe" in code
    assert "def OnInit()" in code
    assert "general.getVersion()" in code


def test_s2_echo_controller_script_contract() -> None:
    """Verify S2 device_SBEcho.py defines required OnIdle and OnSysEx hooks."""
    # req: TST-05, WIRE-01
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "spikes" / "S2" / "device_SBEcho.py"
    code = script_path.read_text(encoding="utf-8")

    assert "# name=SBEcho" in code
    assert "def OnIdle()" in code
    assert "def OnSysEx(event" in code
    assert "midiOutSysex" in code


def test_s3_test_ports_enumeration() -> None:
    """Verify S3 test_ports.py port enumeration executes without exceptions."""
    # req: TST-05, PORT-20
    mod = _import_test_ports_module()
    ports = mod.enumerate_ports()
    assert isinstance(ports, dict)
    assert "inputs" in ports
    assert "outputs" in ports
    assert isinstance(ports["inputs"], list)
    assert isinstance(ports["outputs"], list)
