"""Device script generator producing FL Studio controller scripts per [DEV-01]..[DEV-03].

Supports both multi-file directory layout and single-file inlined script generation.
"""

from __future__ import annotations

import pathlib
import secrets
from typing import Any

# Path to template assets directory
ASSETS_DIR = pathlib.Path(__file__).parent / "assets"


class DeviceScriptGenerator:
    """Generates FL Studio controller scripts in multi-file or single-file inlined format."""

    def __init__(
        self,
        device_name: str = "StudioBridge",
        port_root: str = "StudioBridge",
        build_id: str = "1.0.0",
        secret: str = "",
        auth_alg: str = "sha256",
        max_frame: int = 512,
        budget_ms: int = 15,
        budget_calls: int = 150,
        unsafe: int = 0,
        assets_dir: pathlib.Path | str | None = None,
    ) -> None:
        self.device_name = device_name
        self.port_root = port_root
        self.build_id = build_id
        self.secret = secret if secret else secrets.token_hex(32)
        self.auth_alg = auth_alg
        self.max_frame = int(max_frame)
        self.budget_ms = int(budget_ms)
        self.budget_calls = int(budget_calls)
        self.unsafe = int(unsafe)
        self.assets_dir = pathlib.Path(assets_dir) if assets_dir else ASSETS_DIR

    def _read_asset(self, filename: str) -> str:
        """Read asset file content."""
        asset_path = self.assets_dir / filename
        if not asset_path.exists():
            raise FileNotFoundError(f"Device script asset '{filename}' not found at {asset_path}")
        return asset_path.read_text(encoding="utf-8")

    def _render_entry_script(self) -> str:
        """Render device entry script with injected parameters."""
        raw = self._read_asset("device_entry.py")
        rendered = raw.replace("{DEVICE}", self.device_name)
        rendered = rendered.replace("{PORT_ROOT}", self.port_root)
        rendered = rendered.replace("{DIST}", "studiobridge")

        # Replace default injected parameter values
        replacements: dict[str, Any] = {
            'BUILD_ID = "1.0.0"': f'BUILD_ID = "{self.build_id}"',
            'SECRET = ""': f'SECRET = "{self.secret}"',
            'AUTH_ALG = "sha256"': f'AUTH_ALG = "{self.auth_alg}"',
            'PORT_ROOT = "StudioBridge"': f'PORT_ROOT = "{self.port_root}"',
            "MAX_FRAME = 512": f"MAX_FRAME = {self.max_frame}",
            "BUDGET_MS = 15": f"BUDGET_MS = {self.budget_ms}",
            "BUDGET_CALLS = 150": f"BUDGET_CALLS = {self.budget_calls}",
            "UNSAFE = 0": f"UNSAFE = {self.unsafe}",
        }
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)

        return rendered

    def generate_multi_file(self, target_dir: pathlib.Path | str) -> dict[str, pathlib.Path]:
        """Generate multi-file modular script bundle in target directory.

        Creates:
          target_dir/device_{device_name}.py
          target_dir/_sb_wire.py
          target_dir/_sb_json.py
          target_dir/_sb_auth.py
          target_dir/_sb_core.py
          target_dir/_sb_api.py

        Returns:
            Dict mapping filename to written Path.
        """
        dest_dir = pathlib.Path(target_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        created_files: dict[str, pathlib.Path] = {}

        # 1. Write sibling modules verbatim
        sibling_names = [
            "_sb_wire.py",
            "_sb_json.py",
            "_sb_auth.py",
            "_sb_core.py",
            "_sb_api.py",
        ]
        for name in sibling_names:
            content = self._read_asset(name)
            out_file = dest_dir / name
            out_file.write_text(content, encoding="utf-8")
            created_files[name] = out_file

        # 2. Write entry script
        entry_name = f"device_{self.device_name}.py"
        entry_content = self._render_entry_script()
        entry_file = dest_dir / entry_name
        entry_file.write_text(entry_content, encoding="utf-8")
        created_files[entry_name] = entry_file

        return created_files

    def get_inlined_code(self) -> str:
        """Generate single-file inlined script string per [DEV-01].

        Concatenates all modules and entry handlers into a single self-contained script.
        """
        wire_code = self._read_asset("_sb_wire.py")
        json_code = self._read_asset("_sb_json.py")
        auth_code = self._read_asset("_sb_auth.py")
        api_code = self._read_asset("_sb_api.py")
        core_code = self._read_asset("_sb_core.py")
        entry_code = self._render_entry_script()

        # Build single-file script
        parts: list[str] = [
            f"# name={self.device_name}",
            "# url=https://example.invalid/studiobridge",
            f"# supportedDevices={self.port_root} (A)",
            "",
            '"""FL Studio controller script (Single-file inlined build).',
            "",
            "Generated by StudioBridge DeviceScriptGenerator.",
            "Conforms strictly to Python 3.9 embedded environment.",
            '"""',
            "",
            "import collections",
            "import contextlib",
            "import struct",
            "import sys",
            "import time",
            "",
            "# Injected parameters",
            f'BUILD_ID = "{self.build_id}"',
            f'SECRET = "{self.secret}"',
            f'AUTH_ALG = "{self.auth_alg}"',
            f'PORT_ROOT = "{self.port_root}"',
            f"MAX_FRAME = {self.max_frame}",
            f"BUDGET_MS = {self.budget_ms}",
            f"BUDGET_CALLS = {self.budget_calls}",
            f"UNSAFE = {self.unsafe}",
            "",
            "# Module aliases for inlined execution",
            "class _GlobalNamespace:",
            "    def __getattr__(self, name):",
            "        if name in globals():",
            "            return globals()[name]",
            "        raise AttributeError(name)",
            "",
            "_mod = sys.modules.get(__name__) or _GlobalNamespace()",
            "wire = _mod",
            "json_codec = _mod",
            "auth = _mod",
            "api = _mod",
            "core = _mod",
            "",
            "# --- BEGIN _sb_wire.py ---",
            wire_code,
            "# --- END _sb_wire.py ---",
            "",
            "# --- BEGIN _sb_json.py ---",
            json_code,
            "# --- END _sb_json.py ---",
            "",
            "# --- BEGIN _sb_auth.py ---",
            auth_code,
            "# --- END _sb_auth.py ---",
            "",
            "# --- BEGIN _sb_api.py ---",
            api_code,
            "# --- END _sb_api.py ---",
            "",
            "# --- BEGIN _sb_core.py ---",
            core_code,
            "# --- END _sb_core.py ---",
            "",
            "# --- BEGIN device_entry.py handlers ---",
            entry_code,
            "# --- END device_entry.py handlers ---",
        ]

        return "\n".join(parts)

    def generate_single_file(self, target_file: pathlib.Path | str) -> pathlib.Path:
        """Generate single-file inlined script and write to target path."""
        out_path = pathlib.Path(target_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        inlined_code = self.get_inlined_code()
        out_path.write_text(inlined_code, encoding="utf-8")
        return out_path
