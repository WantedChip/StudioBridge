"""Device script asset installer and uninstaller [SET-01, SET-02, UPG-01, UPG-02].

Manages installation of FL Studio controller script assets into
Documents\\Image-Line\\FL Studio\\Settings\\Hardware\\{DEVICE}\\.
Records file hashes in %LOCALAPPDATA%\\studiobridge\\setup-report.json for integrity
verification and clean, reversible uninstalls.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studiobridge._version import __version__
from studiobridge.core.logging import get_logger
from studiobridge.core.paths import (
    DEFAULT_DEVICE_NAME,
    find_fl_install_dirs,
    find_fl_user_data_dir,
    get_app_data_dir,
    get_default_fl_user_data_dir,
    get_fl_hardware_dir,
)
from studiobridge.device.generator import DeviceScriptGenerator

logger = get_logger("setup.installer")

DEFAULT_REPORT_FILENAME = "setup-report.json"


@dataclass(slots=True)
class InstalledFileRecord:
    """Record of an installed file including path, hash, and size."""

    name: str
    path: str
    sha256: str
    size: int


@dataclass(slots=True)
class SetupReport:
    """Detailed report of setup installation or uninstallation action."""

    action: str  # "install", "repair", "uninstall", "dry_run"
    installed_at: str
    build_id: str
    device_name: str
    port_root: str
    hardware_dir: str
    user_data_dir: str
    secret_path: str
    files: list[dict[str, Any]] = field(default_factory=list)
    uninstalled_files: list[str] = field(default_factory=list)
    success: bool = True
    dry_run: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary representation."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class Installer:
    """Engine for installing, repairing, and uninstalling StudioBridge assets."""

    def __init__(
        self,
        *,
        fl_dir: Path | None = None,
        user_data_dir: Path | None = None,
        app_data_dir: Path | None = None,
        device_name: str = DEFAULT_DEVICE_NAME,
        port_root: str = DEFAULT_DEVICE_NAME,
        build_id: str = __version__,
        auth_alg: str = "sha256",
        unsafe_device: bool = False,
    ) -> None:
        self.device_name = device_name
        self.port_root = port_root
        self.build_id = build_id
        self.auth_alg = auth_alg
        self.unsafe_device = unsafe_device

        self.app_data_dir = app_data_dir or get_app_data_dir()
        self.report_path = self.app_data_dir / DEFAULT_REPORT_FILENAME
        self.secret_path = self.app_data_dir / "secret"

        self._fl_dir = fl_dir
        self._user_data_dir = user_data_dir

    def resolve_user_data_dir(self) -> Path:
        """Resolve FL Studio user data directory."""
        if self._user_data_dir is not None:
            return self._user_data_dir
        found = find_fl_user_data_dir()
        if found is not None:
            return found
        return get_default_fl_user_data_dir()

    def resolve_hardware_dir(self) -> Path:
        """Resolve controller script destination directory."""
        user_data = self.resolve_user_data_dir()
        return get_fl_hardware_dir(user_data, self.device_name)

    def resolve_fl_install_dirs(self) -> list[Path]:
        """Discover installed FL Studio program directories."""
        if self._fl_dir is not None:
            return [self._fl_dir]
        return find_fl_install_dirs()

    def load_report(self) -> SetupReport | None:
        """Load existing setup report from disk if present."""
        if not self.report_path.exists():
            return None
        try:
            data = json.loads(self.report_path.read_text(encoding="utf-8"))
            return SetupReport(**data)
        except Exception as exc:
            logger.warning("corrupt_setup_report", f"Failed to load setup report: {exc}")
            return None

    def _resolve_secret(self, is_repair: bool, rotate_secret: bool) -> str:
        """Determine wire secret based on install mode."""
        if is_repair and not rotate_secret and self.secret_path.exists():
            try:
                existing = self.secret_path.read_text(encoding="utf-8").strip()
                if len(existing) >= 32:
                    return existing
            except OSError:
                pass
        return secrets.token_hex(32)

    @staticmethod
    def _compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def install(
        self,
        *,
        dry_run: bool = False,
        repair: bool = False,
        rotate_secret: bool = False,
    ) -> SetupReport:
        """Install or repair StudioBridge controller scripts and configuration.

        Adheres to:
        - [SET-01]: Modifies only user data directory and %LOCALAPPDATA%\\studiobridge\\.
        - [SET-02]: Records all files with SHA-256 in setup-report.json.
        - [UPG-01]: Retains wire secret during repairs unless rotate_secret is True.
        """
        user_data_dir = self.resolve_user_data_dir()
        hardware_dir = self.resolve_hardware_dir()
        secret = self._resolve_secret(repair, rotate_secret)

        generator = DeviceScriptGenerator(
            device_name=self.device_name,
            port_root=self.port_root,
            build_id=self.build_id,
            secret=secret,
            auth_alg=self.auth_alg,
            unsafe=1 if self.unsafe_device else 0,
        )

        now = datetime.now(timezone.utc).isoformat()
        action_name = "dry_run" if dry_run else ("repair" if repair else "install")

        # 1. Preview or generate files
        sibling_names = [
            "_sb_wire.py",
            "_sb_json.py",
            "_sb_auth.py",
            "_sb_core.py",
            "_sb_api.py",
        ]
        entry_name = f"device_{self.device_name}.py"

        file_records: list[dict[str, Any]] = []

        if dry_run:
            # Calculate what would be written
            for name in sibling_names:
                content = generator._read_asset(name).encode("utf-8")
                file_records.append(
                    {
                        "name": name,
                        "path": str(hardware_dir / name),
                        "sha256": self._compute_sha256(content),
                        "size": len(content),
                    }
                )

            entry_bytes = generator._render_entry_script().encode("utf-8")
            file_records.append(
                {
                    "name": entry_name,
                    "path": str(hardware_dir / entry_name),
                    "sha256": self._compute_sha256(entry_bytes),
                    "size": len(entry_bytes),
                }
            )

            return SetupReport(
                action=action_name,
                installed_at=now,
                build_id=self.build_id,
                device_name=self.device_name,
                port_root=self.port_root,
                hardware_dir=str(hardware_dir),
                user_data_dir=str(user_data_dir),
                secret_path=str(self.secret_path),
                files=file_records,
                success=True,
                dry_run=True,
                message=f"Dry run: {len(file_records)} files would be written to {hardware_dir}",
            )

        # 2. Perform actual write
        hardware_dir.mkdir(parents=True, exist_ok=True)
        self.app_data_dir.mkdir(parents=True, exist_ok=True)

        # Save secret securely
        self.secret_path.write_text(secret, encoding="utf-8")

        # Generate scripts
        written_files = generator.generate_multi_file(hardware_dir)
        for name, file_path in written_files.items():
            content_bytes = file_path.read_bytes()
            file_records.append(
                {
                    "name": name,
                    "path": str(file_path),
                    "sha256": self._compute_sha256(content_bytes),
                    "size": len(content_bytes),
                }
            )

        report = SetupReport(
            action=action_name,
            installed_at=now,
            build_id=self.build_id,
            device_name=self.device_name,
            port_root=self.port_root,
            hardware_dir=str(hardware_dir),
            user_data_dir=str(user_data_dir),
            secret_path=str(self.secret_path),
            files=file_records,
            success=True,
            dry_run=False,
            message=(
                f"Successfully {'repaired' if repair else 'installed'} {len(file_records)} files "
                f"in {hardware_dir}."
            ),
        )

        # Persist report to %LOCALAPPDATA%\\studiobridge\\setup-report.json [SET-02]
        self.report_path.write_text(report.to_json(), encoding="utf-8")
        return report

    def uninstall(
        self,
        *,
        dry_run: bool = False,
        force: bool = False,
        remove_secret: bool = True,
    ) -> SetupReport:
        """Uninstall StudioBridge controller scripts and clean up report [UPG-02].

        Removes only files listed in setup-report.json whose hashes still match disk
        (unless force is True).
        """
        user_data_dir = self.resolve_user_data_dir()
        hardware_dir = self.resolve_hardware_dir()
        existing_report = self.load_report()
        now = datetime.now(timezone.utc).isoformat()

        files_to_remove: list[tuple[Path, str]] = []
        if existing_report and existing_report.files:
            for item in existing_report.files:
                p = Path(item["path"])
                expected_sha = item.get("sha256", "")
                files_to_remove.append((p, expected_sha))
        else:
            # Fallback if no report exists: standard files
            if hardware_dir.exists():
                for p in hardware_dir.iterdir():
                    if p.is_file() and (p.name.startswith("_sb_") or p.name.startswith("device_")):
                        files_to_remove.append((p, ""))

        uninstalled_paths: list[str] = []
        skipped_paths: list[str] = []

        for p, expected_sha in files_to_remove:
            if not p.exists():
                continue
            if expected_sha and not force:
                try:
                    actual_sha = self._compute_sha256(p.read_bytes())
                    if actual_sha != expected_sha:
                        logger.warning(
                            "hash_mismatch_skip",
                            f"Skipping modified file during uninstall: {p}",
                        )
                        skipped_paths.append(str(p))
                        continue
                except OSError:
                    continue

            uninstalled_paths.append(str(p))
            if not dry_run:
                try:
                    p.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("unlink_error", f"Failed to remove {p}: {exc}")

        if not dry_run:
            # Try to remove hardware directory if empty
            if hardware_dir.exists():
                with contextlib.suppress(OSError):
                    hardware_dir.rmdir()

            if remove_secret:
                self.secret_path.unlink(missing_ok=True)

            self.report_path.unlink(missing_ok=True)

        return SetupReport(
            action="uninstall",
            installed_at=now,
            build_id=self.build_id,
            device_name=self.device_name,
            port_root=self.port_root,
            hardware_dir=str(hardware_dir),
            user_data_dir=str(user_data_dir),
            secret_path=str(self.secret_path),
            uninstalled_files=uninstalled_paths,
            success=True,
            dry_run=dry_run,
            message=(
                f"{'Dry run: would remove' if dry_run else 'Removed'} "
                f"{len(uninstalled_paths)} files."
                + (f" Skipped {len(skipped_paths)} modified files." if skipped_paths else "")
            ),
        )
