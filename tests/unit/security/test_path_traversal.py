"""Path traversal and containment defense unit tests.

Verifies rejection of directory traversal attacks, UNC network paths, embedded
null bytes, URL-encoded path sequences, and directory escapes across core path
validation, MCP tool providers, offline FLP operations, and CLI handlers.

# req: SEC-04
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from studiobridge.cli.commands.flp import (
    _handle_diff,
    _handle_edit,
    _handle_inspect,
    _handle_validate,
)
from studiobridge.cli.commands.flp_template import _handle_new
from studiobridge.core.errors import SecurityError
from studiobridge.core.paths import validate_safe_path
from studiobridge.flp.model.project import Project
from studiobridge.mcp.tools.flp import FlpTools
from studiobridge.mcp.tools.notes import NotesTools
from studiobridge.mcp.tools.render import RenderTools

# -----------------------------------------------------------------------------
# Core Path Traversal Validation Tests
# -----------------------------------------------------------------------------


class TestCorePathTraversalValidation:
    """Verifies core validate_safe_path security boundaries.

    # req: SEC-04
    """

    def test_reject_empty_path(self) -> None:
        """Reject empty or whitespace-only paths.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path("")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path("   ")
        assert exc_info.value.code == "E_SECURITY"

    @pytest.mark.parametrize(
        "traversal_path",
        [
            "../../etc/passwd",
            "..\\..\\Windows\\System32\\cmd.exe",
            "dir/../../../secret.txt",
            "foo/bar/..",
            "foo/bar/../..",
            "..",
            "../",
            "..\\",
        ],
    )
    def test_reject_directory_traversal_sequences(self, traversal_path: str) -> None:
        """Reject parent directory traversal sequences '..'.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path(traversal_path)
        assert exc_info.value.code == "E_SECURITY"
        assert "forbidden" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "null_byte_path",
        [
            "project\0.flp",
            "safe_dir/test\0_malicious.flp",
            "\0start_null.flp",
        ],
    )
    def test_reject_embedded_null_bytes(self, null_byte_path: str) -> None:
        """Reject paths containing embedded null bytes.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path(null_byte_path)
        assert exc_info.value.code == "E_SECURITY"
        assert "null byte" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "url_encoded_path",
        [
            "%2e%2e/etc/passwd",
            "%2e%2e%2f%2e%2e%2fWindows",
            "%252e%252e/secret",
            "folder/%2e%2e/file.txt",
        ],
    )
    def test_reject_url_encoded_traversal(self, url_encoded_path: str) -> None:
        """Reject URL-encoded path traversal sequences.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path(url_encoded_path)
        assert exc_info.value.code == "E_SECURITY"
        assert "url-encoded" in str(exc_info.value).lower()

    @pytest.mark.parametrize(
        "unc_path",
        [
            r"\\evil-server\share\file.flp",
            "//evil-server/share/file.flp",
            r"\\?\UNC\evil-server\share\file.flp",
        ],
    )
    def test_reject_unauthorized_unc_network_paths(self, unc_path: str) -> None:
        """Reject unauthorized UNC network paths.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path(unc_path, allow_unc=False)
        assert exc_info.value.code == "E_SECURITY"
        assert "unc" in str(exc_info.value).lower()

    def test_reject_path_escaping_allowed_roots(self, tmp_path: Path) -> None:
        """Reject paths outside explicitly designated allowed root directories.

        # req: SEC-04
        """
        safe_root = tmp_path / "safe"
        safe_root.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "target.flp"
        outside_file.write_bytes(b"FLdt")

        with pytest.raises(SecurityError) as exc_info:
            validate_safe_path(outside_file, allowed_roots=[safe_root])
        assert exc_info.value.code == "E_SECURITY"
        assert "outside allowed safe directories" in str(exc_info.value).lower()

    def test_accept_valid_path_within_allowed_root(self, tmp_path: Path) -> None:
        """Accept paths strictly contained within allowed root directory.

        # req: SEC-04
        """
        safe_root = tmp_path / "safe"
        safe_root.mkdir()
        valid_file = safe_root / "project.flp"
        valid_file.write_bytes(b"FLdt")

        resolved = validate_safe_path(valid_file, allowed_roots=[safe_root])
        assert resolved == valid_file.resolve()


# -----------------------------------------------------------------------------
# MCP Tools Path Traversal Defense Tests
# -----------------------------------------------------------------------------


class TestMcpToolsPathContainment:
    """Verifies that all file-accepting MCP tool providers reject traversal attacks.

    # req: SEC-04
    """

    def test_flp_inspect_rejects_traversal(self) -> None:
        """flp_inspect rejects directory traversal and UNC paths.

        # req: SEC-04
        """
        provider = FlpTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file="../../etc/passwd")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file=r"\\remote\share\pwn.flp")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file="file\0evil.flp")
        assert exc_info.value.code == "E_SECURITY"

    def test_flp_diff_rejects_traversal(self, tmp_path: Path) -> None:
        """flp_diff rejects traversal in file_a and file_b arguments.

        # req: SEC-04
        """
        valid_flp = tmp_path / "sample.flp"
        valid_flp.write_bytes(b"FLdt")
        provider = FlpTools()

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_diff(file_a="../../a.flp", file_b=str(valid_flp))
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_diff(file_a=str(valid_flp), file_b="..\\..\\Windows\\System32\\cmd.exe")
        assert exc_info.value.code == "E_SECURITY"

    def test_flp_edit_rejects_traversal(self, tmp_path: Path) -> None:
        """flp_edit rejects traversal in file and destination arguments.

        # req: SEC-04
        """
        valid_flp = tmp_path / "sample.flp"
        valid_flp.write_bytes(b"FLdt")
        provider = FlpTools()

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_edit(file="../../escaped.flp", mutations=[])
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_edit(file=str(valid_flp), destination="../../dest.flp", mutations=[])
        assert exc_info.value.code == "E_SECURITY"

    def test_flp_save_as_rejects_traversal(self, tmp_path: Path) -> None:
        """flp_save_as rejects traversal in source and destination.

        # req: SEC-04
        """
        valid_flp = tmp_path / "sample.flp"
        valid_flp.write_bytes(b"FLdt")
        provider = FlpTools()

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_save_as(source="../../source.flp", destination=str(tmp_path / "out.flp"))
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.flp_save_as(source=str(valid_flp), destination="../../out.flp")
        assert exc_info.value.code == "E_SECURITY"

    def test_flp_new_from_template_rejects_traversal(self) -> None:
        """flp_new_from_template rejects traversal destination.

        # req: SEC-04
        """
        provider = FlpTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.flp_new_from_template(template="minimal", destination="../../out.flp")
        assert exc_info.value.code == "E_SECURITY"

    def test_notes_tools_rejects_traversal(self) -> None:
        """NotesTools methods reject directory traversal attacks.

        # req: SEC-04
        """
        provider = NotesTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.notes_read(flp_path="../../escaped.flp")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.notes_from_midi(path=r"..\..\Windows\System32\sample.mid")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.notes_apply(notes=[], file="../../evil.flp")
        assert exc_info.value.code == "E_SECURITY"

    def test_render_tools_rejects_traversal(self) -> None:
        """RenderTools methods reject directory traversal and null byte injections.

        # req: SEC-04
        """
        provider = RenderTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.render_start(source="../../etc/passwd")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.render_start(source="valid.flp", out_dir="..\\..\\Windows\\System32")
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            provider.render_analyze(path="audio\0injection.wav")
        assert exc_info.value.code == "E_SECURITY"


# -----------------------------------------------------------------------------
# FLP Operations & CLI Path Traversal Defense Tests
# -----------------------------------------------------------------------------


class TestFlpOperationsPathContainment:
    """Verifies path containment during FLP project operations and CLI command dispatch.

    # req: SEC-04
    """

    def test_project_load_validate_path_rejects_traversal(self) -> None:
        """Project.load with validate_path=True rejects traversal attacks.

        # req: SEC-04
        """
        with pytest.raises(SecurityError) as exc_info:
            Project.load("../../etc/passwd", validate_path=True)
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            Project.load(r"\\remote\share\file.flp", validate_path=True)
        assert exc_info.value.code == "E_SECURITY"

        with pytest.raises(SecurityError) as exc_info:
            Project.load("file\0evil.flp", validate_path=True)
        assert exc_info.value.code == "E_SECURITY"

    def test_cli_flp_inspect_rejects_traversal(self) -> None:
        """sbridge flp inspect rejects path traversal arguments with SecurityError.

        # req: SEC-04
        """
        args = argparse.Namespace(file="../../etc/passwd", json=False)
        with pytest.raises(SecurityError) as exc_info:
            _handle_inspect(args)
        assert exc_info.value.code == "E_SECURITY"

    def test_cli_flp_diff_rejects_traversal(self, tmp_path: Path) -> None:
        """sbridge flp diff rejects path traversal arguments with SecurityError.

        # req: SEC-04
        """
        sample_file = tmp_path / "sample.flp"
        sample_file.write_bytes(b"FLdt")

        args = argparse.Namespace(file_a="../../a.flp", file_b=str(sample_file), json=False)
        with pytest.raises(SecurityError) as exc_info:
            _handle_diff(args)
        assert exc_info.value.code == "E_SECURITY"

    def test_cli_flp_edit_rejects_traversal(self) -> None:
        """sbridge flp edit rejects path traversal arguments with SecurityError.

        # req: SEC-04
        """
        args = argparse.Namespace(file=r"..\..\Windows\System32\cmd.exe", json=False)
        with pytest.raises(SecurityError) as exc_info:
            _handle_edit(args)
        assert exc_info.value.code == "E_SECURITY"

    def test_cli_flp_validate_rejects_traversal(self) -> None:
        """sbridge flp validate rejects path traversal arguments with SecurityError.

        # req: SEC-04
        """
        args = argparse.Namespace(file="escaped/../../secret.flp", json=False)
        with pytest.raises(SecurityError) as exc_info:
            _handle_validate(args)
        assert exc_info.value.code == "E_SECURITY"

    def test_cli_flp_new_rejects_traversal(self) -> None:
        """sbridge flp new rejects traversal destination with SecurityError.

        # req: SEC-04
        """
        args = argparse.Namespace(
            output="../../new_project.flp",
            template="minimal",
            force=False,
            json=False,
        )
        with pytest.raises(SecurityError) as exc_info:
            _handle_new(args)
        assert exc_info.value.code == "E_SECURITY"
