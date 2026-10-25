"""FL Studio installation and executable metadata discovery.

Discovers installed FL Studio versions and extracts PE version resource metadata
and host architecture execution modes (native x64 vs Windows ARM64 Prism emulation).
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import re
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studiobridge.core.errors import FlInstallNotFoundError
from studiobridge.core.paths import find_fl_install_dirs

IMAGE_FILE_MACHINE_UNKNOWN: int = 0x0000
IMAGE_FILE_MACHINE_I386: int = 0x014C
IMAGE_FILE_MACHINE_AMD64: int = 0x8664
IMAGE_FILE_MACHINE_ARM64: int = 0xAA64


class _VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD),
        ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD),
        ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD),
        ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD),
        ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD),
        ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD),
        ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


@dataclass(frozen=True, slots=True)
class FlInstall:
    """Represents a discovered FL Studio installation.

    Attributes:
        path: Root directory containing FL Studio.
        exe_path: Full path to FL64.exe (or FL.exe).
        version_str: Dot-separated version string (e.g. '26.1.3.5570').
        major: Major version number.
        minor: Minor version number.
        build: Build number.
        revision: Revision number.
        architecture: Binary architecture ('x64' or 'x86').
        is_emulated: True if running under Prism emulation on Windows ARM64.
        name: Name of installation directory or product title.
    """

    path: Path
    exe_path: Path
    version_str: str
    major: int
    minor: int
    build: int
    revision: int
    architecture: str = "x64"
    is_emulated: bool = False
    name: str = ""

    @property
    def display_name(self) -> str:
        """Human-readable display name including version and architecture."""
        base = self.name or self.path.name
        arch_info = (
            f"{self.architecture} (Prism emulated)" if self.is_emulated else self.architecture
        )
        return f"{base} ({self.version_str}) [{arch_info}]"

    def to_dict(self) -> dict[str, Any]:
        """Serialize install metadata to dictionary."""
        return {
            "path": str(self.path),
            "exe_path": str(self.exe_path),
            "version_str": self.version_str,
            "major": self.major,
            "minor": self.minor,
            "build": self.build,
            "revision": self.revision,
            "architecture": self.architecture,
            "is_emulated": self.is_emulated,
            "name": self.name,
            "display_name": self.display_name,
        }


class FlDiscovery:
    """Discovers installed FL Studio versions and extracts executable metadata."""

    def __init__(self, search_paths: list[Path] | None = None) -> None:
        self._custom_search_paths = search_paths

    @staticmethod
    def is_prism_emulated() -> bool:
        """Detect whether host OS is Windows ARM64 running x64 under Prism emulation.

        Uses IsWow64Process2 via kernel32 when available on Windows.
        """
        if sys.platform != "win32":
            return False

        # Check environment hint
        proc_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
        if proc_arch == "ARM64":
            return True

        # Query native machine via IsWow64Process2
        try:
            kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
            if hasattr(kernel32, "IsWow64Process2"):
                kernel32.IsWow64Process2.argtypes = [
                    wintypes.HANDLE,
                    ctypes.POINTER(wintypes.USHORT),
                    ctypes.POINTER(wintypes.USHORT),
                ]
                kernel32.IsWow64Process2.restype = wintypes.BOOL

                h_proc = kernel32.GetCurrentProcess()
                pm = wintypes.USHORT()
                nm = wintypes.USHORT()
                if (
                    kernel32.IsWow64Process2(h_proc, ctypes.byref(pm), ctypes.byref(nm))
                    and nm.value == IMAGE_FILE_MACHINE_ARM64
                ):
                    return True
        except Exception:
            pass

        return platform.machine().lower() in ("arm64", "aarch64")

    @classmethod
    def extract_pe_version(cls, exe_path: Path) -> tuple[int, int, int, int, str]:
        """Extract product version from Windows PE executable resource.

        Returns:
            Tuple of (major, minor, build, revision, version_string).
        """
        if sys.platform == "win32" and exe_path.exists():
            try:
                version_dll = ctypes.WinDLL("version.dll", use_last_error=True)
                version_dll.GetFileVersionInfoSizeW.argtypes = [
                    wintypes.LPCWSTR,
                    ctypes.POINTER(wintypes.DWORD),
                ]
                version_dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD

                version_dll.GetFileVersionInfoW.argtypes = [
                    wintypes.LPCWSTR,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.LPVOID,
                ]
                version_dll.GetFileVersionInfoW.restype = wintypes.BOOL

                version_dll.VerQueryValueW.argtypes = [
                    wintypes.LPCVOID,
                    wintypes.LPCWSTR,
                    ctypes.POINTER(wintypes.LPVOID),
                    ctypes.POINTER(wintypes.UINT),
                ]
                version_dll.VerQueryValueW.restype = wintypes.BOOL

                dummy = wintypes.DWORD()
                size = version_dll.GetFileVersionInfoSizeW(str(exe_path), ctypes.byref(dummy))
                if size > 0:
                    buf = ctypes.create_string_buffer(size)
                    if version_dll.GetFileVersionInfoW(str(exe_path), 0, size, buf):
                        lplp_buffer = wintypes.LPVOID()
                        pu_len = wintypes.UINT()
                        if (
                            version_dll.VerQueryValueW(
                                buf,
                                "\\",
                                ctypes.byref(lplp_buffer),
                                ctypes.byref(pu_len),
                            )
                            and lplp_buffer.value
                        ):
                            info = _VS_FIXEDFILEINFO.from_address(lplp_buffer.value)
                            major = (info.dwProductVersionMS >> 16) & 0xFFFF
                            minor = info.dwProductVersionMS & 0xFFFF
                            build = (info.dwProductVersionLS >> 16) & 0xFFFF
                            rev = info.dwProductVersionLS & 0xFFFF
                            ver_str = f"{major}.{minor}.{build}.{rev}"
                            return (major, minor, build, rev, ver_str)
            except Exception:
                pass

        # Fallback: inspect directory name or path for version hints
        # (e.g. 'FL Studio 2026', 'FL Studio 21')
        folder_name = exe_path.parent.name
        match = re.search(r"(\d+)(?:\.(\d+))?", folder_name)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2)) if match.group(2) else 0
            return (major, minor, 0, 0, f"{major}.{minor}.0.0")

        return (24, 0, 0, 0, "24.0.0.0")

    def inspect_install(self, path: Path) -> FlInstall:
        """Inspect an FL Studio directory and construct an FlInstall instance."""
        p = Path(path).resolve()
        exe_64 = p / "FL64.exe"
        exe_32 = p / "FL.exe"

        if exe_64.exists():
            exe_path = exe_64
            arch = "x64"
        elif exe_32.exists():
            exe_path = exe_32
            arch = "x86"
        else:
            # Check if path itself is an executable
            if p.is_file() and p.name.lower() in ("fl64.exe", "fl.exe"):
                exe_path = p
                p = p.parent
                arch = "x64" if "64" in exe_path.name else "x86"
            else:
                exe_path = exe_64
                arch = "x64"

        major, minor, build, rev, ver_str = self.extract_pe_version(exe_path)
        is_emulated = self.is_prism_emulated() if arch == "x64" else False

        return FlInstall(
            path=p,
            exe_path=exe_path,
            version_str=ver_str,
            major=major,
            minor=minor,
            build=build,
            revision=rev,
            architecture=arch,
            is_emulated=is_emulated,
            name=p.name,
        )

    def find_installs(self) -> list[FlInstall]:
        """Discover all available FL Studio installations.

        Returns installations sorted descending by version (newest first).
        """
        paths: list[Path] = []
        if self._custom_search_paths is not None:
            paths.extend(self._custom_search_paths)
        else:
            paths.extend(find_fl_install_dirs())

        # Deduplicate paths
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for p in paths:
            norm = str(p.resolve()).lower()
            if norm not in seen:
                seen.add(norm)
                unique_paths.append(p)

        installs: list[FlInstall] = []
        for p in unique_paths:
            with contextlib.suppress(Exception):
                installs.append(self.inspect_install(p))

        # Sort descending by version tuple
        installs.sort(key=lambda i: (i.major, i.minor, i.build, i.revision), reverse=True)
        return installs

    def get_default_install(self, preferred_path: Path | str | None = None) -> FlInstall | None:
        """Resolve the default or preferred FL Studio installation.

        Returns None if no installation can be found.
        """
        if preferred_path:
            p = Path(preferred_path)
            if p.exists():
                return self.inspect_install(p)

        installs = self.find_installs()
        return installs[0] if installs else None

    def resolve_install(self, preferred_path: Path | str | None = None) -> FlInstall:
        """Resolve an FL Studio installation or raise FlInstallNotFoundError."""
        inst = self.get_default_install(preferred_path)
        if inst is None or (not inst.exe_path.exists() and not inst.path.exists()):
            msg = (
                f"No FL Studio installation found at '{preferred_path}'"
                if preferred_path
                else "No FL Studio installation (FL64.exe) found in standard locations"
            )
            raise FlInstallNotFoundError(msg, code="E_RND_NO_INSTALL")
        return inst
