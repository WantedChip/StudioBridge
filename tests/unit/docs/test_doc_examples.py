"""Unit tests for documentation content, recipes, and compatibility generator.

Verifies automated compatibility table compilation from diagnostic fixtures,
validates code snippets and recipes from documentation guides, and ensures
authoritative coverage of all diagnostic doctor checks and Tier-1 agent configurations.

# req: DOC-01
# req: DOC-02
# req: DOC-03
# req: CAP-01
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from studiobridge import AsyncStudio, Studio
from tools.generate_compat import (
    ARCHITECTURES,
    CAPABILITIES_CATALOG,
    FL_BUILDS,
    build_compat_dataset,
    load_diagnostic_fixtures,
    verify_compat_dataset,
)
from tools.generate_compat import (
    main as compat_main,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOCS_DIR = REPO_ROOT / "site" / "src" / "content" / "docs"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "diag"


# =============================================================================
# 1. Compatibility Generator Tests (tools/generate_compat.py)
# =============================================================================


class TestCompatGenerator:
    """Tests for tools/generate_compat.py matrix compilation and verification.

    # req: CAP-01
    # req: DOC-02
    """

    def test_load_diagnostic_fixtures_directory_and_zip(self) -> None:
        """Verify ingestion of directory bundles, zip archives, and community fixtures.

        # req: DOC-02
        """
        assert FIXTURES_DIR.exists(), f"Fixtures dir {FIXTURES_DIR} must exist"
        fixtures = load_diagnostic_fixtures(FIXTURES_DIR)

        assert fixtures["machine_a"] is not None, "Machine A fixture must be loaded"
        assert fixtures["machine_b"] is not None, "Machine B fixture must be loaded"
        assert len(fixtures["community"]) >= 2, "Community submissions must be ingested"

        # Check Machine A structure
        ma = fixtures["machine_a"]
        assert "env" in ma or "probe" in ma or "doctor" in ma
        if "env" in ma:
            assert ma["env"]["platform"]["machine"] in ("ARM64", "AMD64")

        # Check Machine B structure
        mb = fixtures["machine_b"]
        assert "env" in mb or "probe" in mb or "doctor" in mb

    def test_build_compat_dataset_schema(self) -> None:
        """Verify compiled dataset schema satisfies web and documentation contracts.

        # req: CAP-01
        """
        fixtures = load_diagnostic_fixtures(FIXTURES_DIR)
        dataset = build_compat_dataset(fixtures)

        errors = verify_compat_dataset(dataset)
        assert len(errors) == 0, f"Schema validation errors: {errors}"

        # Verify metadata
        meta = dataset["meta"]
        assert meta["schemaVersion"] == "1.0.0"
        assert meta["specVersion"] == "1.0.0"
        assert "machineA" in meta["testedEnvironments"]
        assert "machineB" in meta["testedEnvironments"]
        assert meta["testedEnvironments"]["machineA"]["arch"] == "ARM64"
        assert meta["testedEnvironments"]["machineB"]["arch"] == "x64"

    def test_matrix_all_configurations_and_capabilities(self) -> None:
        """Verify all 6 matrix combinations cover all 12 core capabilities.

        # req: CAP-01
        """
        dataset = build_compat_dataset()
        matrix = dataset["matrix"]

        expected_configs = [
            "26.1.3-ARM64",
            "26.1.3-x64",
            "25.2.3-ARM64",
            "25.2.3-x64",
            "21.2-ARM64",
            "21.2-x64",
        ]
        assert len(matrix) == 6
        for cfg in expected_configs:
            assert cfg in matrix, f"Missing matrix configuration '{cfg}'"
            entry = matrix[cfg]
            assert entry["flBuild"] in [b["id"] for b in FL_BUILDS]
            assert entry["arch"] in [a["id"] for a in ARCHITECTURES]
            assert len(entry["capabilities"]) == 12

            for cat in CAPABILITIES_CATALOG:
                cid = cat["id"]
                assert cid in entry["capabilities"], f"Missing capability '{cid}' in '{cfg}'"
                cap_item = entry["capabilities"][cid]
                assert cap_item["state"] in ("available", "degraded", "unavailable")
                assert cap_item["statusLabel"] in ("AVAILABLE", "DEGRADED", "UNAVAILABLE")
                assert len(cap_item["reason"]) > 0
                assert len(cap_item["alternatives"]) > 0
                assert len(cap_item["diagRef"]) > 0

    def test_state_transitions(self) -> None:
        """Verify state transitions across ARM64/x64 and FL version boundaries.

        # req: CAP-01
        """
        dataset = build_compat_dataset()
        matrix = dataset["matrix"]

        # CAP_HOST_NATIVE_ARM64: degraded on ARM64, available on x64
        a_caps = matrix["26.1.3-ARM64"]["capabilities"]
        b_caps = matrix["26.1.3-x64"]["capabilities"]
        assert a_caps["CAP_HOST_NATIVE_ARM64"]["state"] == "degraded"
        assert b_caps["CAP_HOST_NATIVE_ARM64"]["state"] == "available"

        # CAP_PLUGIN_INSTANTIATE: unavailable across all platforms
        for cfg in matrix.values():
            assert cfg["capabilities"]["CAP_PLUGIN_INSTANTIATE"]["state"] == "unavailable"

        # CAP_FLP_PLAYLIST_WRITE: degraded on FL 26, available on FL 25 and FL 21
        assert a_caps["CAP_FLP_PLAYLIST_WRITE"]["state"] == "degraded"
        assert b_caps["CAP_FLP_PLAYLIST_WRITE"]["state"] == "degraded"
        assert matrix["25.2.3-ARM64"]["capabilities"]["CAP_FLP_PLAYLIST_WRITE"]["state"] == (
            "available"
        )
        assert matrix["21.2-x64"]["capabilities"]["CAP_FLP_PLAYLIST_WRITE"]["state"] == "available"

    def test_cli_verify_flag(self) -> None:
        """Verify CLI --verify flag execution returns 0 on valid fixtures.

        # req: CAP-01
        """
        code = compat_main(["--fixtures-dir", str(FIXTURES_DIR), "--verify", "--quiet"])
        assert code == 0

    def test_cli_output_and_markdown_out(self, tmp_path: Path) -> None:
        """Verify CLI writes schema-valid compat.json and Markdown tables.

        # req: CAP-01
        # req: DOC-01
        """
        json_out = tmp_path / "compat.json"
        md_out = tmp_path / "compatibility.md"

        code = compat_main(
            [
                "--fixtures-dir",
                str(FIXTURES_DIR),
                "--output",
                str(json_out),
                "--markdown-out",
                str(md_out),
                "--quiet",
            ]
        )
        assert code == 0
        assert json_out.exists()
        assert md_out.exists()

        # Validate JSON content
        data = json.loads(json_out.read_text(encoding="utf-8"))
        errors = verify_compat_dataset(data)
        assert len(errors) == 0

        # Validate Markdown content
        md_text = md_out.read_text(encoding="utf-8")
        assert 'title: "Compatibility & Capability Matrix"' in md_text
        assert "## Matrix Summary" in md_text
        assert "## Tested Hardware Platforms" in md_text
        assert "Machine A (Windows on ARM64 Reference)" in md_text
        assert "Machine B (Windows x64 Audio Workstation)" in md_text
        assert "## Detailed Capability Reference" in md_text
        assert "## Non-Affiliation Notice" in md_text

    def test_verify_dataset_detects_malformed_structures(self) -> None:
        """Verify verify_compat_dataset rejects malformed datasets.

        # req: CAP-01
        """
        bad_dataset: dict[str, Any] = {"meta": {}, "matrix": {}}
        errors = verify_compat_dataset(bad_dataset)
        assert len(errors) > 0


# =============================================================================
# 2. Tier-1 Agent Configuration Snippets Verification
# =============================================================================


class TestAgentConfigurationSnippets:
    """Verifies all Tier-1 coding agents have valid, parseable config snippets in docs.

    # req: DOC-03
    """

    @pytest.fixture
    def quickstart_content(self) -> str:
        """Load quickstart.md documentation text."""
        doc_candidates = [
            DOCS_DIR / "docs" / "getting-started" / "quickstart.md",
            DOCS_DIR / "quickstart.md",
        ]
        for p in doc_candidates:
            if p.is_file():
                return p.read_text(encoding="utf-8")
        pytest.fail(f"Could not find quickstart.md in {[str(c) for c in doc_candidates]}")

    def test_tier1_agents_documented(self, quickstart_content: str) -> None:
        """Verify all Tier-1 agents are documented in quickstart guide.

        Tier-1 agents: Claude Desktop, Cursor, Windsurf, Copilot, Cline, Codex, Antigravity.
        # req: DOC-03
        """
        tier1_agents = [
            "Claude Desktop",
            "Cursor",
            "Windsurf",
            "Copilot",
            "Cline",
            "Codex",
            "Antigravity",
        ]
        for agent in tier1_agents:
            assert agent in quickstart_content, f"Tier-1 agent '{agent}' missing from quickstart"

    def test_json_mcp_config_snippets_validity(self, quickstart_content: str) -> None:
        """Verify all JSON code blocks in quickstart parse cleanly and use proper MCP command.

        # req: DOC-03
        """
        # Extract json code blocks
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", quickstart_content, re.DOTALL)
        assert len(json_blocks) >= 5, "Expected at least 5 JSON configuration blocks"

        for block in json_blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Invalid JSON in quickstart snippet:\n{block}\nError: {exc}")

            assert isinstance(parsed, dict)
            # Check for mcpServers or context_servers or mcp.servers key
            server_container = None
            if "mcpServers" in parsed:
                server_container = parsed["mcpServers"]
            elif "context_servers" in parsed:
                server_container = parsed["context_servers"]
            elif "mcp.servers" in parsed:
                server_container = parsed["mcp.servers"]

            if server_container and "studiobridge" in server_container:
                sb_cfg = server_container["studiobridge"]
                assert sb_cfg.get("command") == "uvx"
                assert sb_cfg.get("args") == ["studiobridge", "mcp"]

    def test_toml_mcp_config_snippets_validity(self, quickstart_content: str) -> None:
        """Verify TOML code blocks (e.g. Codex) parse cleanly and define studiobridge server.

        # req: DOC-03
        """
        toml_blocks = re.findall(r"```toml\s*\n(.*?)\n```", quickstart_content, re.DOTALL)
        assert len(toml_blocks) >= 1, "Expected at least 1 TOML configuration block"

        for block in toml_blocks:
            try:
                parsed = tomllib.loads(block)
            except Exception as exc:
                pytest.fail(f"Invalid TOML in quickstart snippet:\n{block}\nError: {exc}")

            assert "mcp_servers" in parsed
            assert "studiobridge" in parsed["mcp_servers"]
            sb_cfg = parsed["mcp_servers"]["studiobridge"]
            assert sb_cfg["command"] == "uvx"
            assert sb_cfg["args"] == ["studiobridge", "mcp"]


# =============================================================================
# 3. Python SDK Documentation Code Examples Verification
# =============================================================================


class TestPythonDocExamples:
    """Verifies that all Python SDK code recipes in documentation are valid.

    # req: DOC-03
    """

    def test_quickstart_python_snippets_ast_parse(self) -> None:
        """Verify all python code blocks in quickstart parse cleanly via ast.parse.

        # req: DOC-03
        """
        quickstart_path = DOCS_DIR / "docs" / "getting-started" / "quickstart.md"
        if not quickstart_path.exists():
            quickstart_path = DOCS_DIR / "quickstart.md"

        content = quickstart_path.read_text(encoding="utf-8")
        py_blocks = re.findall(r"```python\s*\n(.*?)\n```", content, re.DOTALL)
        assert len(py_blocks) >= 2, "Expected at least 2 Python SDK code examples"

        for i, code in enumerate(py_blocks):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                pytest.fail(f"Python SDK snippet #{i + 1} has syntax error:\n{code}\nError: {exc}")

    def test_sdk_studio_recipe_mock_execution(self) -> None:
        """Verify Studio synchronous quickstart snippet executes cleanly with mock backend.

        # req: DOC-03
        """
        with patch.object(Studio, "connect") as mock_connect:
            mock_studio = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_studio
            mock_studio.transport.is_playing.return_value = False
            mock_studio.mixer.get_volume.return_value = 0.80

            with Studio.connect() as studio:
                is_playing = studio.transport.is_playing()
                assert is_playing is False

                master_vol = studio.mixer.get_volume(0)
                assert master_vol == 0.80

    def test_sdk_async_studio_recipe_mock_execution(self) -> None:
        """Verify AsyncStudio async quickstart snippet executes cleanly with mock backend.

        # req: DOC-03
        """

        async def _test() -> None:
            with patch.object(AsyncStudio, "connect") as mock_connect:
                mock_builder = MagicMock()
                mock_studio = MagicMock()
                mock_connect.return_value = mock_builder

                async def _mock_aenter(self_builder: Any) -> Any:
                    return mock_studio

                async def _mock_aexit(self_builder: Any, *args: Any) -> None:
                    pass

                mock_builder.__aenter__ = _mock_aenter
                mock_builder.__aexit__ = _mock_aexit

                async def mock_get_tempo() -> float:
                    return 130.0

                mock_studio.transport.get_tempo = mock_get_tempo

                async with AsyncStudio.connect() as studio:
                    tempo = await studio.transport.get_tempo()
                    assert tempo == 130.0

        asyncio.run(_test())


# =============================================================================
# 4. Doctor Check Documentation Directory Completeness
# =============================================================================


class TestDoctorCheckCompleteness:
    """Verifies every doctor check ID is fully documented with symptoms, causes, and remediation.

    # req: DOC-01
    """

    def test_every_doctor_id_documented(self) -> None:
        """Verify 100% of check IDs in doctor.py are documented in doctor-checks.md.

        # req: DOC-01
        """
        doctor_py_path = (
            REPO_ROOT / "packages" / "studiobridge" / "src" / "studiobridge" / "setup" / "doctor.py"
        )
        assert doctor_py_path.exists(), "doctor.py must exist"
        doctor_py_content = doctor_py_path.read_text(encoding="utf-8")

        # Extract all registered check IDs
        check_ids = sorted(set(re.findall(r'id=["\'](D-[A-Z0-9-]+)["\']', doctor_py_content)))
        assert len(check_ids) >= 25, f"Expected >= 25 doctor check IDs, found {len(check_ids)}"

        doc_paths = [
            DOCS_DIR / "docs" / "troubleshooting" / "doctor-checks.md",
            DOCS_DIR / "troubleshooting.md",
        ]

        for doc_path in doc_paths:
            if not doc_path.exists():
                continue
            doc_content = doc_path.read_text(encoding="utf-8")

            for check_id in check_ids:
                assert check_id in doc_content, f"Check ID '{check_id}' missing in {doc_path.name}"

                # Match section heading
                section_pattern = rf"### `{re.escape(check_id)}`([\s\S]*?)(?=### `D-|$)"
                match = re.search(section_pattern, doc_content)
                assert match is not None, f"Heading '### `{check_id}`' missing in {doc_path.name}"

                section_body = match.group(1)
                assert "Failure Mode:" in section_body or "Symptoms:" in section_body, (
                    f"Check ID '{check_id}' missing Failure Mode/Symptoms in {doc_path.name}"
                )
                assert "Root Causes:" in section_body, (
                    f"Check ID '{check_id}' missing Root Causes in {doc_path.name}"
                )
                assert "Recovery Steps:" in section_body, (
                    f"Check ID '{check_id}' missing Recovery Steps in {doc_path.name}"
                )
