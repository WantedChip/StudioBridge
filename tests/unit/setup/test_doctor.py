"""Unit tests for StudioBridge setup doctor and seeded fault verification.

Verifies [DOC-01] and diagnostic checks D-ENV-01 through D-SEC-01.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.ports.fake import FakeMidiPort
from studiobridge.setup.doctor import Doctor
from studiobridge.setup.installer import Installer


@pytest.fixture
def test_env(tmp_path: Path):
    """Create an isolated test directory structure for FL Studio and StudioBridge."""
    user_data = tmp_path / "Documents" / "Image-Line" / "FL Studio"
    user_data.mkdir(parents=True, exist_ok=True)
    app_data = tmp_path / "AppData" / "Local" / "studiobridge"
    app_data.mkdir(parents=True, exist_ok=True)
    fl_dir = tmp_path / "Program Files" / "Image-Line" / "FL Studio 24"
    fl_dir.mkdir(parents=True, exist_ok=True)
    (fl_dir / "FL64.exe").write_bytes(b"MOCK_EXE")

    return {
        "user_data": user_data,
        "app_data": app_data,
        "fl_dir": fl_dir,
    }


def test_doctor_clean_fl_closed_all_live_skipped(test_env):
    """Verify [DOC-01]: When FL Studio is closed, live checks are skipped without failing."""
    # First install valid assets
    installer = Installer(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
    )
    installer.install()

    # Create loopback port backend
    port_a, port_b = FakeMidiPort.create_pair("StudioBridge (A)", "StudioBridge (B)")

    doctor = Doctor(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        port_backend=port_a,
        is_fl_running=False,
    )
    report = doctor.run()

    assert not report.fl_running
    assert not report.has_errors
    assert report.skipped >= 5

    # Verify live checks are explicitly marked skipped
    skipped_ids = {c.id for c in report.checks if c.status == "skipped"}
    assert "D-DEV-03" in skipped_ids
    assert "D-WIRE-01" in skipped_ids
    assert "D-WIRE-02" in skipped_ids
    assert "D-SBX-01" in skipped_ids
    assert "D-ACT-01" in skipped_ids


def test_doctor_seeded_fault_missing_device_script(test_env):
    """Verify D-DEV-01: Detects missing device script and marks report as errored."""
    doctor = Doctor(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        is_fl_running=False,
    )
    report = doctor.run()

    # D-DEV-01 should fail with severity error
    check = next(c for c in report.checks if c.id == "D-DEV-01")
    assert check.status == "fail"
    assert check.severity == "error"
    assert "not found" in check.evidence
    assert report.has_errors


def test_doctor_seeded_fault_stale_build_id(test_env):
    """Verify D-DEV-02: Flags warning when device script build ID does not match package."""
    installer = Installer(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        build_id="0.0.9-stale",
    )
    installer.install()

    doctor = Doctor(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        is_fl_running=False,
    )
    report = doctor.run()

    check = next(c for c in report.checks if c.id == "D-DEV-02")
    assert check.status == "warn"
    assert "differs" in check.evidence


def test_doctor_seeded_fault_missing_fl_installation(test_env):
    """Verify D-FL-01: Detects missing FL Studio installation."""
    empty_fl_dir = test_env["fl_dir"] / "nonexistent"

    doctor = Doctor(
        fl_dir=empty_fl_dir,
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        is_fl_running=False,
    )
    report = doctor.run()

    check = next(c for c in report.checks if c.id == "D-FL-01")
    assert check.status == "fail"
    assert check.severity == "error"
    assert report.has_errors


def test_doctor_seeded_fault_port_name_too_long(test_env):
    """Verify D-PORT-04: Fails when port name exceeds 31 characters."""
    long_name = "StudioBridge_Loopback_Input_Port_Over_31_Chars"
    FakeMidiPort.register_port(long_name, long_name)
    fake_port = FakeMidiPort()

    doctor = Doctor(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        port_backend=fake_port,
        is_fl_running=False,
    )
    report = doctor.run()

    check = next(c for c in report.checks if c.id == "D-PORT-04")
    assert check.status == "fail"
    assert check.severity == "error"
    assert "exceeds 31 characters" in check.evidence


def test_doctor_table_and_json_formatting(test_env):
    """Verify formatting methods for human and machine consumption."""
    doctor = Doctor(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
        is_fl_running=False,
    )
    report = doctor.run()

    # Table output
    table_str = report.format_table()
    assert "StudioBridge Doctor Report" in table_str
    assert "D-ENV-01" in table_str
    assert "D-DEV-01" in table_str

    # JSON output
    json_str = report.to_json()
    parsed = json.loads(json_str)
    assert parsed["fl_running"] is False
    assert len(parsed["checks"]) >= 20
    assert "has_errors" in parsed


def test_installer_install_repair_uninstall_cycle(test_env):
    """Verify [SET-01, SET-02, UPG-01, UPG-02]: Full install, repair, and uninstall lifecycle."""
    installer = Installer(
        fl_dir=test_env["fl_dir"],
        user_data_dir=test_env["user_data"],
        app_data_dir=test_env["app_data"],
    )

    # 1. Dry run
    dry_report = installer.install(dry_run=True)
    assert dry_report.dry_run
    assert not (test_env["user_data"] / "Settings" / "Hardware" / "StudioBridge").exists()

    # 2. Real install
    install_report = installer.install(dry_run=False)
    assert install_report.success
    assert len(install_report.files) == 6
    secret_path = test_env["app_data"] / "secret"
    assert secret_path.exists()
    initial_secret = secret_path.read_text(encoding="utf-8")

    # Verify setup-report.json created per [SET-02]
    report_file = test_env["app_data"] / "setup-report.json"
    assert report_file.exists()

    # 3. Repair preserves secret per [UPG-01]
    repair_report = installer.install(repair=True, rotate_secret=False)
    assert repair_report.success
    repaired_secret = secret_path.read_text(encoding="utf-8")
    assert repaired_secret == initial_secret

    # 4. Uninstall removes files per [UPG-02]
    uninstall_report = installer.uninstall(dry_run=False)
    assert uninstall_report.success
    assert not report_file.exists()
    assert not (
        test_env["user_data"] / "Settings" / "Hardware" / "StudioBridge" / "device_StudioBridge.py"
    ).exists()
