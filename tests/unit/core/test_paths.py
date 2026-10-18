"""Unit tests for StudioBridge path resolution and FL Studio discovery.

# req: PATH-01
"""

from __future__ import annotations

from pathlib import Path

from studiobridge.core.paths import (
    ensure_app_dirs,
    find_fl_install_dirs,
    find_fl_user_data_dir,
    get_app_data_dir,
    get_broker_json_path,
    get_broker_token_path,
    get_capabilities_cache_path,
    get_config_path,
    get_documents_dir,
    get_fl_hardware_dir,
    get_fl_pianoroll_scripts_dir,
    get_jobs_dir,
    get_journal_dir,
    get_logs_dir,
    get_secret_path,
)


def test_app_data_dir_env_override(monkeypatch, tmp_path: Path):
    """Verify SBRIDGE_APP_DATA_DIR overrides local app data path.

    # req: PATH-01
    """
    custom_dir = tmp_path / "custom_appdata"
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(custom_dir))

    app_dir = get_app_data_dir()
    assert app_dir == custom_dir
    assert get_config_path() == custom_dir / "config.toml"
    assert get_broker_json_path() == custom_dir / "broker.json"
    assert get_broker_token_path() == custom_dir / "broker.token"
    assert get_secret_path() == custom_dir / "secret"
    assert get_logs_dir() == custom_dir / "logs"
    assert get_journal_dir() == custom_dir / "journal"
    assert get_capabilities_cache_path() == custom_dir / "capabilities.json"
    assert get_jobs_dir() == custom_dir / "jobs"


def test_app_data_dir_localappdata(monkeypatch, tmp_path: Path):
    """Verify %LOCALAPPDATA%\\studiobridge resolution when env override not present.

    # req: PATH-01
    """
    monkeypatch.delenv("SBRIDGE_APP_DATA_DIR", raising=False)
    fake_local = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    app_dir = get_app_data_dir()
    assert app_dir == fake_local / "studiobridge"


def test_ensure_app_dirs_creates_structure(monkeypatch, tmp_path: Path):
    """Verify ensure_app_dirs creates necessary storage subdirectories.

    # req: PATH-01
    """
    target = tmp_path / "sbridge_storage"
    monkeypatch.setenv("SBRIDGE_APP_DATA_DIR", str(target))

    assert not target.exists()
    ensure_app_dirs()
    assert target.exists()
    assert (target / "logs").is_dir()
    assert (target / "journal").is_dir()
    assert (target / "jobs").is_dir()


def test_documents_dir_override(monkeypatch, tmp_path: Path):
    """Verify SBRIDGE_DOCUMENTS_DIR override for Documents directory.

    # req: PATH-01
    """
    custom_docs = tmp_path / "MyDocuments"
    custom_docs.mkdir()
    monkeypatch.setenv("SBRIDGE_DOCUMENTS_DIR", str(custom_docs))

    docs = get_documents_dir()
    assert docs == custom_docs


def test_fl_user_data_discovery_success(monkeypatch, tmp_path: Path):
    """Verify detection of FL Studio user data directory under Documents.

    # req: PATH-01
    """
    docs_dir = tmp_path / "Documents"
    fl_user_dir = docs_dir / "Image-Line" / "FL Studio"
    fl_user_dir.mkdir(parents=True)
    monkeypatch.setenv("SBRIDGE_DOCUMENTS_DIR", str(docs_dir))
    monkeypatch.delenv("SBRIDGE_FL_USER_DIR", raising=False)

    found = find_fl_user_data_dir()
    assert found == fl_user_dir

    hw_dir = get_fl_hardware_dir(found, device_name="StudioBridge")
    assert hw_dir == fl_user_dir / "Settings" / "Hardware" / "StudioBridge"

    pr_dir = get_fl_pianoroll_scripts_dir(found)
    assert pr_dir == fl_user_dir / "Settings" / "Piano roll scripts"


def test_fl_user_data_env_override(monkeypatch, tmp_path: Path):
    """Verify SBRIDGE_FL_USER_DIR environment override.

    # req: PATH-01
    """
    custom_fl = tmp_path / "Relocated_FL"
    custom_fl.mkdir()
    monkeypatch.setenv("SBRIDGE_FL_USER_DIR", str(custom_fl))

    found = find_fl_user_data_dir()
    assert found == custom_fl


def test_fl_user_data_caller_override(tmp_path: Path):
    """Verify direct caller override for find_fl_user_data_dir.

    # req: PATH-01
    """
    custom_fl = tmp_path / "Explicit_FL"
    custom_fl.mkdir()

    found = find_fl_user_data_dir(override=custom_fl)
    assert found == custom_fl

    non_existent = tmp_path / "Does_Not_Exist"
    assert find_fl_user_data_dir(override=non_existent) is None


def test_find_fl_install_dirs_from_env(monkeypatch, tmp_path: Path):
    """Verify SBRIDGE_FL_INSTALL_DIR discovery when executable is present.

    # req: PATH-01
    """
    install_dir = tmp_path / "FL Studio 2024"
    install_dir.mkdir()
    (install_dir / "FL64.exe").touch()
    monkeypatch.setenv("SBRIDGE_FL_INSTALL_DIR", str(install_dir))

    installs = find_fl_install_dirs()
    assert len(installs) == 1
    assert installs[0] == install_dir


def test_find_fl_install_dirs_program_files(monkeypatch, tmp_path: Path):
    """Verify scanning Program Files for FL Studio installations.

    # req: PATH-01
    """
    monkeypatch.delenv("SBRIDGE_FL_INSTALL_DIR", raising=False)
    fake_pf = tmp_path / "Program Files"
    il_dir = fake_pf / "Image-Line"
    fl21 = il_dir / "FL Studio 21"
    fl24 = il_dir / "FL Studio 2024"
    other = il_dir / "Shared"
    fl21.mkdir(parents=True)
    fl24.mkdir(parents=True)
    other.mkdir(parents=True)

    (fl21 / "FL64.exe").touch()
    (fl24 / "FL.exe").touch()

    monkeypatch.setenv("ProgramFiles", str(fake_pf))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)

    installs = find_fl_install_dirs()
    assert len(installs) == 2
    install_names = [p.name for p in installs]
    assert "FL Studio 21" in install_names
    assert "FL Studio 2024" in install_names


def test_windows_documents_dir_fallbacks(monkeypatch, tmp_path: Path):
    """Verify fallback branches of _get_windows_documents_dir.

    # req: PATH-01
    """
    import sys

    from studiobridge.core.paths import _get_windows_documents_dir

    # 1. Non-win32
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _get_windows_documents_dir() is None

    # 2. Win32 with OneDrive
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("SBRIDGE_DOCUMENTS_DIR", raising=False)
    fake_od = tmp_path / "OneDrive"
    fake_od_docs = fake_od / "Documents"
    fake_od_docs.mkdir(parents=True)
    monkeypatch.setenv("OneDrive", str(fake_od))

    # Mock SHGetKnownFolderPath to fail so it falls back to OneDrive
    import ctypes

    if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "shell32"):
        monkeypatch.setattr(ctypes.windll.shell32, "SHGetKnownFolderPath", lambda *a, **k: 1)

    assert _get_windows_documents_dir() == fake_od_docs

    # 3. Win32 with USERPROFILE
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("OneDriveConsumer", raising=False)
    fake_up = tmp_path / "Users" / "Alice"
    fake_up_docs = fake_up / "Documents"
    fake_up_docs.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(fake_up))

    assert _get_windows_documents_dir() == fake_up_docs


def test_app_data_dir_platformdirs_fallback(monkeypatch):
    """Verify platformdirs fallback when LOCALAPPDATA is unset.

    # req: PATH-01
    """
    monkeypatch.delenv("SBRIDGE_APP_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    app_dir = get_app_data_dir()
    assert "studiobridge" in str(app_dir).lower()


def test_find_fl_install_dirs_with_program_files_x86(monkeypatch, tmp_path: Path):
    """Verify scanning both 64-bit and 32-bit Program Files directories.

    # req: PATH-01
    """
    monkeypatch.delenv("SBRIDGE_FL_INSTALL_DIR", raising=False)
    pf64 = tmp_path / "PF64"
    pf86 = tmp_path / "PF86"
    fl_x86 = pf86 / "Image-Line" / "FL Studio 20"
    fl_x86.mkdir(parents=True)
    (fl_x86 / "FL64.exe").touch()

    monkeypatch.setenv("ProgramFiles", str(pf64))
    monkeypatch.setenv("ProgramFiles(x86)", str(pf86))

    installs = find_fl_install_dirs()
    assert any(p.name == "FL Studio 20" for p in installs)


def test_default_fl_dirs_and_documents_env(monkeypatch, tmp_path: Path):
    """Verify get_fl_hardware_dir default and _get_windows_documents_dir with env set.

    # req: PATH-01
    """
    from studiobridge.core.paths import _get_windows_documents_dir

    fake_docs = tmp_path / "DirectDocs"
    fake_docs.mkdir()
    monkeypatch.setenv("SBRIDGE_DOCUMENTS_DIR", str(fake_docs))
    import sys

    monkeypatch.setattr(sys, "platform", "win32")

    assert _get_windows_documents_dir() == fake_docs

    hw = get_fl_hardware_dir()
    assert "Settings" in hw.parts
    assert "Hardware" in hw.parts
