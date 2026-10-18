"""Unit tests for Markdown API reference card generator and CLI integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.cli import ExitCode, cli_entry
from studiobridge.manifest.cards import (
    generate_all_cards,
    generate_card,
)
from studiobridge.manifest.drift import load_baseline_manifest
from studiobridge.manifest.schema import (
    FunctionDoc,
    Manifest,
)


@pytest.fixture
def baseline_manifest() -> Manifest:
    """Fixture providing the bundled api_v44 baseline manifest."""
    return load_baseline_manifest()


def test_generate_card_complete_function(baseline_manifest: Manifest) -> None:
    """Verify generated card for mixer.setTrackVolume has all required sections and formatting."""
    mod = baseline_manifest.modules["mixer"]
    fn = mod.functions["setTrackVolume"]

    card_md = generate_card("mixer", "setTrackVolume", fn, mod)

    # 1. Heading and Resource URI
    assert "# mixer.setTrackVolume" in card_md
    assert "**Resource URI:** `studio://api/mixer/setTrackVolume`" in card_md

    # 2. Signature block
    assert "```python" in card_md
    assert "def setTrackVolume(" in card_md
    assert "index: int" in card_md
    assert "volume: float" in card_md
    assert "pickupMode: int = 0" in card_md
    assert ") -> None: ..." in card_md

    # 3. Summary
    assert "## Summary" in card_md
    assert "Set output volume level for mixer track." in card_md

    # 4. Parameters table
    assert "## Parameters" in card_md
    assert "| `index` | `int` | No | `[0, 126]` | API v1 |" in card_md
    assert "| `volume` | `float` | No | `[0.0, 1.0]` | API v1 |" in card_md
    assert "| `pickupMode` | `int` | Yes |" in card_md

    # 5. Return value
    assert "## Return Value" in card_md
    assert "- **Type:** `None`" in card_md

    # 6. Metadata
    assert "## Metadata" in card_md
    assert "| Since API Version | API v1 |" in card_md
    assert "| Mutating | Yes |" in card_md
    assert "| Protected | No |" in card_md
    assert (
        "| Verification | getter: `getTrackVolume`, compare: `approx`, settle: `idle1`" in card_md
    )
    assert "| Execution Plane | `live` |" in card_md


def test_generate_card_no_parameters(baseline_manifest: Manifest) -> None:
    """Verify function without parameters outputs clean 'takes no parameters' note."""
    mod = baseline_manifest.modules["mixer"]
    fn = mod.functions["trackCount"]

    card_md = generate_card("mixer", "trackCount", fn, mod)
    assert "# mixer.trackCount" in card_md
    assert "**Resource URI:** `studio://api/mixer/trackCount`" in card_md
    assert "This function takes no parameters." in card_md
    assert "- **Type:** `int`" in card_md
    assert "| Mutating | No |" in card_md


def test_generate_card_undocumented_and_deprecated() -> None:
    """Verify cards accurately render flags for undocumented or deprecated/missing functions."""
    fn_doc = FunctionDoc(
        name="internalDebugCmd",
        since=10,
        ret="bool",
        undocumented=True,
        present_in_build=False,
    )

    card_md = generate_card("system", "internalDebugCmd", fn_doc)
    assert "# system.internalDebugCmd" in card_md
    assert "| Undocumented | Yes (discovered via runtime introspection) |" in card_md
    assert "| Present in Build | No (deprecated or missing in current runtime) |" in card_md


def test_generate_all_cards_memory(baseline_manifest: Manifest) -> None:
    """Verify generate_all_cards generates all 119 functions and supports transparent lookup."""
    cards = generate_all_cards(baseline_manifest)

    assert len(cards) == 119

    # Access via canonical URI
    uri = "studio://api/mixer/setTrackVolume"
    assert uri in cards
    card_by_uri = cards[uri]
    assert "# mixer.setTrackVolume" in card_by_uri

    # Access via dot notation
    card_by_dot = cards["mixer.setTrackVolume"]
    assert card_by_dot == card_by_uri

    # Access via path notation
    card_by_path = cards["mixer/setTrackVolume"]
    assert card_by_path == card_by_uri


def test_generate_all_cards_to_disk(tmp_path: Path, baseline_manifest: Manifest) -> None:
    """Verify generate_all_cards writes Markdown files organized by module directory."""
    out_dir = tmp_path / "docs_api"
    cards = generate_all_cards(baseline_manifest, output_dir=out_dir)

    assert len(cards) == 119
    assert out_dir.is_dir()

    # Check mixer directory and card
    mixer_dir = out_dir / "mixer"
    assert mixer_dir.is_dir()

    set_vol_file = mixer_dir / "setTrackVolume.md"
    assert set_vol_file.is_file()

    content = set_vol_file.read_text(encoding="utf-8")
    assert content == cards["studio://api/mixer/setTrackVolume"]


def test_cli_manifest_cards(capsys) -> None:
    """Verify CLI `sbridge manifest cards` outputs summary message."""
    code = cli_entry(["manifest", "cards"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    assert "Generated 119 API reference cards for 8 modules." in captured.out


def test_cli_manifest_cards_with_out_and_json(tmp_path: Path, capsys) -> None:
    """Verify CLI `sbridge manifest cards --out <dir> --json` writes cards and outputs JSON."""
    out_dir = tmp_path / "cards_out"
    code = cli_entry(["manifest", "cards", "--out", str(out_dir), "--json"])
    assert code == ExitCode.OK

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["api_version"] == 44
    assert data["total_cards"] == 119
    assert data["output_dir"] == str(out_dir)
    assert len(data["uris"]) == 119

    # Confirm files written to disk
    assert (out_dir / "mixer" / "setTrackVolume.md").is_file()
    assert (out_dir / "channels" / "channelCount.md").is_file()
