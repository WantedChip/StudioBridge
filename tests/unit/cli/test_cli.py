"""Unit tests for StudioBridge CLI skeleton, arguments, exit codes, and JSON schemas."""

from __future__ import annotations

import json

import pytest

from studiobridge._version import __version__
from studiobridge.cli import ExitCode, cli_entry, main


def test_cli_version(capsys):
    """Verify --version flag outputs correct version and exits 0."""
    with pytest.raises(SystemExit) as exc:
        cli_entry(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_cli_no_args_shows_help(capsys):
    """Verify executing with no arguments shows help and returns ExitCode.USAGE."""
    code = cli_entry([])
    assert code == ExitCode.USAGE
    captured = capsys.readouterr()
    assert "usage:" in captured.out or "usage:" in captured.err


def test_cli_hello_emulator(capsys):
    """Verify 'sbridge hello --emulator' succeeds and prints handshake info."""
    code = cli_entry(["hello", "--emulator"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    assert "StudioBridge (Emulator)" in captured.out
    assert "API v" in captured.out


def test_cli_hello_emulator_json(capsys):
    """Verify 'sbridge hello --emulator --json' outputs valid schema."""
    code = cli_entry(["--json", "hello", "--emulator"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["source"] == "emulator"
    assert "api" in data
    assert "build_id" in data


def test_cli_hello_no_broker(capsys, monkeypatch, tmp_path):
    """Verify 'sbridge hello' returns ExitCode.UNAVAILABLE when broker is stopped."""
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(tmp_path))
    code = cli_entry(["hello"])
    assert code == ExitCode.UNAVAILABLE
    captured = capsys.readouterr()
    assert "Broker is not running" in captured.err or "Broker is not running" in captured.out


def test_cli_probe_json(capsys):
    """Verify 'sbridge probe --json' outputs valid machine capability schema."""
    code = cli_entry(["--json", "probe"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "host" in data
    assert "fl_studio" in data
    assert "midi" in data
    assert "studiobridge" in data
    assert data["studiobridge"]["version"] == __version__


def test_cli_doctor_json(capsys):
    """Verify 'sbridge doctor --json' executes checks and outputs structured JSON."""
    code = cli_entry(["--json", "doctor", "--skip-live"])
    # May return 0 or 10 depending on local machine environment, but JSON must be valid
    assert code in (ExitCode.OK, ExitCode.DOCTOR_ERRORS)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "checks" in data
    assert "has_errors" in data
    assert isinstance(data["checks"], list)


def test_cli_setup_dry_run_json(capsys, tmp_path, monkeypatch):
    """Verify 'sbridge setup --dry-run --json' outputs dry run report without writing."""
    user_data = tmp_path / "FL_User"
    app_data = tmp_path / "App_Data"
    monkeypatch.setenv("SBRIDGE_FL_USER_DIR", str(user_data))
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(app_data))

    code = cli_entry(["--json", "setup", "--dry-run", "--user-data-dir", str(user_data)])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["dry_run"] is True
    assert data["action"] == "dry_run"
    assert len(data["files"]) > 0


def test_cli_status_when_stopped(capsys, tmp_path, monkeypatch):
    """Verify 'sbridge status' returns ExitCode.UNAVAILABLE when broker is stopped."""
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(tmp_path))
    code = cli_entry(["status"])
    assert code == ExitCode.UNAVAILABLE
    captured = capsys.readouterr()
    assert "STOPPED" in captured.out


def test_cli_ports_list_json(capsys):
    """Verify 'sbridge ports list --json' outputs port listings."""
    code = cli_entry(["--json", "ports", "list"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "inputs" in data
    assert "outputs" in data
    assert "total" in data


def test_cli_diag_json(capsys, tmp_path, monkeypatch):
    """Verify 'sbridge diag --json' creates bundle and outputs JSON descriptor."""
    out_zip = tmp_path / "cli-diag.zip"
    code = cli_entry(["--json", "diag", "--out", str(out_zip), "--skip-live"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["bundle_path"] == str(out_zip)
    assert out_zip.exists()


def test_cli_broker_status_stopped(capsys, tmp_path, monkeypatch):
    """Verify 'sbridge broker status' returns 3 when stopped."""
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(tmp_path))
    code = cli_entry(["broker", "status"])
    assert code == ExitCode.UNAVAILABLE
    captured = capsys.readouterr()
    assert "stopped" in captured.out


def test_main_wrapper():
    """Verify main() entry point returns integer exit code when called with args."""
    res = main(["--json", "ports", "list"])
    assert res == ExitCode.OK
