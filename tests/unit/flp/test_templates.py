"""Unit tests for FLP seed templates, project instantiation, and stock fragment library.

Verifies:
- All 6 baseline seed templates exist, load, and pass invariant validation (# req: FLP-40).
- Seed hash verification and corruption detection (# req: FLP-40, PKG-02).
- Fresh project instantiation and parameter overrides (# req: FLP-40).
- Stock fragment indexing, relocation rules, and opaque plugin blob preservation
  (# req: FLP-21, FLP-40).
- Structured E_UNAVAILABLE errors with actionable remedy for missing fragments (# req: FLP-40).
- Semi-automatic fragment extraction and provenance metadata recording (# req: FLP-40, FLP-60).
- CLI commands: `sbridge flp new`, `sbridge flp template list`, `sbridge flp template add`
  (# req: FLP-40).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from studiobridge.cli.commands.flp_template import handle_flp_template
from studiobridge.core.errors import TemplateFragmentUnavailableError
from studiobridge.flp import (
    Project,
    check_invariants,
    instantiate,
    instantiate_channel,
    instantiate_project,
    validate_invariants,
)
from studiobridge.flp.templates.instantiator import (
    TemplateLibrary,
    get_seed_path,
    list_seed_templates,
    verify_seed_integrity,
)

# =============================================================================
# 1. Baseline Seed Templates & Integrity Tests
# =============================================================================


def test_seed_templates_exist_and_load() -> None:
    """Verify all 6 seed templates exist in package data and load cleanly (# req: FLP-40)."""
    expected_seeds = [
        "audio_clip",
        "automation",
        "layer",
        "minimal",
        "one_each_stock",
        "sampler",
    ]
    available = list_seed_templates()
    for name in expected_seeds:
        assert name in available, f"Seed template '{name}' missing from {available}"

        seed_file = get_seed_path(name)
        assert seed_file.is_file(), f"Seed file {seed_file} does not exist"

        project = Project.load(seed_file)
        assert project.version.startswith("26.")
        assert project.ppq == 96
        assert project.tempo == 120.0

        # Structural invariants must hold strictly
        violations = validate_invariants(project)
        assert violations == [], f"Seed '{name}' has invariant violations: {violations}"


def test_seed_hash_verification() -> None:
    """Verify cryptographic SHA-256 integrity of bundled seed files (# req: FLP-40, PKG-02)."""
    assert verify_seed_integrity(), "verify_seed_integrity() failed on bundled seeds"


def test_seed_hash_verification_detects_corruption(tmp_path: Path) -> None:
    """Verify hash check detects corrupted or missing seed files (# req: FLP-40)."""
    # Create fake directory with corrupted seed
    fake_seeds = tmp_path / "seeds"
    fake_seeds.mkdir()

    hashes = {"corrupted.flp": "a" * 64}
    (fake_seeds / "hashes.json").write_text(json.dumps(hashes), encoding="utf-8")
    (fake_seeds / "corrupted.flp").write_bytes(b"not the right hash")

    assert not verify_seed_integrity(fake_seeds)


# =============================================================================
# 2. Project Instantiation Tests
# =============================================================================


def test_instantiate_minimal_project() -> None:
    """Verify fresh project creation from minimal seed template (# req: FLP-40)."""
    project = instantiate(
        "minimal",
        {
            "title": "Clean Slate",
            "author": "Producer",
            "comments": "Testing instantiation",
            "tempo": 128.0,
        },
    )

    assert project.title == "Clean Slate"
    assert project.author == "Producer"
    assert project.comments == "Testing instantiation"
    assert project.tempo == 128.0
    assert len(project.channels) == 0
    assert len(project.patterns) == 1

    violations = validate_invariants(project)
    assert violations == []


def test_instantiate_all_seed_templates() -> None:
    """Verify instantiating each of the 6 seed templates conforms to schema (# req: FLP-40)."""
    seeds = ["minimal", "sampler", "audio_clip", "layer", "automation", "one_each_stock"]
    for s in seeds:
        proj = instantiate(s)
        assert proj is not None
        violations = validate_invariants(proj)
        assert violations == [], f"Instantiated project '{s}' failed invariants: {violations}"


def test_instantiate_with_extra_channels_in_params() -> None:
    """Verify instantiating a project with channels specified in params (# req: FLP-40)."""
    proj = instantiate(
        "minimal",
        {
            "title": "Multi-Instrument",
            "tempo": 140.0,
            "channels": [
                "sampler",
                {"kind": "3x_osc", "name": "Lead Synth", "target_mixer_track": 1},
                {"kind": "audio_clip", "name": "Vocal Chop", "target_mixer_track": 2},
            ],
        },
    )

    assert len(proj.channels) == 3
    assert proj.channels[0].name == "Sampler"
    assert proj.channels[0].index == 0
    assert proj.channels[1].name == "Lead Synth"
    assert proj.channels[1].index == 1
    assert proj.channels[1].target_mixer_track == 1
    assert proj.channels[2].name == "Vocal Chop"
    assert proj.channels[2].index == 2
    assert proj.channels[2].target_mixer_track == 2

    violations = validate_invariants(proj)
    assert violations == []


def test_project_new_classmethod() -> None:
    """Verify Project.new() classmethod convenience wrapper (# req: FLP-40)."""
    p = Project.new("sampler", title="Sampler Beat", tempo=115.0)
    assert p.title == "Sampler Beat"
    assert p.tempo == 115.0
    assert len(p.channels) == 1
    assert p.channels[0].name == "Sampler"
    assert validate_invariants(p) == []


# =============================================================================
# 3. Fragment Relocation & Opaque Preservation Tests
# =============================================================================


def test_instantiate_channel_stock_fragments() -> None:
    """Verify adding stock fragments to an existing project relocates IDs (# req: FLP-40)."""
    project = instantiate("minimal")
    assert len(project.channels) == 0

    # 1. Add Sampler
    ch0 = instantiate_channel(project, "sampler", {"name": "Kick Drum"})
    assert ch0.index == 0
    assert ch0.name == "Kick Drum"
    assert len(project.channels) == 1

    # 2. Add 3x Osc with plugin state
    ch1 = instantiate_channel(
        project,
        "3x_osc",
        {"name": "Sub Bass", "target_mixer_track": 3},
    )
    assert ch1.index == 1
    assert ch1.name == "Sub Bass"
    assert ch1.channel_type == "plugin"
    assert ch1.target_mixer_track == 3
    assert ch1.plugin is not None
    assert b"3x Osc" in ch1.plugin.data  # Preserved opaque blob intact
    assert len(project.channels) == 2

    # 3. Add Fruity Parametric EQ 2
    ch2 = instantiate_channel(
        project,
        "fruity_parametric_eq_2",
        {"name": "Master EQ"},
    )
    assert ch2.index == 2
    assert ch2.name == "Master EQ"
    assert ch2.plugin is not None
    assert b"EQ2" in ch2.plugin.data  # Preserved opaque blob intact
    assert len(project.channels) == 3

    # Check structural schema invariants
    check_invariants(project)
    assert validate_invariants(project) == []


def test_opaque_plugin_bytes_verbatim_preservation() -> None:
    """Verify opaque plugin wrapper blobs are preserved 100% byte-for-byte (# req: FLP-21)."""
    frag = TemplateLibrary.get_fragment(kind="3x_osc")
    assert frag is not None

    orig_plugin_event = next(e for e in frag.events if e.id == 213)
    orig_bytes = orig_plugin_event.raw

    p = instantiate("minimal")
    ch = instantiate_channel(p, "3x_osc", {"name": "Test Osc"})
    assert ch.plugin is not None
    assert ch.plugin.data == orig_bytes


def test_instantiate_with_project_argument() -> None:
    """Verify instantiate(kind, project=p) adds channel and returns project (# req: FLP-40)."""
    p = instantiate("minimal")
    ret = instantiate("layer", {"name": "Layer Bus"}, project=p)
    assert ret is p
    assert len(p.channels) == 1
    assert p.channels[0].name == "Layer Bus"
    assert validate_invariants(p) == []


def test_project_add_channel_from_template_method() -> None:
    """Verify Project.add_channel_from_template method (# req: FLP-40)."""
    p = Project.new("minimal")
    ch = p.add_channel_from_template("audio_clip", name="Impact FX", target_mixer_track=5)
    assert ch.index == 0
    assert ch.name == "Impact FX"
    assert ch.target_mixer_track == 5
    assert len(p.channels) == 1
    assert validate_invariants(p) == []


# =============================================================================
# 4. Error Handling & E_UNAVAILABLE Tests
# =============================================================================


def test_missing_fragment_raises_unavailable_with_remedy() -> None:
    """Verify requesting an unavailable fragment raises E_UNAVAILABLE with remedy."""
    project = instantiate("minimal")

    with pytest.raises(TemplateFragmentUnavailableError) as exc_info:
        instantiate_channel(project, "serum_synth")

    err = exc_info.value
    assert err.code == "E_UNAVAILABLE"
    assert "serum_synth" in str(err)
    assert err.remedy is not None
    assert "sbridge flp template add" in err.remedy


def test_missing_template_raises_unavailable() -> None:
    """Verify instantiating a non-existent template raises E_UNAVAILABLE (# req: FLP-40)."""
    with pytest.raises(TemplateFragmentUnavailableError) as exc_info:
        instantiate_project("non_existent_template")

    err = exc_info.value
    assert err.code == "E_UNAVAILABLE"
    assert "non_existent_template" in str(err)
    assert err.remedy is not None


# =============================================================================
# 5. Fragment Extraction & Provenance Tests
# =============================================================================


def test_extract_fragment_from_project(tmp_path: Path) -> None:
    """Verify extracting a channel fragment records provenance and registers it (# req: FLP-40)."""
    stock_path = get_seed_path("one_each_stock")
    stock_proj = Project.load(stock_path)

    # Extract 3x Osc from channel index 3
    frag = TemplateLibrary.extract_fragment(
        stock_proj,
        channel_index=3,
        name="Custom 3x Osc",
        author="Lead Designer",
        kind="plugin",
    )

    assert frag.name == "Custom 3x Osc"
    assert frag.kind == "plugin"
    assert frag.provenance.author == "Lead Designer"
    assert frag.provenance.fl_version == "26.1.0"
    assert "one_each_stock.flp" in frag.provenance.source_file
    assert frag.provenance.date is not None

    # Check it can be looked up and instantiated into a fresh project
    target_proj = instantiate("minimal")
    new_ch = instantiate_channel(target_proj, "Custom 3x Osc", {"name": "Imported Lead"})
    assert new_ch.name == "Imported Lead"
    assert new_ch.channel_type == "plugin"
    assert new_ch.plugin is not None
    assert validate_invariants(target_proj) == []


# =============================================================================
# 6. CLI Command Tests
# =============================================================================


def test_cli_flp_template_list_text(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sbridge flp template list` text output (# req: FLP-40)."""
    args = argparse.Namespace(flp_template_action="list", json=False)
    code = handle_flp_template(args)
    assert code == 0

    captured = capsys.readouterr()
    assert "Baseline Seed Templates:" in captured.out
    assert "minimal" in captured.out
    assert "one_each_stock" in captured.out
    assert "Stock Fragment Library:" in captured.out
    assert "3x Osc" in captured.out


def test_cli_flp_template_list_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sbridge flp template list --json` output (# req: FLP-40)."""
    args = argparse.Namespace(flp_template_action="list", json=True)
    code = handle_flp_template(args)
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert isinstance(data["templates"], list)
    assert isinstance(data["fragments"], list)
    template_names = [t["name"] for t in data["templates"]]
    assert "minimal" in template_names
    assert "one_each_stock" in template_names


def test_cli_flp_new(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sbridge flp new` creates functional project (# req: FLP-40)."""
    out_file = tmp_path / "song.flp"
    args = argparse.Namespace(
        flp_template_action="new",
        output=str(out_file),
        template="minimal",
        title="CLI Beat",
        author="Tester",
        tempo=132.0,
        comments="Generated via test",
        force=False,
        json=False,
    )
    code = handle_flp_template(args)
    assert code == 0
    assert out_file.is_file()

    # Re-parse generated file and verify
    reparsed = Project.load(out_file)
    assert reparsed.title == "CLI Beat"
    assert reparsed.author == "Tester"
    assert reparsed.tempo == 132.0
    assert validate_invariants(reparsed) == []

    captured = capsys.readouterr()
    assert "Created project 'song.flp' from template 'minimal'" in captured.out


def test_cli_flp_new_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sbridge flp new --json` output format (# req: FLP-40)."""
    out_file = tmp_path / "song_json.flp"
    args = argparse.Namespace(
        flp_template_action="new",
        output=str(out_file),
        template="sampler",
        title="JSON Track",
        tempo=124.0,
        force=False,
        json=True,
    )
    code = handle_flp_template(args)
    assert code == 0
    assert out_file.is_file()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["template"] == "sampler"
    assert data["title"] == "JSON Track"
    assert data["tempo"] == 124.0
    assert data["channels"] == 1


def test_cli_flp_template_add(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sbridge flp template add <flp> --select channel:0` (# req: FLP-40)."""
    stock_path = get_seed_path("sampler")
    args = argparse.Namespace(
        flp_template_action="add",
        file=str(stock_path),
        select="channel:0",
        name="Extracted Sampler",
        kind="sampler",
        author="Test Creator",
        json=True,
    )
    code = handle_flp_template(args)
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "ok"
    assert data["channel_index"] == 0
    assert data["fragment"]["name"] == "Extracted Sampler"
    assert data["fragment"]["provenance"]["author"] == "Test Creator"
