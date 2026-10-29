"""Windows platform path resolution and FL Studio directory discovery.

Implements path resolution for StudioBridge local storage (%LOCALAPPDATA%\\studiobridge)
and FL Studio user data discovery (Documents\\Image-Line\\FL Studio).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import platformdirs

APP_NAME: Final[str] = "studiobridge"
DEFAULT_DEVICE_NAME: Final[str] = "StudioBridge"


def _get_windows_documents_dir() -> Path | None:
    """Resolve Windows user Documents folder via Known Folder API or environment."""
    if sys.platform != "win32":
        return None

    # Check for direct environment override first
    env_docs = os.environ.get("SBRIDGE_DOCUMENTS_DIR")
    if env_docs:
        p = Path(env_docs)
        if p.exists():
            return p

    # 1. Try Windows SHGetKnownFolderPath with FOLDERID_Documents
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        # FOLDERID_Documents: {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        guid = GUID(
            0xFDD39AD0,
            0x238F,
            0x46AF,
            (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        path_buf = ctypes.c_wchar_p()
        res = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(path_buf)
        )
        if res == 0 and path_buf.value:
            p = Path(path_buf.value)
            if p.exists():
                return p
    except Exception:
        pass

    # 2. Check OneDrive-redirected Documents
    onedrive = os.environ.get("ONEDRIVE") or os.environ.get("ONEDRIVECONSUMER")
    if onedrive:
        od_docs = Path(onedrive) / "Documents"
        if od_docs.exists():
            return od_docs

    # 3. Fallback to standard userprofile Documents
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        up_docs = Path(userprofile) / "Documents"
        if up_docs.exists():
            return up_docs

    return None


def get_documents_dir() -> Path:
    """Return the resolved user Documents directory."""
    env_override = os.environ.get("SBRIDGE_DOCUMENTS_DIR")
    if env_override:
        return Path(env_override)

    win_docs = _get_windows_documents_dir()
    if win_docs:
        return win_docs

    return Path.home() / "Documents"


def get_app_data_dir() -> Path:
    """Return the StudioBridge local application data directory.

    On Windows this resolves to %LOCALAPPDATA%\\studiobridge\\.
    On other platforms or fallbacks it uses platformdirs.
    """
    env_override = os.environ.get("SBRIDGE_APP_DATA_DIR")
    if env_override:
        return Path(env_override)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME

    return platformdirs.user_data_path(APP_NAME, appauthor=False)


def get_config_path() -> Path:
    """Return path to user config file (%LOCALAPPDATA%\\studiobridge\\config.toml)."""
    return get_app_data_dir() / "config.toml"


def get_broker_json_path() -> Path:
    """Return path to broker metadata file (%LOCALAPPDATA%\\studiobridge\\broker.json)."""
    return get_app_data_dir() / "broker.json"


def get_broker_token_path() -> Path:
    """Return path to broker token file (%LOCALAPPDATA%\\studiobridge\\broker.token)."""
    return get_app_data_dir() / "broker.token"


def get_secret_path() -> Path:
    """Return path to HMAC wire secret file (%LOCALAPPDATA%\\studiobridge\\secret)."""
    return get_app_data_dir() / "secret"


def get_logs_dir() -> Path:
    """Return path to logs directory (%LOCALAPPDATA%\\studiobridge\\logs\\)."""
    return get_app_data_dir() / "logs"


def get_journal_dir() -> Path:
    """Return path to mutation journal directory (%LOCALAPPDATA%\\studiobridge\\journal\\)."""
    return get_app_data_dir() / "journal"


def get_capabilities_cache_path() -> Path:
    """Return path to capabilities cache file (%LOCALAPPDATA%\\studiobridge\\capabilities.json)."""
    return get_app_data_dir() / "capabilities.json"


def get_jobs_dir() -> Path:
    """Return path to render jobs directory (%LOCALAPPDATA%\\studiobridge\\jobs\\)."""
    return get_app_data_dir() / "jobs"


def ensure_app_dirs() -> None:
    """Create local application data directory and standard subdirectories if missing."""
    app_data = get_app_data_dir()
    app_data.mkdir(parents=True, exist_ok=True)
    get_logs_dir().mkdir(parents=True, exist_ok=True)
    get_journal_dir().mkdir(parents=True, exist_ok=True)
    get_jobs_dir().mkdir(parents=True, exist_ok=True)


def get_default_fl_user_data_dir() -> Path:
    """Return the canonical FL Studio user data directory path."""
    return get_documents_dir() / "Image-Line" / "FL Studio"


def find_fl_user_data_dir(override: Path | None = None) -> Path | None:
    """Find the FL Studio user data directory.

    Checks:
    1. Caller-supplied override.
    2. SBRIDGE_FL_USER_DIR environment variable.
    3. Canonical user Documents\\Image-Line\\FL Studio\\.
    Returns Path if found on disk, or None if not found.
    """
    if override is not None:
        return override if override.exists() else None

    env_dir = os.environ.get("SBRIDGE_FL_USER_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p

    canonical = get_default_fl_user_data_dir()
    if canonical.exists():
        return canonical

    return None


def get_fl_hardware_dir(
    user_data_dir: Path | None = None, device_name: str = DEFAULT_DEVICE_NAME
) -> Path:
    """Return the FL Studio controller script hardware directory.

    Default: Documents\\Image-Line\\FL Studio\\Settings\\Hardware\\{device_name}\\
    """
    base = user_data_dir or find_fl_user_data_dir() or get_default_fl_user_data_dir()
    return base / "Settings" / "Hardware" / device_name


def get_fl_pianoroll_scripts_dir(user_data_dir: Path | None = None) -> Path:
    """Return the FL Studio Piano roll scripts directory.

    Default: Documents\\Image-Line\\FL Studio\\Settings\\Piano roll scripts\\
    """
    base = user_data_dir or find_fl_user_data_dir() or get_default_fl_user_data_dir()
    return base / "Settings" / "Piano roll scripts"


def find_fl_install_dirs() -> list[Path]:
    """Scan standard program locations for FL Studio installations containing FL64.exe."""
    found: list[Path] = []

    # Check environment override
    env_install = os.environ.get("SBRIDGE_FL_INSTALL_DIR")
    if env_install:
        p = Path(env_install)
        if (p / "FL64.exe").exists() or (p / "FL.exe").exists():
            found.append(p)
            return found

    # Windows standard 64-bit and 32-bit Program Files
    prog_roots: list[str] = []
    pf = os.environ.get("PROGRAMFILES")
    if pf:
        prog_roots.append(pf)
    pf86 = os.environ.get("PROGRAMFILES(X86)")
    if pf86 and pf86 != pf:
        prog_roots.append(pf86)

    for root_str in prog_roots:
        il_dir = Path(root_str) / "Image-Line"
        if not il_dir.exists():
            continue
        try:
            for child in il_dir.iterdir():
                if (
                    child.is_dir()
                    and "FL Studio" in child.name
                    and ((child / "FL64.exe").exists() or (child / "FL.exe").exists())
                ):
                    found.append(child)
        except OSError:
            pass

    return sorted(found)


def _is_subpath(target: Path, root: Path) -> bool:
    """Check if target path resides within root path."""
    try:
        t_str = os.path.normcase(str(target.resolve()))
        r_str = os.path.normcase(str(root.resolve()))
        if t_str == r_str:
            return True
        if not r_str.endswith(("\\", "/")):
            r_str = r_str + os.sep
        return t_str.startswith(r_str)
    except Exception:
        return False


def validate_safe_path(
    path: Path | str,
    allowed_roots: Sequence[Path | str] | None = None,
    allow_unc: bool = False,
) -> Path:
    """Validate that path contains no traversal attacks and resolves within safe roots.

    Guarantees [MCP-SEC]:
    - Rejects path traversal sequences (e.g. '..')
    - Rejects unauthorized UNC network paths (e.g. '\\\\server\\share')
    - Confirms path resolves within allowed safe roots (project dir, Documents,
      FL Studio user data, local app data, system temp).

    Raises:
        SecurityError: If path contains traversal sequences or escapes allowed safe roots.
    """
    from studiobridge.core.errors import SecurityError

    raw = str(path).strip()
    if not raw:
        raise SecurityError("Path cannot be empty", code="E_SECURITY")

    # 1. Reject unauthorized UNC paths
    if not allow_unc and (raw.startswith(("\\\\", "//")) or raw.startswith("\\\\?\\UNC\\")):
        raise SecurityError(
            f"Unauthorized UNC network path is forbidden: '{raw}'",
            code="E_SECURITY",
            remedy="Provide a local filesystem path within the project root or user Documents.",
        )

    # 2. Reject directory traversal sequences
    parts = Path(raw).parts
    if (
        any(p == ".." for p in parts)
        or "../" in raw
        or "..\\" in raw
        or raw.endswith(("/..", "\\..", ".."))
    ):
        raise SecurityError(
            f"Path traversal sequence '..' is forbidden: '{raw}'",
            code="E_SECURITY",
            remedy="Specify a path without '..' parent directory references.",
        )

    # 3. Resolve path
    try:
        resolved = Path(raw).resolve()
    except Exception as exc:
        raise SecurityError(
            f"Cannot resolve path '{raw}': {exc}",
            code="E_SECURITY",
        ) from exc

    # 4. Determine allowed roots
    if allowed_roots is not None:
        roots = [Path(r).resolve() for r in allowed_roots]
    else:
        import tempfile

        roots = [
            Path.cwd().resolve(),
            get_documents_dir().resolve(),
            get_default_fl_user_data_dir().resolve(),
            get_app_data_dir().resolve(),
            get_jobs_dir().resolve(),
            Path(tempfile.gettempdir()).resolve(),
        ]
        # Include configured allowlist environment paths if present
        env_allowed = os.environ.get("SBRIDGE_ALLOWED_PATHS")
        if env_allowed:
            for item in env_allowed.replace(";", ",").split(","):
                if item.strip():
                    roots.append(Path(item.strip()).resolve())

    # 5. Verify containment
    if not any(_is_subpath(resolved, r) for r in roots):
        raise SecurityError(
            f"Path '{raw}' resolves outside allowed safe directories: '{resolved}'",
            code="E_SECURITY",
            remedy=(
                "Ensure file is located within current project directory, user Documents, "
                "or configured safe roots."
            ),
        )

    return resolved
