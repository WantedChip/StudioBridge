"""Unit tests for Software Bill of Materials (SBOM) generator.

Covers:
- CycloneDX 1.5 JSON schema generation and verification (# req: DIST-06, # req: REL-01)
- SPDX 2.3 JSON schema generation and verification (# req: DIST-06, # req: REL-01)
- Package manifest and lockfile parsing (# req: DIST-06)
- Runtime dependency closure computation (# req: DIST-06)
- Component inventory, purl formatting, and SHA-256 hashes (# req: DIST-06)
- CLI invocation, verification gates, and error reporting (# req: REL-01)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.generate_sbom import (
    determine_runtime_closure,
    generate_cyclonedx_sbom,
    generate_spdx_sbom,
    load_lockfile_packages,
    load_npm_package_info,
    load_python_package_info,
    resolve_license,
    verify_cyclonedx_sbom,
    verify_sbom_file,
    verify_spdx_sbom,
)
from tools.generate_sbom import (
    main as sbom_main,
)

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def workspace_root() -> Path:
    """Return workspace root path."""
    return _WORKSPACE_ROOT


@pytest.fixture(scope="session")
def python_info(workspace_root: Path) -> dict[str, Any]:
    """Load python package info from pyproject.toml."""
    path = workspace_root / "packages" / "studiobridge" / "pyproject.toml"
    return load_python_package_info(path)


@pytest.fixture(scope="session")
def npm_info(workspace_root: Path) -> dict[str, Any]:
    """Load npm package info from npm/studiobridge/package.json."""
    path = workspace_root / "npm" / "studiobridge" / "package.json"
    return load_npm_package_info(path)


@pytest.fixture(scope="session")
def lock_packages(workspace_root: Path) -> list[dict[str, Any]]:
    """Load resolved packages from uv.lock."""
    path = workspace_root / "uv.lock"
    return load_lockfile_packages(path)


@pytest.fixture(scope="session")
def runtime_closure(
    python_info: dict[str, Any], lock_packages: list[dict[str, Any]]
) -> set[str]:
    """Compute runtime dependency closure."""
    return determine_runtime_closure(python_info["dependencies"], lock_packages)


# req: DIST-06
def test_load_python_package_info(python_info: dict[str, Any]) -> None:
    """Verify python package info loaded from pyproject.toml."""
    assert python_info["name"] == "studiobridge"
    assert python_info["version"] == "1.0.0"
    assert python_info["license"] == "MIT"
    assert len(python_info["authors"]) >= 1
    assert "WantedChip" in python_info["authors"][0]["name"]

    dep_names = [d.split(">")[0].split("=")[0].strip() for d in python_info["dependencies"]]
    assert "anyio" in dep_names
    assert "platformdirs" in dep_names
    assert "tomlkit" in dep_names


# req: DIST-06
def test_load_npm_package_info(npm_info: dict[str, Any]) -> None:
    """Verify npm package info loaded from package.json."""
    assert npm_info["name"] == "studiobridge"
    assert npm_info["version"] == "1.0.0"
    assert npm_info["license"] == "MIT"
    assert "WantedChip" in npm_info["author"]
    assert "https://github.com/WantedChip/studiobridge" in npm_info["repository"]


# req: DIST-06
def test_load_lockfile_packages(lock_packages: list[dict[str, Any]]) -> None:
    """Verify lockfile packages loaded with hashes and dependency links."""
    assert len(lock_packages) >= 20

    names = {p["name"] for p in lock_packages}
    assert "anyio" in names
    assert "platformdirs" in names
    assert "tomlkit" in names
    assert "idna" in names
    assert "typing-extensions" in names

    # Verify SHA-256 hash presence
    anyio_pkg = next(p for p in lock_packages if p["name"] == "anyio")
    assert anyio_pkg["hash_sha256"]
    assert len(anyio_pkg["hash_sha256"]) == 64


# req: DIST-06
def test_runtime_dependency_closure(runtime_closure: set[str]) -> None:
    """Verify runtime dependency closure isolates runtime packages from dev packages."""
    assert "anyio" in runtime_closure
    assert "platformdirs" in runtime_closure
    assert "tomlkit" in runtime_closure
    assert "idna" in runtime_closure
    assert "typing-extensions" in runtime_closure

    # Dev packages must NOT be in runtime closure
    assert "pytest" not in runtime_closure
    assert "ruff" not in runtime_closure
    assert "pyright" not in runtime_closure
    assert "hypothesis" not in runtime_closure


# req: DIST-06
def test_resolve_license() -> None:
    """Verify license resolution returns valid SPDX identifiers."""
    assert resolve_license("studiobridge") == "MIT"
    assert resolve_license("anyio") == "MIT"
    assert resolve_license("platformdirs") == "MIT"
    assert resolve_license("tomlkit") == "MIT"
    assert resolve_license("idna") == "BSD-3-Clause"
    assert resolve_license("typing-extensions") == "PSF-2.0"
    assert resolve_license("unknown-pkg", fallback="MIT") == "MIT"
    assert resolve_license("unknown-pkg", fallback="BSD 3-Clause") == "BSD-3-Clause"


# req: DIST-06
# req: REL-01
def test_cyclonedx_sbom_generation(
    python_info: dict[str, Any],
    npm_info: dict[str, Any],
    lock_packages: list[dict[str, Any]],
    runtime_closure: set[str],
) -> None:
    """Verify CycloneDX 1.5 JSON SBOM generation and structural compliance."""
    sbom = generate_cyclonedx_sbom(python_info, npm_info, lock_packages, runtime_closure)

    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["version"] == 1
    assert sbom["serialNumber"].startswith("urn:uuid:")

    # Metadata & root component
    meta = sbom["metadata"]
    assert meta["component"]["name"] == "studiobridge"
    assert meta["component"]["version"] == "1.0.0"
    assert meta["component"]["purl"] == "pkg:pypi/studiobridge@1.0.0"
    assert meta["component"]["licenses"][0]["license"]["id"] == "MIT"

    # Components list
    components = sbom["components"]
    comp_map = {c["name"]: c for c in components}

    # npm launcher component
    npm_comp = comp_map["studiobridge"]
    assert npm_comp["purl"] == "pkg:npm/studiobridge@1.0.0"
    assert npm_comp["scope"] == "required"
    assert npm_comp["type"] == "application"

    # Core runtime dependencies
    anyio_comp = comp_map["anyio"]
    assert anyio_comp["purl"].startswith("pkg:pypi/anyio@")
    assert anyio_comp["scope"] == "required"
    assert anyio_comp["hashes"][0]["alg"] == "SHA-256"
    assert len(anyio_comp["hashes"][0]["content"]) == 64

    # Dependencies graph
    deps = sbom["dependencies"]
    dep_map = {d["ref"]: d["dependsOn"] for d in deps}

    # studiobridge python depends on anyio, platformdirs, tomlkit
    py_ref = "pkg:pypi/studiobridge@1.0.0"
    assert py_ref in dep_map
    root_targets = dep_map[py_ref]
    assert any("anyio" in t for t in root_targets)
    assert any("platformdirs" in t for t in root_targets)
    assert any("tomlkit" in t for t in root_targets)

    # npm launcher depends on studiobridge python package
    npm_ref = "pkg:npm/studiobridge@1.0.0"
    assert npm_ref in dep_map
    assert py_ref in dep_map[npm_ref]

    # Verification function reports 0 errors
    errors = verify_cyclonedx_sbom(sbom)
    assert not errors, f"Validation errors: {errors}"


# req: DIST-06
# req: REL-01
def test_spdx_sbom_generation(
    python_info: dict[str, Any],
    npm_info: dict[str, Any],
    lock_packages: list[dict[str, Any]],
    runtime_closure: set[str],
) -> None:
    """Verify SPDX 2.3 JSON SBOM generation and structural compliance."""
    sbom = generate_spdx_sbom(python_info, npm_info, lock_packages, runtime_closure)

    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert sbom["dataLicense"] == "CC0-1.0"
    assert sbom["SPDXID"] == "SPDXRef-DOCUMENT"
    assert sbom["name"] == "studiobridge-sbom"
    assert sbom["documentNamespace"].startswith("https://github.com/WantedChip/studiobridge/spdx/")

    packages = sbom["packages"]
    pkg_map = {p["name"]: p for p in packages}

    assert "studiobridge" in pkg_map
    assert "anyio" in pkg_map
    assert "platformdirs" in pkg_map
    assert "tomlkit" in pkg_map

    # Check SPDX identifiers format
    for p in packages:
        assert p["SPDXID"].startswith("SPDXRef-Package-")
        assert p["licenseConcluded"]
        assert p["filesAnalyzed"] is False

    relationships = sbom["relationships"]
    rel_types = {r["relationshipType"] for r in relationships}
    assert "DESCRIBES" in rel_types
    assert "DEPENDS_ON" in rel_types

    # Verification function reports 0 errors
    errors = verify_spdx_sbom(sbom)
    assert not errors, f"Validation errors: {errors}"


# req: REL-01
def test_cyclonedx_verification_catches_invalid() -> None:
    """Verify CycloneDX validation logic detects corrupt or missing fields."""
    invalid_bom = {
        "bomFormat": "InvalidFormat",
        "specVersion": "1.0",
        "serialNumber": "bad-serial",
        "components": [],
        "dependencies": [],
    }
    errors = verify_cyclonedx_sbom(invalid_bom)
    assert len(errors) >= 4
    assert any("Invalid bomFormat" in e for e in errors)
    assert any("Invalid specVersion" in e for e in errors)
    assert any("Invalid serialNumber" in e for e in errors)
    assert any("Components list is empty" in e for e in errors)


# req: REL-01
def test_spdx_verification_catches_invalid() -> None:
    """Verify SPDX validation logic detects corrupt or missing fields."""
    invalid_spdx = {
        "spdxVersion": "SPDX-1.0",
        "dataLicense": "GPL-3.0",
        "SPDXID": "BadDocId",
        "packages": [],
        "relationships": [],
    }
    errors = verify_spdx_sbom(invalid_spdx)
    assert len(errors) >= 4
    assert any("Invalid spdxVersion" in e for e in errors)
    assert any("Invalid dataLicense" in e for e in errors)
    assert any("Invalid SPDXID" in e for e in errors)
    assert any("Packages list is empty" in e for e in errors)


# req: REL-01
def test_verify_sbom_file_disk(tmp_path: Path) -> None:
    """Verify reading and validating written SBOM files from disk."""
    out_cdx = tmp_path / "sbom-cdx.json"
    ret = sbom_main(["--format", "cyclonedx", "--output", str(out_cdx), "--quiet"])
    assert ret == 0
    assert out_cdx.exists()

    ok, errors = verify_sbom_file(out_cdx)
    assert ok
    assert not errors

    out_spdx = tmp_path / "sbom-spdx.json"
    ret = sbom_main(["--format", "spdx", "--output", str(out_spdx), "--quiet"])
    assert ret == 0
    assert out_spdx.exists()

    ok, errors = verify_sbom_file(out_spdx)
    assert ok
    assert not errors

    # Non-existent file
    ok_nonexistent, errors_nonexistent = verify_sbom_file(tmp_path / "missing.json")
    assert not ok_nonexistent
    assert any("File not found" in e for e in errors_nonexistent)

    # Invalid JSON file
    bad_json = tmp_path / "corrupt.json"
    bad_json.write_text("{invalid json", encoding="utf-8")
    ok_corrupt, errors_corrupt = verify_sbom_file(bad_json)
    assert not ok_corrupt
    assert any("Failed parsing JSON" in e for e in errors_corrupt)


# req: REL-01
def test_cli_verify_in_memory() -> None:
    """Verify CLI in-memory verification passes with code 0."""
    ret_cdx = sbom_main(["--verify", "--quiet"])
    assert ret_cdx == 0

    ret_spdx = sbom_main(["--format", "spdx", "--verify", "--quiet"])
    assert ret_spdx == 0


# req: REL-01
def test_cli_verify_target_path(tmp_path: Path) -> None:
    """Verify CLI verifying target file path returns code 0."""
    target_file = tmp_path / "target_sbom.json"
    ret_build = sbom_main(["--output", str(target_file), "--quiet"])
    assert ret_build == 0

    ret_check = sbom_main(["--verify", str(target_file), "--quiet"])
    assert ret_check == 0

    ret_bad = sbom_main(["--verify", str(tmp_path / "nonexistent.json"), "--quiet"])
    assert ret_bad == 1
