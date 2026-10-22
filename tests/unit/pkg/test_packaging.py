"""Packaging, distribution, npm launcher, and MCP registry tests.

Covers:
- Python universal pure-Python wheel tag and zero native binaries ([PKG-01])
- Package data inventory and discovery ([PKG-02])
- Version lockstep between Python package and npm launcher ([NPM-01])
- Cross-platform npm launcher execution and stdio discipline ([NPM-02])
- MCP Registry metadata and ownership verification tokens ([REG-01])
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Generator
from pathlib import Path

import pytest
import tomlkit

import studiobridge

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def workspace_root() -> Path:
    """Return the root directory of the repository workspace."""
    return _WORKSPACE_ROOT


@pytest.fixture(scope="session")
def wheel_path(
    workspace_root: Path, tmp_path_factory: pytest.TempPathFactory
) -> Generator[Path, None, None]:
    """Build the universal wheel into a temporary directory and return its path."""
    out_dir = tmp_path_factory.mktemp("dist")
    cmd = [
        "uv",
        "build",
        "--package",
        "studiobridge",
        "--wheel",
        "--out-dir",
        str(out_dir),
    ]
    res = subprocess.run(
        cmd,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"uv build failed: {res.stderr}\n{res.stdout}"

    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected 1 wheel, found {wheels}"
    yield wheels[0]


# req: PKG-01
def test_runtime_dependencies_zero_native(workspace_root: Path) -> None:
    """Verify runtime dependencies <= 8 and all are pure Python with zero native code."""
    pyproject_path = workspace_root / "packages" / "studiobridge" / "pyproject.toml"
    assert pyproject_path.exists(), f"Missing pyproject.toml at {pyproject_path}"

    with open(pyproject_path, encoding="utf-8") as f:
        doc = tomlkit.load(f)

    project_table = doc.get("project", {})
    deps = project_table.get("dependencies", [])

    # Runtime dependencies budget <= 8 per spec 11_l3_distribution_ci.md §2
    assert len(deps) <= 8, f"Too many runtime dependencies ({len(deps)} > 8): {deps}"

    # Verify expected pure Python packages
    dep_names = [dep.split(">")[0].split("=")[0].split("<")[0].strip().lower() for dep in deps]
    assert "anyio" in dep_names
    assert "platformdirs" in dep_names
    assert "tomlkit" in dep_names

    # Assert build backend is hatchling
    build_sys = doc.get("build-system", {})
    assert build_sys.get("build-backend") == "hatchling.build"


# req: PKG-01
def test_universal_wheel_tag(wheel_path: Path) -> None:
    """Verify built wheel is tagged as universal pure Python (py3-none-any)."""
    assert wheel_path.name.endswith("-py3-none-any.whl"), (
        f"Wheel {wheel_path.name} is not tagged py3-none-any"
    )

    with zipfile.ZipFile(wheel_path, "r") as zf:
        wheel_info_files = [n for n in zf.namelist() if n.endswith(".dist-info/WHEEL")]
        assert len(wheel_info_files) == 1
        wheel_text = zf.read(wheel_info_files[0]).decode("utf-8")
        assert "Root-Is-Purelib: true" in wheel_text
        assert "Tag: py3-none-any" in wheel_text


# req: PKG-01
def test_zero_native_binaries_in_wheel(wheel_path: Path) -> None:
    """Verify wheel contains zero native binaries or compiled extensions."""
    forbidden_exts = {".so", ".pyd", ".dll", ".dylib", ".exe", ".o", ".a", ".lib"}
    with zipfile.ZipFile(wheel_path, "r") as zf:
        for name in zf.namelist():
            ext = Path(name).suffix.lower()
            assert ext not in forbidden_exts, f"Wheel contains native binary: {name}"


# req: PKG-02
def test_package_data_inventory(wheel_path: Path) -> None:
    """Verify all required package data are included in the universal wheel."""
    with zipfile.ZipFile(wheel_path, "r") as zf:
        namelist = set(zf.namelist())

    # 1. Manifest fixtures
    assert "studiobridge/manifest/fixtures/api_v44.json" in namelist

    # 2. Quirks overlays
    assert "studiobridge/manifest/overlays/fl_quirks.yaml" in namelist

    # 3. Device script assets
    expected_device_assets = [
        "studiobridge/device/assets/device_entry.py",
        "studiobridge/device/assets/_sb_api.py",
        "studiobridge/device/assets/_sb_auth.py",
        "studiobridge/device/assets/_sb_core.py",
        "studiobridge/device/assets/_sb_json.py",
        "studiobridge/device/assets/_sb_wire.py",
    ]
    for asset in expected_device_assets:
        assert asset in namelist, f"Missing device asset in wheel: {asset}"

    # 4. Agent templates
    template_files = [n for n in namelist if n.startswith("studiobridge/agents/templates/")]
    assert len(template_files) >= 10, f"Expected >= 10 agent templates, got {len(template_files)}"
    assert "studiobridge/agents/templates/claude_code.json" in namelist
    assert "studiobridge/agents/templates/cursor.json" in namelist

    # 5. Bundled skill
    assert "studiobridge/agents/bundle/studiobridge/SKILL.md" in namelist
    assert "studiobridge/agents/bundle/studiobridge/AGENTS.md" in namelist
    assert "studiobridge/agents/bundle/studiobridge/references/api_search.md" in namelist
    assert "studiobridge/agents/bundle/studiobridge/references/modes.md" in namelist
    assert "studiobridge/agents/bundle/studiobridge/references/render_workflows.md" in namelist
    assert "studiobridge/agents/bundle/studiobridge/references/verified_writes.md" in namelist

    # 6. MCP schemas
    mcp_schemas = [
        n for n in namelist if n.startswith("studiobridge/mcp/schemas/") and n.endswith(".json")
    ]
    assert len(mcp_schemas) >= 20, f"Expected >= 20 MCP schemas, found {len(mcp_schemas)}"
    assert "studiobridge/mcp/schemas/channel_get.json" in namelist
    assert "studiobridge/mcp/schemas/mixer_get.json" in namelist

    # 7. Type markers and stubs
    assert "studiobridge/py.typed" in namelist
    assert "studiobridge/sdk/_generated/py.typed" in namelist
    assert "studiobridge/sdk/_generated/mixer.pyi" in namelist


# req: REG-01
def test_mcp_registry_server_json(workspace_root: Path) -> None:
    """Validate server.json structure, reverse-DNS naming, and package entries."""
    server_json_path = workspace_root / "server.json"
    assert server_json_path.exists(), f"Missing server.json at {server_json_path}"

    with open(server_json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Name must be reverse-DNS with exactly one '/'
    name = data.get("name", "")
    assert name == "io.github.wantedchip/studiobridge", f"Invalid name in server.json: {name}"
    assert name.count("/") == 1

    # Check packages array contains pypi and npm
    packages = data.get("packages", [])
    assert len(packages) >= 2
    types = {pkg.get("registryType") for pkg in packages}
    assert "pypi" in types
    assert "npm" in types

    for pkg in packages:
        assert pkg.get("identifier") == "studiobridge"
        assert pkg.get("version") == studiobridge.__version__
        assert pkg.get("transport", {}).get("type") == "stdio"

    # Environment variables documented
    env_vars = data.get("environmentVariables", {})
    assert "SBRIDGE_TOOLSETS" in env_vars
    assert "SBRIDGE_MODE" in env_vars


# req: REG-01
def test_ownership_tokens_consistency(workspace_root: Path) -> None:
    """Verify ownership tokens [REG-01] match across server.json, npm, and READMEs."""
    server_json_path = workspace_root / "server.json"
    npm_pkg_path = workspace_root / "npm" / "studiobridge" / "package.json"
    pkg_readme_path = workspace_root / "packages" / "studiobridge" / "README.md"
    root_readme_path = workspace_root / "README.md"

    with open(server_json_path, encoding="utf-8") as f:
        server_name = json.load(f)["name"]

    with open(npm_pkg_path, encoding="utf-8") as f:
        npm_mcp_name = json.load(f)["mcpName"]

    pkg_readme = pkg_readme_path.read_text(encoding="utf-8")
    root_readme = root_readme_path.read_text(encoding="utf-8")

    expected_token = f"<!-- mcp-name: {server_name} -->"

    assert npm_mcp_name == server_name, (
        f"npm mcpName '{npm_mcp_name}' does not match server.json name '{server_name}'"
    )
    assert expected_token in pkg_readme, (
        f"packages/studiobridge/README.md missing expected token: '{expected_token}'"
    )
    assert expected_token in root_readme, (
        f"root README.md missing expected token: '{expected_token}'"
    )


# req: NPM-01
def test_npm_package_json(workspace_root: Path) -> None:
    """Verify npm/studiobridge/package.json structure and version lockstep."""
    npm_pkg_path = workspace_root / "npm" / "studiobridge" / "package.json"
    assert npm_pkg_path.exists(), f"Missing package.json at {npm_pkg_path}"

    with open(npm_pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)

    assert pkg.get("name") == "studiobridge"
    assert pkg.get("version") == studiobridge.__version__

    bin_table = pkg.get("bin", {})
    assert bin_table.get("studiobridge") == "./bin/sbridge.js"
    assert bin_table.get("sbridge") == "./bin/sbridge.js"
    assert bin_table.get("studiobridge-mcp") == "./bin/sbridge.js"

    assert pkg.get("engines", {}).get("node") == ">=18"
    assert "bin/" in pkg.get("files", [])
    assert "README.md" in pkg.get("files", [])
    assert "LICENSE" in pkg.get("files", [])

    # No postinstall network downloads allowed
    scripts = pkg.get("scripts", {})
    assert "postinstall" not in scripts

    # Verify license file exists in npm folder
    assert (workspace_root / "npm" / "studiobridge" / "LICENSE").exists()


# req: NPM-02
def test_npm_launcher_source_and_stdio_discipline(workspace_root: Path) -> None:
    """Verify npm launcher bin/sbridge.js enforces strict stdio discipline."""
    script_path = workspace_root / "npm" / "studiobridge" / "bin" / "sbridge.js"
    assert script_path.exists(), f"Missing launcher script at {script_path}"

    content = script_path.read_text(encoding="utf-8")

    # Shebang check
    assert content.startswith("#!/usr/bin/env node")

    # Strict stdio discipline: MUST NEVER print to stdout
    assert "console.log" not in content, "Launcher must not call console.log (pollutes stdout)"
    assert "process.stdout.write" not in content, "Launcher must not write to process.stdout"

    # Confirm diagnostic writes use stderr
    assert "process.stderr.write" in content or "console.error" in content


# req: NPM-02
def test_npm_launcher_node_execution(workspace_root: Path) -> None:
    """Verify launcher syntax with node --check and test clean stdio execution."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js runtime not installed on host")

    script_path = workspace_root / "npm" / "studiobridge" / "bin" / "sbridge.js"

    # 1. Syntax check
    check_res = subprocess.run(
        [node_exe, "--check", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_res.returncode == 0, f"Node syntax error: {check_res.stderr}"

    # 2. Test SBRIDGE_PY_CMD passthrough stdio cleanliness
    env = os.environ.copy()
    env["SBRIDGE_PY_CMD"] = f"{sys.executable} -c \"import sys; sys.stdout.write('ok\\n')\""

    res = subprocess.run(
        [node_exe, str(script_path), "test"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    # stdout should contain ONLY the child output, no extra banners
    assert res.stdout.strip() == "ok"

    # 3. Test failure path with invalid PATH: diagnostics must go strictly to stderr, stdout empty
    empty_env = {
        "PATH": "",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
    }
    err_res = subprocess.run(
        [node_exe, str(script_path)],
        env=empty_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert err_res.returncode != 0
    # stdout MUST be completely empty!
    assert err_res.stdout == "", f"Stdout was polluted on error: {err_res.stdout}"
    assert "No compatible Python environment found" in err_res.stderr


# req: NPM-02
def test_npm_launcher_alias_forwarding(workspace_root: Path, tmp_path: Path) -> None:
    """Verify studiobridge-mcp alias prepends 'mcp' argument automatically."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js runtime not installed on host")

    orig_script = workspace_root / "npm" / "studiobridge" / "bin" / "sbridge.js"
    alias_script = tmp_path / "studiobridge-mcp.js"
    shutil.copy(orig_script, alias_script)

    env = os.environ.copy()
    env["SBRIDGE_PY_CMD"] = (
        f'{sys.executable} -c "import sys, json; print(json.dumps(sys.argv[1:]))"'
    )

    # Invocation without 'mcp' -> launcher should inject 'mcp'
    res1 = subprocess.run(
        [node_exe, str(alias_script), "--check"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res1.returncode == 0
    args1 = json.loads(res1.stdout.strip())
    assert args1 == ["mcp", "--check"]

    # Invocation with 'mcp' -> launcher should not duplicate 'mcp'
    res2 = subprocess.run(
        [node_exe, str(alias_script), "mcp", "--check"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res2.returncode == 0
    args2 = json.loads(res2.stdout.strip())
    assert args2 == ["mcp", "--check"]


# req: PKG-01
def test_sdist_packaging(workspace_root: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Verify source distribution includes required source files, README, and LICENSE."""
    import tarfile

    out_dir = tmp_path_factory.mktemp("sdist")
    cmd = [
        "uv",
        "build",
        "--package",
        "studiobridge",
        "--sdist",
        "--out-dir",
        str(out_dir),
    ]
    res = subprocess.run(
        cmd,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"uv sdist build failed: {res.stderr}\n{res.stdout}"

    tarballs = list(out_dir.glob("*.tar.gz"))
    assert len(tarballs) == 1, f"Expected 1 sdist tarball, found {tarballs}"

    with tarfile.open(tarballs[0], "r:gz") as tf:
        names = tf.getnames()
        # Find prefix (e.g. studiobridge-0.1.0/)
        assert any(n.endswith("/pyproject.toml") for n in names)
        assert any(n.endswith("/README.md") for n in names)
        assert any(n.endswith("/LICENSE") for n in names)
        assert any(n.endswith("/src/studiobridge/__init__.py") for n in names)
        assert any(n.endswith("/manifest/fixtures/api_v44.json") for n in names)
