"""Smoke tests verifying package import, version exposure, and submodule structure."""

import importlib

import pytest

import studiobridge


def test_package_version() -> None:
    """Verify package version is exposed and matches expected scaffold version."""
    # req: REPO-01
    assert hasattr(studiobridge, "__version__")
    assert studiobridge.__version__ == "0.1.0"


def test_submodules_exist() -> None:
    """Verify architectural submodules exist."""
    # req: REPO-01
    submodules = [
        "studiobridge.core",
        "studiobridge.wire",
        "studiobridge.ports",
        "studiobridge.broker",
        "studiobridge.device",
        "studiobridge.manifest",
        "studiobridge.pianoroll",
        "studiobridge.actuate",
        "studiobridge.render",
        "studiobridge.flp",
        "studiobridge.setup",
        "studiobridge.sdk",
        "studiobridge.mcp",
        "studiobridge.cli",
        "studiobridge.http",
        "studiobridge.agents",
    ]
    for mod_name in submodules:
        mod = importlib.import_module(mod_name)
        assert mod is not None


def test_core_isolation() -> None:
    """Verify core submodule can be imported independently."""
    # req: REPO-01
    core_mod = importlib.import_module("studiobridge.core")
    assert core_mod is not None


@pytest.mark.winmm
def test_winmm_marker_configured() -> None:
    """Verify winmm marker is registered and functional."""
    # req: REPO-01
    pass


@pytest.mark.live
def test_live_marker_configured() -> None:
    """Verify live marker is registered (skipped by default in regular test runs)."""
    # req: REPO-01
    pass
