"""Unit tests for brand token management and rename tooling.

Tests sub-phase v0.1.9 requirements:
- Definition of central brand tokens and validation constraints (tools/tokens.py).
- Port root length constraint (<= 20 chars to prevent WinMM 31-char truncation).
- Rename dry-run accuracy and non-destructive behavior (tools/rename.py).
- Strict case-sensitive and token-boundary replacements without collision.
- Wire magic protocol constant protection ('53 42', b"SB").
- Automated CI check (--check) flagging unauthorized brand tokens.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.rename import (
    RenameReport,
    check_brand_integrity,
    main,
    perform_rename,
)
from tools.tokens import (
    DEFAULT_TOKENS,
    MAX_PORT_ROOT_LENGTH,
    BrandTokens,
    check_protocol_constant_protection,
    validate_tokens,
)


class TestPortRootValidation:
    """Validate PORT_ROOT length constraints per 00_INDEX.md §8."""

    def test_default_port_root_valid(self) -> None:
        """Default port root 'SBridge' (7 chars) must be valid and <= 20 chars."""
        tokens = BrandTokens()
        assert tokens.port_root == "SBridge"
        assert len(tokens.port_root) <= MAX_PORT_ROOT_LENGTH
        validate_tokens(tokens)

    def test_port_root_max_length_boundary(self) -> None:
        """Port root of exactly 20 characters is valid."""
        twenty_chars = "A" * 20
        tokens = BrandTokens(port_root=twenty_chars)
        assert len(tokens.port_root) == 20
        validate_tokens(tokens)

    def test_port_root_exceeding_20_chars_raises_value_error(self) -> None:
        """Port root of 21 characters must be rejected to prevent WinMM truncation."""
        twenty_one_chars = "A" * 21
        with pytest.raises(ValueError, match="exceeds maximum length of 20 characters"):
            BrandTokens(port_root=twenty_one_chars)

    def test_port_root_empty_raises_value_error(self) -> None:
        """Empty port root must be rejected."""
        with pytest.raises(ValueError, match="PORT_ROOT must not be empty"):
            BrandTokens(port_root="")

    def test_validate_tokens_dict_input(self) -> None:
        """validate_tokens accepts raw dictionary mapping."""
        valid_dict = {
            "dist": "studiobridge",
            "cli": "sbridge",
            "port_root": "ValidPort",
            "device": "ValidDevice",
            "mcpname": "io.github.owner/valid",
        }
        validate_tokens(valid_dict)

        invalid_dict = dict(valid_dict, port_root="WayTooLongPortRootNameExceeding20Chars")
        with pytest.raises(ValueError, match="exceeds maximum length of 20 characters"):
            validate_tokens(invalid_dict)


class TestTokenInvariants:
    """Test token field formats and wire magic invariant protection."""

    def test_dist_must_be_valid_lowercase_identifier(self) -> None:
        """DIST must be a valid lowercase Python identifier."""
        with pytest.raises(ValueError, match="DIST 'StudioBridge' must be a valid lowercase"):
            BrandTokens(dist="StudioBridge")

        with pytest.raises(ValueError, match="DIST '123bad' must be a valid lowercase"):
            BrandTokens(dist="123bad")

    def test_cli_must_be_valid_lowercase(self) -> None:
        """CLI must be a valid lowercase command name."""
        with pytest.raises(ValueError, match="CLI 'SBRIDGE' must be a valid lowercase"):
            BrandTokens(cli="SBRIDGE")

    def test_device_must_be_valid_identifier(self) -> None:
        """DEVICE must be a non-empty valid identifier."""
        with pytest.raises(ValueError, match="DEVICE must not be empty"):
            BrandTokens(device="")

    def test_wire_magic_invariant_rejected_as_token_value(self) -> None:
        """Token values matching wire protocol magic must be rejected."""
        for forbidden in ("53 42", "0x53", "0x42", "5342", "SB"):
            with pytest.raises(ValueError, match="conflicting with protocol wire magic constant"):
                BrandTokens(dist=forbidden)

    def test_check_protocol_constant_protection_rejects_magic(self) -> None:
        """check_protocol_constant_protection rejects mappings containing wire magic."""
        with pytest.raises(ValueError, match="matches wire protocol constant"):
            check_protocol_constant_protection({"old": "sbridge", "WIRE_MAGIC": "53 42"})

        with pytest.raises(ValueError, match="matches wire protocol constant"):
            check_protocol_constant_protection(["sbridge", 'b"SB"'])

    def test_token_dicts(self) -> None:
        """BrandTokens produces expected dictionary representations."""
        tokens = BrandTokens()
        assert tokens.as_dict() == DEFAULT_TOKENS
        template_dict = tokens.as_template_dict()
        assert template_dict["{DIST}"] == "studiobridge"
        assert template_dict["{CLI}"] == "sbridge"
        assert template_dict["{PORT_ROOT}"] == "SBridge"
        assert template_dict["{DEVICE}"] == "StudioBridge"
        assert template_dict["{MCPNAME}"] == "io.github.<owner>/studiobridge"


class TestRenameDryRun:
    """Test --dry-run accuracy and non-destructive execution."""

    @pytest.fixture
    def sample_workspace(self, tmp_path: Path) -> Path:
        """Create a mock workspace with source files, docs, and templates."""
        pkg_dir = tmp_path / "packages" / "studiobridge"
        pkg_dir.mkdir(parents=True)
        py_file = pkg_dir / "app.py"
        py_file.write_text(
            '"""StudioBridge main application."""\n'
            "from studiobridge.core import StudioBridgeError\n"
            'CLI_NAME = "sbridge"\n'
            'PORT_DEFAULT = "SBridge"\n'
            'MAGIC = b"SB"  # 0x53 0x42\n',
            encoding="utf-8",
        )

        doc_file = tmp_path / "README.md"
        doc_file.write_text(
            "# StudioBridge\n\nRun `sbridge hello` to connect. Port is `SBridge`.\n"
            "Publish as io.github.<owner>/studiobridge.\n",
            encoding="utf-8",
        )

        tmpl_file = tmp_path / "template.txt"
        tmpl_file.write_text(
            "Install {DIST} via `pip install {DIST}`. Command: {CLI}. Device: {DEVICE}.\n",
            encoding="utf-8",
        )

        return tmp_path

    def test_dry_run_reports_accurate_counts_without_modifying_files(
        self, sample_workspace: Path
    ) -> None:
        """perform_rename with dry_run=True computes counts and leaves files untouched."""
        py_file = sample_workspace / "packages" / "studiobridge" / "app.py"
        doc_file = sample_workspace / "README.md"
        tmpl_file = sample_workspace / "template.txt"

        original_py = py_file.read_text(encoding="utf-8")
        original_doc = doc_file.read_text(encoding="utf-8")
        original_tmpl = tmpl_file.read_text(encoding="utf-8")

        from_tokens = BrandTokens()
        to_tokens = BrandTokens(
            dist="novadaw",
            cli="ndaw",
            port_root="NovaPort",
            device="NovaDaw",
            mcpname="io.github.nova/novadaw",
        )

        report = perform_rename(
            root=sample_workspace,
            from_tokens=from_tokens,
            to_tokens=to_tokens,
            dry_run=True,
        )

        assert isinstance(report, RenameReport)
        assert report.scanned_files == 3
        assert report.modified_files == 3
        assert report.total_replacements > 0
        assert len(report.errors) == 0

        # Assert files on disk are 100% UNMODIFIED
        assert py_file.read_text(encoding="utf-8") == original_py
        assert doc_file.read_text(encoding="utf-8") == original_doc
        assert tmpl_file.read_text(encoding="utf-8") == original_tmpl

    def test_cli_dry_run_invocation(
        self, sample_workspace: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI invocation with --dry-run prints report and returns 0."""
        tokens_json = json.dumps(
            {
                "dist": "novadaw",
                "cli": "ndaw",
                "port_root": "NovaPort",
                "device": "NovaDaw",
                "mcpname": "io.github.nova/novadaw",
            }
        )

        ret = main(["--root", str(sample_workspace), "--to-tokens", tokens_json, "--dry-run", "-v"])
        assert ret == 0

        captured = capsys.readouterr()
        assert "Brand Token Rename Report [DRY RUN (no files modified)]" in captured.out
        assert "Scanned files: 3" in captured.out
        assert "Modified files: 3" in captured.out
        assert "Total replacements:" in captured.out


class TestReplacementBehavior:
    """Test case-sensitivity and token-boundary replacements."""

    def test_boundary_and_case_sensitivity(self, tmp_path: Path) -> None:
        """Replacements must preserve case and respect word/token boundaries."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "# Collisions that MUST NOT be touched:\n"
            "# crossbridge, asbridge, sbridgesmith, mystudiobridge, studiobridges, ISBridge\n"
            "var_a = 'crossbridge'\n"
            "var_b = 'asbridge'\n"
            "var_c = 'sbridgesmith'\n"
            "var_d = 'mystudiobridge'\n"
            "var_e = 'studiobridges'\n"
            "var_f = 'ISBridge'\n\n"
            "# Valid targets that MUST be replaced:\n"
            "from studiobridge.core import StudioBridgeError\n"
            "cmd = 'sbridge'\n"
            "port = 'SBridge'\n"
            "env = 'SBRIDGE_CONFIG'\n"
            "header = 'device_StudioBridge.py'\n",
            encoding="utf-8",
        )

        from_tokens = BrandTokens()
        to_tokens = BrandTokens(
            dist="novadaw",
            cli="ndaw",
            port_root="NovaPort",
            device="NovaDaw",
            mcpname="io.github.nova/novadaw",
        )

        report = perform_rename(
            root=tmp_path,
            from_tokens=from_tokens,
            to_tokens=to_tokens,
            dry_run=False,
        )

        assert report.modified_files == 1
        content = test_file.read_text(encoding="utf-8")

        # Non-targets MUST NOT have been modified
        assert "var_a = 'crossbridge'" in content
        assert "var_b = 'asbridge'" in content
        assert "var_c = 'sbridgesmith'" in content
        assert "var_d = 'mystudiobridge'" in content
        assert "var_e = 'studiobridges'" in content
        assert "var_f = 'ISBridge'" in content

        # Valid targets MUST have been modified correctly
        assert "from novadaw.core import NovaDawError" in content
        assert "cmd = 'ndaw'" in content
        assert "port = 'NovaPort'" in content
        assert "env = 'NDAW_CONFIG'" in content
        assert "header = 'device_NovaDaw.py'" in content


class TestProtocolConstantProtection:
    """Verify wire magic bytes 0x53 0x42 ('SB') are protected from modification."""

    def test_protocol_constant_preserved_in_file(self, tmp_path: Path) -> None:
        """Wire magic constants must remain identical after rename execution."""
        proto_file = tmp_path / "wire_frame.py"
        proto_file.write_text(
            '"""StudioBridge wire protocol framing."""\n'
            'MAGIC = b"SB"\n'
            'WIRE_MAGIC_HEX = "53 42"\n'
            "BYTE_ARRAY = bytes([0x53, 0x42])\n"
            'F0 = "F0 7D 53 42 01"\n'
            "import studiobridge\n",
            encoding="utf-8",
        )

        from_tokens = BrandTokens()
        to_tokens = BrandTokens(
            dist="novadaw",
            cli="ndaw",
            port_root="NovaPort",
            device="NovaDaw",
            mcpname="io.github.nova/novadaw",
        )

        report = perform_rename(
            root=tmp_path,
            from_tokens=from_tokens,
            to_tokens=to_tokens,
            dry_run=False,
        )

        assert report.modified_files == 1
        content = proto_file.read_text(encoding="utf-8")

        # Protocol constants MUST remain unchanged
        assert 'MAGIC = b"SB"' in content
        assert 'WIRE_MAGIC_HEX = "53 42"' in content
        assert "BYTE_ARRAY = bytes([0x53, 0x42])" in content
        assert 'F0 = "F0 7D 53 42 01"' in content

        # Brand token was replaced
        assert "import novadaw" in content

    def test_wire_magic_in_from_tokens_rejected(self) -> None:
        """Attempting to target wire magic in tokens raises ValueError."""
        with pytest.raises(ValueError, match="matches wire protocol constant"):
            check_protocol_constant_protection({"wire": "53 42"})

        with pytest.raises(ValueError, match="conflicting with protocol wire magic constant"):
            validate_tokens({"dist": "53 42"})


class TestBrandIntegrityCheck:
    """Test automated CI check (--check) for brand token integrity."""

    def test_ci_check_passes_on_current_codebase(self) -> None:
        """check_brand_integrity must pass cleanly on current repository."""
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        result = check_brand_integrity(root=repo_root)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_ci_check_flags_unauthorized_token(self, tmp_path: Path) -> None:
        """check_brand_integrity flags unauthorized tokens in new files."""
        # Create a clean mock workspace
        valid_file = tmp_path / "valid.py"
        valid_file.write_text("import studiobridge\n", encoding="utf-8")

        res_clean = check_brand_integrity(root=tmp_path)
        assert res_clean.passed is True

        # Now introduce an unauthorized legacy token
        bad_file = tmp_path / "legacy.py"
        bad_file.write_text("import Flapi\n", encoding="utf-8")

        res_bad = check_brand_integrity(root=tmp_path)
        assert res_bad.passed is False
        assert any("Unauthorized token 'Flapi'" in err for err in res_bad.errors)

    def test_ci_check_cli_exit_code(self, tmp_path: Path) -> None:
        """CLI --check returns 0 on clean code and 1 when unauthorized tokens found."""
        valid_file = tmp_path / "valid.py"
        valid_file.write_text("import studiobridge\n", encoding="utf-8")

        assert main(["--root", str(tmp_path), "--check"]) == 0

        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import PyFLP\n", encoding="utf-8")

        assert main(["--root", str(tmp_path), "--check"]) == 1


class TestCommandLineInterface:
    """Test CLI argument parsing and error conditions."""

    def test_missing_to_tokens_when_not_check(self) -> None:
        """Omitting --to-tokens without --check exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--dry-run"])
        assert exc_info.value.code != 0

    def test_invalid_to_tokens_json(self) -> None:
        """Invalid JSON in --to-tokens returns non-zero exit code."""
        ret = main(["--to-tokens", "{not: json}", "--dry-run"])
        assert ret == 1

    def test_long_port_root_cli_rejected(self) -> None:
        """Port root > 20 chars via CLI returns exit code 1."""
        bad_json = json.dumps({"port_root": "WayTooLongPortRootExceeding20Chars"})
        ret = main(["--to-tokens", bad_json, "--dry-run"])
        assert ret == 1
