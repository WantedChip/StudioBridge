"""End-to-end live FL Studio project load verification and pre-release test suite.

Runs headless render preflight (FL64.exe /R /Ewav) via the FL-load test harness
for every stock seed template and mutated golden output project before release.
Decorated with @pytest.mark.live, these tests are cleanly skipped if FL Studio
is not installed on the host.

# req: FLP-50
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.cli.main import cli_entry
from studiobridge.core.errors import FlInstallNotFoundError
from studiobridge.flp.templates.instantiator import (
    get_seed_path,
    instantiate_channel,
    instantiate_project,
    list_seed_templates,
)
from studiobridge.flp.validate.fl_load import FlLoadHarness
from studiobridge.render.discover import FlDiscovery, FlInstall


def _get_live_fl_install() -> FlInstall | None:
    """Resolve FL Studio installation if present on host, else None."""
    discovery = FlDiscovery()
    try:
        install = discovery.resolve_install()
        if install.exe_path.is_file():
            return install
    except FlInstallNotFoundError:
        pass
    except Exception:
        pass
    return None


@pytest.fixture
def live_fl_install() -> FlInstall:
    """Ensure a real FL Studio installation is present on host or skip cleanly."""
    install = _get_live_fl_install()
    if install is None:
        pytest.skip(
            "Live test skipped: FL Studio executable (FL64.exe) is not installed on this host."
        )
    return install


@pytest.mark.live
def test_all_seed_templates_fl_load_validation(live_fl_install: FlInstall) -> None:
    """Every clean-room stock seed template must open cleanly in FL Studio without freeze or crash.

    # req: FLP-50
    """
    seeds = list_seed_templates()
    assert len(seeds) >= 6, "Expected at least 6 baseline seed templates"

    harness = FlLoadHarness(fl_install=live_fl_install)

    for seed_name in seeds:
        seed_path = get_seed_path(seed_name)
        assert seed_path.is_file(), f"Seed template file not found: {seed_path}"

        result = harness.run(seed_path, timeout_s=30.0)
        assert result.outcome == "ok", (
            f"Seed template '{seed_name}' failed headless FL-load verification: "
            f"outcome={result.outcome}, exit_code={result.exit_code}, "
            f"dialog='{result.dialog_title}', error='{result.error_message}'"
        )
        assert result.is_ok is True
        assert result.dialog_title is None


@pytest.mark.live
def test_mutated_golden_output_fl_load_validation(
    live_fl_install: FlInstall, tmp_path: Path
) -> None:
    """Mutated projects generated via templates and edits must pass headless load validation.

    # req: FLP-50
    """
    # 1. Author a mutated project with added channels and notes
    proj = instantiate_project("minimal")
    proj.title = "Live Preflight Golden Project"
    proj.tempo = 128.0

    instantiate_channel(proj, "sampler", {"name": "Main Kick", "target_mixer_track": 1})
    instantiate_channel(proj, "3x_osc", {"name": "Lead Synth", "target_mixer_track": 2})

    golden_flp = tmp_path / "golden_mutated.flp"
    proj.save_as(golden_flp)

    harness = FlLoadHarness(fl_install=live_fl_install)
    result = harness.run(golden_flp, timeout_s=30.0)

    assert result.outcome == "ok", (
        f"Mutated golden project failed headless load validation: outcome={result.outcome}, "
        f"dialog='{result.dialog_title}', error='{result.error_message}'"
    )
    assert result.is_ok is True


@pytest.mark.live
def test_cli_flp_validate_in_fl_live(
    live_fl_install: FlInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    """`sbridge flp validate <seed> --in-fl` CLI pre-release gate check.

    # req: FLP-50
    """
    seed_path = get_seed_path("minimal")
    code = cli_entry(["flp", "validate", str(seed_path), "--in-fl", "--json"])
    assert code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["invariants"]["valid"] is True
    assert payload["risk"]["is_safe_to_load"] is True
    assert payload["fl_load"] is not None
    assert payload["fl_load"]["outcome"] == "ok"
