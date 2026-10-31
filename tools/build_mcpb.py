"""Claude Desktop MCPB bundle builder for StudioBridge.

Packages the MCPB manifest, assets, launcher wrapper, and integrity checksums
into a standard .mcpb archive for one-click installation into Claude Desktop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[1] / "mcpb"
_DEFAULT_DIST_DIR = Path(__file__).resolve().parents[1] / "dist"


def generate_icon(output_path: Path, size: int = 256) -> Path:
    """Generate the official StudioBridge icon asset as a valid PNG image."""
    width = size
    height = size
    raw = bytearray()
    center = (size - 1) / 2.0
    scale = size / 256.0

    r_corner = 36.0 * scale
    r_box = 120.0 * scale
    circle_radius = 52.0 * scale
    line_thickness = 9.0 * scale
    left_line_x = (-85.0 * scale, -35.0 * scale)
    right_line_x = (35.0 * scale, 85.0 * scale)

    for y in range(height):
        raw.append(0)  # Filter type 0 (None)
        py = y - center
        for x in range(width):
            px = x - center
            dx = max(abs(px) - (r_box - r_corner), 0.0)
            dy = max(abs(py) - (r_box - r_corner), 0.0)
            d_box = math.sqrt(dx * dx + dy * dy)

            if d_box > r_corner:
                raw.extend([0, 0, 0, 0])
                continue

            box_alpha = 1.0
            if d_box > r_corner - 1.0:
                box_alpha = max(0.0, min(1.0, r_corner - d_box))

            dist_c = math.sqrt(px * px + py * py)
            is_line = False
            for lx0, lx1 in [left_line_x, right_line_x]:
                ldx = max(lx0 - px, px - lx1, 0.0)
                ldy = abs(py)
                if math.sqrt(ldx * ldx + ldy * ldy) <= line_thickness:
                    is_line = True
                    break

            if dist_c <= circle_radius:
                a = int(255 * box_alpha)
                raw.extend([232, 70, 26, a])
            elif is_line:
                a = int(255 * box_alpha)
                raw.extend([243, 240, 232, a])
            else:
                a = int(255 * box_alpha)
                raw.extend([24, 24, 21, a])

    compressed = zlib.compress(bytes(raw), level=9)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    png_data = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_data)
    return output_path


def validate_manifest(manifest_data: dict[str, Any]) -> list[str]:
    """Validate manifest data against MCPB bundle specification."""
    errors: list[str] = []

    required_keys = (
        "manifest_version",
        "name",
        "display_name",
        "version",
        "description",
        "author",
        "icon",
        "server",
        "compatibility",
        "capabilities",
    )
    for key in required_keys:
        if key not in manifest_data:
            errors.append(f"Missing required manifest key: '{key}'")

    name = manifest_data.get("name", "")
    if not isinstance(name, str) or not name:
        errors.append("Field 'name' must be a non-empty string.")

    server = manifest_data.get("server")
    if not isinstance(server, dict):
        errors.append("Field 'server' must be an object.")
    else:
        for s_key in ("type", "entry_point", "mcp_config"):
            if s_key not in server:
                errors.append(f"Field 'server' missing required key: '{s_key}'")

    compat = manifest_data.get("compatibility")
    if not isinstance(compat, dict):
        errors.append("Field 'compatibility' must be an object.")
    else:
        if "platforms" not in compat or not isinstance(compat["platforms"], list):
            errors.append("Field 'compatibility.platforms' must be a list.")
        if "runtimes" not in compat or not isinstance(compat["runtimes"], dict):
            errors.append("Field 'compatibility.runtimes' must be an object.")

    tools = manifest_data.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            errors.append("Field 'tools' must be a list of tool definitions.")
        else:
            for idx, tool in enumerate(tools):
                if not isinstance(tool, dict):
                    errors.append(f"Tool at index {idx} must be an object.")
                    continue
                if "name" not in tool or not tool["name"]:
                    errors.append(f"Tool at index {idx} missing 'name'.")
                if "description" not in tool:
                    errors.append(f"Tool at index {idx} missing 'description'.")
                if "input_schema" not in tool and "inputSchema" not in tool:
                    errors.append(f"Tool at index {idx} missing input schema.")

    return errors


def validate_icon(icon_bytes: bytes) -> list[str]:
    """Validate that the provided bytes constitute a valid PNG image asset."""
    errors: list[str] = []
    if len(icon_bytes) < 33:
        return ["Icon file is too small to be a valid PNG."]

    if not icon_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append("Icon does not start with standard PNG signature.")
        return errors

    try:
        length, tag = struct.unpack(">I4s", icon_bytes[8:16])
        if tag != b"IHDR" or length != 13:
            errors.append("First chunk in icon is not valid IHDR.")
            return errors
        w, h, bit_depth, color_type = struct.unpack(">IIBB", icon_bytes[16:26])
        if w < 128 or h < 128:
            errors.append(f"Icon dimensions ({w}x{h}) smaller than required minimum 128x128.")
        if bit_depth != 8:
            errors.append(f"Unexpected PNG bit depth: {bit_depth}")
        if color_type not in (2, 6):  # RGB or RGBA
            errors.append(f"Unexpected PNG color type: {color_type}")
    except struct.error as exc:
        errors.append(f"Corrupt PNG IHDR chunk: {exc}")

    return errors


def validate_launcher(code_text: str) -> list[str]:
    """Validate that the launcher wrapper is syntactically valid Python code."""
    errors: list[str] = []
    try:
        compile(code_text, "launcher.py", "exec")
    except SyntaxError as exc:
        errors.append(f"Launcher syntax error: {exc}")
    return errors


def refresh_tools_in_manifest(manifest_path: Path) -> int:
    """Query StudioMcpServer for registered tools and update manifest.json."""
    from studiobridge.mcp.server import VALID_TOOLSETS, StudioMcpServer

    server = StudioMcpServer(toolsets=VALID_TOOLSETS)
    tools_list: list[dict[str, Any]] = []
    for _name, tool in sorted(server._tools.items()):
        tools_list.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
        )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tools"] = tools_list
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return len(tools_list)


def build_mcpb(
    source_dir: Path | str = _DEFAULT_SOURCE_DIR,
    output_path: Path | str | None = None,
    update_tools: bool = False,
) -> Path:
    """Package an MCPB source directory into a verified .mcpb archive.

    Args:
        source_dir: Path to directory containing manifest.json, icon.png, and launcher.py.
        output_path: Path for output archive. If None, writes to dist/<name>-<version>.mcpb.
        update_tools: If True, regenerates the tools metadata from the server prior to packaging.

    Returns:
        Path to the generated .mcpb archive.

    Raises:
        FileNotFoundError: If required source files are missing.
        ValueError: If manifest, icon, or launcher validation fails.
    """
    src = Path(source_dir).resolve()
    manifest_file = src / "manifest.json"
    icon_file = src / "icon.png"
    launcher_file = src / "launcher.py"

    if not manifest_file.is_file():
        raise FileNotFoundError(f"Missing required manifest file: {manifest_file}")

    if update_tools:
        refresh_tools_in_manifest(manifest_file)

    if not icon_file.is_file():
        generate_icon(icon_file, size=256)

    if not launcher_file.is_file():
        raise FileNotFoundError(f"Missing required launcher file: {launcher_file}")

    # Read and validate components
    manifest_raw = manifest_file.read_bytes()
    try:
        manifest_data = json.loads(manifest_raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in manifest: {exc}") from exc

    manifest_errors = validate_manifest(manifest_data)
    if manifest_errors:
        raise ValueError(f"Manifest validation failed: {'; '.join(manifest_errors)}")

    icon_bytes = icon_file.read_bytes()
    icon_errors = validate_icon(icon_bytes)
    if icon_errors:
        raise ValueError(f"Icon asset validation failed: {'; '.join(icon_errors)}")

    launcher_text = launcher_file.read_text(encoding="utf-8")
    launcher_errors = validate_launcher(launcher_text)
    if launcher_errors:
        raise ValueError(f"Launcher validation failed: {'; '.join(launcher_errors)}")

    # Resolve output path
    if output_path is None:
        name = manifest_data.get("name", "studiobridge").split(".")[-1]
        version = manifest_data.get("version", "1.0.0")
        out_file = _DEFAULT_DIST_DIR / f"{name}-{version}.mcpb"
    else:
        out_file = Path(output_path).resolve()

    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Compute checksums
    files_to_pack: dict[str, bytes] = {
        "manifest.json": manifest_raw,
        "icon.png": icon_bytes,
        "launcher.py": launcher_text.encode("utf-8"),
    }
    checksums: dict[str, str] = {
        fname: hashlib.sha256(content).hexdigest() for fname, content in files_to_pack.items()
    }
    integrity_manifest = {
        "algorithm": "sha256",
        "bundle": manifest_data.get("name", ""),
        "version": manifest_data.get("version", ""),
        "files": checksums,
    }
    checksums_raw = json.dumps(integrity_manifest, indent=2).encode("utf-8")
    files_to_pack["checksums.json"] = checksums_raw

    # Build zip archive with standardized attributes
    with zipfile.ZipFile(out_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        fixed_time = (2026, 1, 1, 0, 0, 0)
        for fname, content in sorted(files_to_pack.items()):
            zinfo = zipfile.ZipInfo(filename=fname, date_time=fixed_time)
            # 0o755 for launcher, 0o644 for others
            perms = 0o755 if fname.endswith(".py") else 0o644
            zinfo.external_attr = perms << 16
            zf.writestr(zinfo, content)

    # Self-verify the produced bundle
    is_valid, verify_errors = verify_mcpb(out_file)
    if not is_valid:
        raise ValueError(f"Built archive failed verification: {'; '.join(verify_errors)}")

    return out_file


def verify_mcpb(archive_path: Path | str) -> tuple[bool, list[str]]:
    """Verify integrity, structure, schema, and assets of an .mcpb archive.

    Returns:
        A tuple of (is_valid, list_of_error_messages).
    """
    path = Path(archive_path).resolve()
    errors: list[str] = []

    if not path.is_file():
        return False, [f"Archive file does not exist: {path}"]

    if not zipfile.is_zipfile(path):
        return False, [f"File is not a valid zip archive: {path}"]

    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            required_members = {"manifest.json", "icon.png", "launcher.py", "checksums.json"}
            missing = required_members - set(namelist)
            if missing:
                errors.append(f"Archive missing required files: {', '.join(sorted(missing))}")
                return False, errors

            # Verify checksums
            try:
                checksums_raw = zf.read("checksums.json").decode("utf-8")
                checksums_data = json.loads(checksums_raw)
                expected_files = checksums_data.get("files", {})
                for fname, expected_hash in expected_files.items():
                    if fname not in namelist:
                        errors.append(f"Checksum manifest references missing file: {fname}")
                        continue
                    actual_content = zf.read(fname)
                    actual_hash = hashlib.sha256(actual_content).hexdigest()
                    if actual_hash != expected_hash:
                        errors.append(
                            f"Checksum mismatch for '{fname}': "
                            f"expected {expected_hash}, got {actual_hash}"
                        )
            except Exception as exc:
                errors.append(f"Invalid checksums manifest: {exc}")

            # Verify manifest
            try:
                manifest_raw = zf.read("manifest.json").decode("utf-8")
                manifest_data = json.loads(manifest_raw)
                errors.extend(validate_manifest(manifest_data))
            except Exception as exc:
                errors.append(f"Invalid manifest.json in archive: {exc}")

            # Verify icon
            try:
                icon_bytes = zf.read("icon.png")
                errors.extend(validate_icon(icon_bytes))
            except Exception as exc:
                errors.append(f"Invalid icon.png in archive: {exc}")

            # Verify launcher
            try:
                launcher_text = zf.read("launcher.py").decode("utf-8")
                errors.extend(validate_launcher(launcher_text))
            except Exception as exc:
                errors.append(f"Invalid launcher.py in archive: {exc}")

            # Verify permissions
            for info in zf.infolist():
                mode = info.external_attr >> 16
                if info.filename.endswith(".py") and mode != 0 and not (mode & 0o111):
                    errors.append(
                        f"File '{info.filename}' missing executable permissions: {oct(mode)}"
                    )

    except Exception as exc:
        errors.append(f"Failed opening archive: {exc}")

    return len(errors) == 0, errors


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the MCPB builder tool."""
    parser = argparse.ArgumentParser(
        prog="build_mcpb",
        description="StudioBridge Claude Desktop MCPB bundle builder and verifier.",
    )
    parser.add_argument(
        "-s",
        "--source-dir",
        type=Path,
        default=_DEFAULT_SOURCE_DIR,
        help="Path to source directory containing manifest.json and assets (default: mcpb/).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination path for .mcpb bundle (default: dist/<name>-<version>.mcpb).",
    )
    parser.add_argument(
        "--verify",
        type=Path,
        nargs="?",
        const=Path(""),
        default=None,
        help="Verify an existing .mcpb bundle archive instead of building.",
    )
    parser.add_argument(
        "--update-tools",
        action="store_true",
        help="Refresh tool discovery metadata in manifest.json from StudioMcpServer.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for building or verifying .mcpb bundles."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verify is not None:
        target = args.verify if str(args.verify) else args.output
        if not target:
            target = args.source_dir.parent / "dist" / "studiobridge-1.0.0.mcpb"
        is_valid, errors = verify_mcpb(target)
        if not is_valid:
            print(f"[FAIL] Bundle verification failed for '{target}':", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"[OK] Bundle verified successfully: {target}")
        return 0

    try:
        archive_path = build_mcpb(
            source_dir=args.source_dir,
            output_path=args.output,
            update_tools=args.update_tools,
        )
        if not args.quiet:
            print(f"[OK] MCPB bundle packaged successfully: {archive_path}")
        return 0
    except Exception as exc:
        print(f"[FAIL] Failed building MCPB bundle: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
