"""Claude Desktop MCPB bundle packaging and verification tests.

Covers:
- MCPB manifest schema and metadata validation (# req: DIST-04)
- StudioBridge icon asset dimensions and PNG validity (# req: DIST-04)
- Launcher wrapper script stdio discipline and execution (# req: DIST-04)
- Bundle builder archive structure, permissions, and checksum integrity (# req: DIST-04)
- Claude Desktop tool discovery and smoke lifecycle (# req: DIST-04)
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from studiobridge._version import __version__
from studiobridge.mcp.server import VALID_TOOLSETS, StudioMcpServer
from tools.build_mcpb import (
    build_mcpb,
    generate_icon,
    validate_icon,
    validate_launcher,
    validate_manifest,
    verify_mcpb,
)
from tools.build_mcpb import (
    main as build_mcpb_main,
)

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
_MCPB_DIR = _WORKSPACE_ROOT / "mcpb"


# req: DIST-04
def test_manifest_schema() -> None:
    """Verify mcpb/manifest.json matches MCPB specification requirements."""
    manifest_path = _MCPB_DIR / "manifest.json"
    assert manifest_path.is_file(), f"Manifest file missing: {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_manifest(data)
    assert not errors, f"Manifest validation errors: {errors}"

    # Specific metadata assertions
    assert data["manifest_version"] == "0.4"
    assert data["name"] == "io.github.wantedchip.studiobridge"
    assert data["display_name"] == "StudioBridge"
    assert data["version"] == __version__
    assert data["author"]["name"] == "WantedChip"
    assert "FL Studio" in data["description"]
    assert data["license"] == "MIT"
    assert data["icon"] == "icon.png"

    # Server configuration
    server = data["server"]
    assert server["type"] == "python"
    assert server["entry_point"] == "launcher.py"
    assert server["mcp_config"]["command"] == "python"
    assert "${__dirname}/launcher.py" in server["mcp_config"]["args"]

    # Platform compatibility
    compat = data["compatibility"]
    assert "win32" in compat["platforms"]
    assert compat["runtimes"]["python"] == ">=3.10,<3.15"

    # Capabilities
    caps = data["capabilities"]
    assert caps["tools"]["listChanged"] is True
    assert caps["prompts"]["listChanged"] is True
    assert "logging" in caps

    # User configuration schema
    user_config = data["user_config"]
    assert "toolsets" in user_config
    assert "mode" in user_config
    assert user_config["mode"]["default"] == "read_only"
    assert "read_only" in user_config["mode"]["enum"]


# req: DIST-04
def test_validate_manifest_error_paths() -> None:
    """Verify validate_manifest catches missing keys and bad field types."""
    # Missing required key
    errs = validate_manifest({"manifest_version": "0.4"})
    assert any("Missing required manifest key" in e for e in errs)

    # Bad server format
    bad_server = {
        "manifest_version": "0.4",
        "name": "test",
        "display_name": "Test",
        "version": "1.0.0",
        "description": "desc",
        "author": "me",
        "icon": "icon.png",
        "server": "not-a-dict",
        "compatibility": {"platforms": ["win32"], "runtimes": {}},
        "capabilities": {},
    }
    errs = validate_manifest(bad_server)
    assert any("Field 'server' must be an object" in e for e in errs)

    # Bad compatibility platforms format
    bad_compat = {
        "manifest_version": "0.4",
        "name": "test",
        "display_name": "Test",
        "version": "1.0.0",
        "description": "desc",
        "author": "me",
        "icon": "icon.png",
        "server": {"type": "python", "entry_point": "a", "mcp_config": {}},
        "compatibility": {"platforms": "win32", "runtimes": {}},
        "capabilities": {},
    }
    errs = validate_manifest(bad_compat)
    assert any("Field 'compatibility.platforms' must be a list" in e for e in errs)


# req: DIST-04
def test_icon_asset() -> None:
    """Verify mcpb/icon.png is a valid PNG image of sufficient resolution."""
    icon_path = _MCPB_DIR / "icon.png"
    assert icon_path.is_file(), f"Icon asset missing: {icon_path}"

    icon_bytes = icon_path.read_bytes()
    errors = validate_icon(icon_bytes)
    assert not errors, f"Icon validation errors: {errors}"

    # Verify PNG magic signature
    assert icon_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    # Verify IHDR chunk details
    w, h, bit_depth, color_type = struct.unpack(">IIBB", icon_bytes[16:26])
    assert w >= 128 and h >= 128, f"Icon resolution too small: {w}x{h}"
    assert bit_depth == 8
    assert color_type in (2, 6)


# req: DIST-04
def test_validate_icon_error_paths(tmp_path: Path) -> None:
    """Verify validate_icon rejects malformed or undersized PNG assets."""
    # Too small
    assert any("too small" in e for e in validate_icon(b"short"))

    # Not a PNG
    assert any("standard PNG signature" in e for e in validate_icon(b"A" * 50))

    # Generated small icon (e.g. 64x64)
    small_icon = tmp_path / "small.png"
    generate_icon(small_icon, size=64)
    errs = validate_icon(small_icon.read_bytes())
    assert any("smaller than required minimum 128x128" in e for e in errs)


# req: DIST-04
def test_launcher_script_syntax_and_import() -> None:
    """Verify mcpb/launcher.py is syntactically valid and handles argument mapping."""
    launcher_path = _MCPB_DIR / "launcher.py"
    assert launcher_path.is_file(), f"Launcher file missing: {launcher_path}"

    code = launcher_path.read_text(encoding="utf-8")
    errors = validate_launcher(code)
    assert not errors, f"Launcher syntax errors: {errors}"

    # Test error path with bad python syntax
    bad_errors = validate_launcher("def invalid(syntax: : :")
    assert any("syntax error" in e.lower() for e in bad_errors)


# req: DIST-04
def test_launcher_stdio_discipline(tmp_path: Path) -> None:
    """Verify launcher forwards commands cleanly without corrupting stdout."""
    launcher_path = _MCPB_DIR / "launcher.py"

    # Test with SBRIDGE_PY_CMD override
    env = os.environ.copy()
    env["SBRIDGE_PY_CMD"] = (
        f'{sys.executable} -c "import sys, json; sys.stdout.write(json.dumps(sys.argv[1:]))"'
    )

    res = subprocess.run(
        [sys.executable, str(launcher_path), "--check"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    # stdout should contain pure JSON array with normalized ['mcp', '--check']
    assert res.stdout.strip() == '["mcp", "--check"]'


# req: DIST-04
def test_build_mcpb_creates_archive(tmp_path: Path) -> None:
    """Verify build_mcpb packages the source directory into a valid .mcpb archive."""
    out_archive = tmp_path / "test-studiobridge.mcpb"
    result_path = build_mcpb(source_dir=_MCPB_DIR, output_path=out_archive)

    assert result_path == out_archive
    assert out_archive.is_file()
    assert zipfile.is_zipfile(out_archive)
    assert out_archive.stat().st_size > 0


# req: DIST-04
def test_mcpb_archive_structure_and_permissions(tmp_path: Path) -> None:
    """Verify archive contains required components with correct permissions."""
    out_archive = tmp_path / "test-structure.mcpb"
    build_mcpb(source_dir=_MCPB_DIR, output_path=out_archive)

    with zipfile.ZipFile(out_archive, "r") as zf:
        members = zf.namelist()
        assert "manifest.json" in members
        assert "icon.png" in members
        assert "launcher.py" in members
        assert "checksums.json" in members

        # Check permission attributes
        for info in zf.infolist():
            mode = info.external_attr >> 16
            if info.filename.endswith(".py"):
                # Launcher must have executable bits
                assert (mode & 0o111) != 0, f"Expected executable bits on {info.filename}"
            else:
                # Regular files must have read bits
                assert (mode & 0o444) != 0, f"Expected read bits on {info.filename}"


# req: DIST-04
def test_mcpb_integrity_checksums(tmp_path: Path) -> None:
    """Verify checksums.json matches actual contents and detects corruption."""
    out_archive = tmp_path / "test-integrity.mcpb"
    build_mcpb(source_dir=_MCPB_DIR, output_path=out_archive)

    # Valid archive passes verification
    is_valid, errors = verify_mcpb(out_archive)
    assert is_valid
    assert not errors

    # Tamper with archive contents
    tampered_archive = tmp_path / "tampered.mcpb"
    with (
        zipfile.ZipFile(out_archive, "r") as zf_in,
        zipfile.ZipFile(tampered_archive, "w") as zf_out,
    ):
        for item in zf_in.infolist():
            content = zf_in.read(item.filename)
            if item.filename == "launcher.py":
                # Alter launcher content to invalidate checksum
                content = content + b"\n# tampered"
            zf_out.writestr(item, content)

    # Verification must fail on tampered archive
    is_valid_tamp, errors_tamp = verify_mcpb(tampered_archive)
    assert not is_valid_tamp
    assert any("Checksum mismatch" in e for e in errors_tamp)


# req: DIST-04
def test_mcpb_verify_cli(tmp_path: Path) -> None:
    """Verify build_mcpb CLI --verify argument behavior."""
    out_archive = tmp_path / "cli-test.mcpb"
    build_mcpb(source_dir=_MCPB_DIR, output_path=out_archive)

    # CLI verification success
    code = build_mcpb_main(["--verify", str(out_archive), "--quiet"])
    assert code == 0

    # CLI verification non-existent file
    non_existent = tmp_path / "does-not-exist.mcpb"
    err_code = build_mcpb_main(["--verify", str(non_existent), "--quiet"])
    assert err_code != 0


# req: DIST-04
def test_tool_discovery_metadata() -> None:
    """Verify manifest.json contains complete tool discovery metadata matching server."""
    manifest_path = _MCPB_DIR / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_tools = {t["name"]: t for t in data.get("tools", [])}

    # Query live server for all registered tools
    server = StudioMcpServer(toolsets=VALID_TOOLSETS)
    server_tools = server._tools

    # All registered tools must be represented in the manifest
    assert len(manifest_tools) == len(server_tools)
    for name, tool_def in server_tools.items():
        assert name in manifest_tools, f"Tool '{name}' missing from manifest tools metadata"
        m_tool = manifest_tools[name]
        assert m_tool["description"] == tool_def.description
        assert "input_schema" in m_tool
        assert m_tool["input_schema"]["type"] == "object"


# req: DIST-04
def test_claude_desktop_bundle_smoke(tmp_path: Path) -> None:
    """Simulate Claude Desktop extension installation and execution lifecycle."""
    # 1. Package bundle
    bundle_path = tmp_path / "studiobridge-smoke.mcpb"
    build_mcpb(source_dir=_MCPB_DIR, output_path=bundle_path)

    # 2. Simulate Claude Desktop unpacking the bundle into an extension directory
    install_dir = tmp_path / "installed_ext"
    install_dir.mkdir()
    with zipfile.ZipFile(bundle_path, "r") as zf:
        zf.extractall(install_dir)

    # 3. Read manifest from install location
    manifest = json.loads((install_dir / "manifest.json").read_text(encoding="utf-8"))
    entry_point = manifest["server"]["entry_point"]
    launcher_script = install_dir / entry_point
    assert launcher_script.is_file()

    # 4. Execute launcher with --check
    res = subprocess.run(
        [sys.executable, str(launcher_script), "mcp", "--check"],
        cwd=str(_WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "MCP check passed" in res.stdout or "MCP check passed" in res.stderr
