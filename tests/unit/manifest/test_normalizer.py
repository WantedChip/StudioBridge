"""Tests for manifest signature normalizer, type inference, AST parsing, and scraper."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from studiobridge.manifest.normalizer import (
    infer_arg_range,
    infer_arg_type,
    infer_ret_type,
    normalize_manifest,
    normalize_raw_module,
    parse_python_signature,
    resolve_type_alias,
)
from studiobridge.manifest.schema import Manifest
from studiobridge.manifest.scraper import (
    ScraperError,
    fetch_or_cache,
    generate_original_summary,
    parse_html_table_doc,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "packages"
    / "studiobridge"
    / "src"
    / "studiobridge"
    / "manifest"
    / "fixtures"
)


class TestTypeInferenceAndAliases:
    """Tests for type alias resolution and argument/return type inference."""

    @pytest.mark.parametrize(
        ("raw_alias", "expected"),
        [
            ("int", "int"),
            ("integer", "int"),
            ("long", "int"),
            ("short", "int"),
            ("float", "float"),
            ("double", "float"),
            ("real", "float"),
            ("bool", "bool"),
            ("boolean", "bool"),
            ("str", "str"),
            ("string", "str"),
            ("text", "str"),
            ("bytes", "bytes"),
            ("bytearray", "bytes"),
            ("none", "none"),
            ("void", "none"),
            ("enum", "enum"),
            ("flags", "flags"),
        ],
    )
    def test_resolve_type_alias(self, raw_alias: str, expected: str) -> None:
        assert resolve_type_alias(raw_alias) == expected

    def test_resolve_type_alias_substring_and_fallback(self) -> None:
        assert resolve_type_alias("typing.Optional[int]") == "int"
        assert resolve_type_alias("custom_unknown_field") == "int"

    def test_infer_arg_type(self) -> None:
        assert infer_arg_type("index") == "int"
        assert infer_arg_type("trackNum") == "int"
        assert infer_arg_type("volume") == "float"
        assert infer_arg_type("pan") == "float"
        assert infer_arg_type("pitch") == "float"
        assert infer_arg_type("isMuted") == "bool"
        assert infer_arg_type("hasHeader") == "bool"
        assert infer_arg_type("enabled") == "bool"
        assert infer_arg_type("name") == "str"
        assert infer_arg_type("sysexData") == "bytes"
        assert infer_arg_type("unknown_param") == "int"
        # From defaults
        assert infer_arg_type("custom", default=1.5) == "float"
        assert infer_arg_type("custom", default=True) == "bool"
        assert infer_arg_type("custom", default=10) == "int"
        assert infer_arg_type("custom", default="hello") == "str"
        assert infer_arg_type("custom", default=b"abc") == "bytes"

    def test_infer_arg_range(self) -> None:
        assert infer_arg_range("mixer", "setTrackVolume", "volume", "float") == [0.0, 1.0]
        assert infer_arg_range("mixer", "setTrackPan", "pan", "float") == [-1.0, 1.0]
        assert infer_arg_range("mixer", "setTrackVolume", "index", "int") == [0, 126]
        assert infer_arg_range("patterns", "jumpToPattern", "index", "int") == [1, 999]
        assert infer_arg_range("channels", "selectChannel", "index", "int") == [0, 999]
        assert infer_arg_range("general", "saveUndo", "name", "str") is None

    def test_infer_ret_type(self) -> None:
        assert infer_ret_type("isPlaying") == "bool"
        assert infer_ret_type("hasWindow") == "bool"
        assert infer_ret_type("canRecord") == "bool"
        assert infer_ret_type("trackCount") == "int"
        assert infer_ret_type("getTrackNumber") == "int"
        assert infer_ret_type("getRecPPQ") == "int"
        assert infer_ret_type("getTrackColor") == "int"
        assert infer_ret_type("getPortNumber") == "int"
        assert infer_ret_type("getTrackVolume") == "float"
        assert infer_ret_type("getTrackPan") == "float"
        assert infer_ret_type("getPlaybackSpeed") == "float"
        assert infer_ret_type("getTrackName") == "str"
        assert infer_ret_type("setTrackVolume") == "none"
        assert infer_ret_type("start") == "none"
        assert infer_ret_type("stop") == "none"
        assert infer_ret_type("muteTrack") == "none"
        assert infer_ret_type("soloTrack") == "none"
        assert infer_ret_type("selectChannel") == "none"
        assert infer_ret_type("customUnknown") == "none"
        assert infer_ret_type("customFn", raw_return="bool") == "bool"


class TestASTSignatureParsing:
    """Tests for Python AST-based signature parsing."""

    def test_parse_python_signature_simple(self) -> None:
        sig = "def setTrackVolume(index: int, volume: float) -> None:"
        name, args, ret = parse_python_signature(sig)
        assert name == "setTrackVolume"
        assert ret == "none"
        assert len(args) == 2
        assert args[0].name == "index"
        assert args[0].type == "int"
        assert not args[0].optional
        assert args[1].name == "volume"
        assert args[1].type == "float"

    def test_parse_python_signature_without_def(self) -> None:
        sig = "getTrackVolume(index: int) -> float"
        name, args, ret = parse_python_signature(sig)
        assert name == "getTrackVolume"
        assert ret == "float"
        assert len(args) == 1
        assert args[0].name == "index"

    def test_parse_python_signature_with_defaults(self) -> None:
        sig = "def muteTrack(index: int, value: int = -1) -> None:"
        name, args, ret = parse_python_signature(sig)
        assert name == "muteTrack"
        assert len(args) == 2
        assert args[1].name == "value"
        assert args[1].optional is True
        assert args[1].default == -1


class TestHTMLScraperAndOriginalSummary:
    """Tests for HTML parsing, cache isolation, and [LEGAL-01] original summaries."""

    def test_original_summary_generation_branches(self) -> None:
        assert (
            "track volume"
            in generate_original_summary("mixer", "getTrackVolume", ["index"], "float").lower()
        )
        assert (
            "track volume"
            in generate_original_summary(
                "mixer", "setTrackVolume", ["index", "volume"], "none"
            ).lower()
        )
        assert (
            "is active or true"
            in generate_original_summary("transport", "isPlaying", [], "bool").lower()
        )
        assert "total count" in generate_original_summary("mixer", "trackCount", [], "int").lower()
        assert (
            "mute state"
            in generate_original_summary("mixer", "muteTrack", ["index"], "none").lower()
        )
        assert (
            "solo state"
            in generate_original_summary("mixer", "soloTrack", ["index"], "none").lower()
        )
        assert (
            "select the active"
            in generate_original_summary("channels", "selectChannel", ["index"], "none").lower()
        )
        assert (
            "transport command"
            in generate_original_summary("transport", "start", [], "none").lower()
        )
        assert "history action" in generate_original_summary("general", "undo", [], "none").lower()
        assert (
            "show the specified"
            in generate_original_summary("ui", "showWindow", ["window"], "none").lower()
        )
        assert (
            "execute custom action"
            in generate_original_summary("general", "customAction", [], "none").lower()
        )

    def test_html_table_parsing(self) -> None:
        sample_html = """
        <html>
        <body>
            <table>
                <tr>
                    <th>Syntax</th>
                    <th>Description</th>
                    <th>Return</th>
                    <th>API Version</th>
                </tr>
                <tr>
                    <td>setTrackVolume(index, volume, pickupMode=0)</td>
                    <td>Sets track volume.</td>
                    <td>None</td>
                    <td>1</td>
                </tr>
                <tr>
                    <td>getTrackVolume(index)</td>
                    <td>Gets track volume.</td>
                    <td>float</td>
                    <td>1</td>
                </tr>
                <tr>
                    <td>SOME_FLAG = 42</td>
                    <td>A constant flag.</td>
                    <td>int</td>
                    <td>1</td>
                </tr>
            </table>
        </body>
        </html>
        """
        raw_mod = parse_html_table_doc(sample_html, "mixer", default_since=1)
        assert raw_mod.name == "mixer"
        assert len(raw_mod.functions) == 2
        assert raw_mod.constants.get("SOME_FLAG") == 42

        f_set = next(f for f in raw_mod.functions if f.name == "setTrackVolume")
        assert len(f_set.raw_args) == 3
        assert f_set.raw_args[2]["name"] == "pickupMode"
        assert f_set.raw_args[2]["optional"] == "true"

        f_get = next(f for f in raw_mod.functions if f.name == "getTrackVolume")
        assert f_get.raw_return == "float"

        # Normalize module
        mod_doc = normalize_raw_module(raw_mod)
        assert "setTrackVolume" in mod_doc.functions
        assert "getTrackVolume" in mod_doc.functions
        assert mod_doc.functions["getTrackVolume"].mutating is False
        assert mod_doc.functions["setTrackVolume"].mutating is True
        assert mod_doc.functions["setTrackVolume"].verify is not None
        assert mod_doc.functions["setTrackVolume"].verify.getter == "getTrackVolume"

    def test_html_table_with_br_and_unusual_rows(self) -> None:
        sample_html = """
        <table>
            <tr><td>trackCount<br>(mode=0)</td><td>Returns count</td></tr>
        </table>
        """
        raw_mod = parse_html_table_doc(sample_html, "mixer")
        assert len(raw_mod.functions) == 1
        assert raw_mod.functions[0].name == "trackCount"

    def test_per_argument_version_footnote_parsing(self) -> None:
        sample_html = """
        <table>
            <tr><td>Syntax</td><td>Desc</td></tr>
            <tr>
                <td>setTrackVolume(index, volume, pickupMode [API 16])</td>
                <td>Set volume</td>
            </tr>
        </table>
        """
        raw_mod = parse_html_table_doc(sample_html, "mixer")
        mod_doc = normalize_raw_module(raw_mod)
        fn = mod_doc.functions["setTrackVolume"]
        pickup_arg = next(a for a in fn.args if a.name == "pickupMode")
        assert pickup_arg.since == 16

    def test_cache_strictly_in_cache_dir(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / ".cache" / "manifest_html"
        dummy_url = "https://example.invalid/fl_scripting_test.html"

        import hashlib

        cache_dir.mkdir(parents=True, exist_ok=True)
        url_hash = hashlib.sha256(dummy_url.encode("utf-8")).hexdigest()[:16]
        cache_file = cache_dir / f"fl_scripting_test_html_{url_hash}.html"
        cache_file.write_text("<table><tr><td>dummy()</td></tr></table>", encoding="utf-8")

        result = fetch_or_cache(dummy_url, cache_dir=cache_dir)
        assert "dummy()" in result
        assert cache_file.exists()
        assert ".cache" in str(cache_file)

    def test_fetch_or_cache_network_error_raises_scraper_error(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / ".cache" / "manifest_html"
        dummy_url = "https://example.invalid/not_cached.html"
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("Connection refused"),
            ),
            pytest.raises(ScraperError, match="Failed to fetch"),
        ):
            fetch_or_cache(dummy_url, cache_dir=cache_dir)


class TestNormalizationDeterminism:
    """Tests guaranteeing that normalizer produces byte-identical output across repeated runs."""

    def test_repeated_runs_produce_byte_identical_json(self) -> None:
        fixture_path = FIXTURES_DIR / "api_v44.json"
        raw_text = fixture_path.read_text(encoding="utf-8")
        raw_dict = json.loads(raw_text)

        run1 = normalize_manifest(raw_dict).to_json(indent=2)
        run2 = normalize_manifest(raw_dict).to_json(indent=2)
        run3 = normalize_manifest(json.loads(run1)).to_json(indent=2)

        assert run1 == run2, "Normalizer output varied between run 1 and run 2"
        assert run2 == run3, "Normalizer output varied between run 2 and run 3"
        assert run1 == raw_text, "Normalizer output differs from saved reference fixture"

    def test_normalize_manifest_types(self) -> None:
        m = Manifest(api_version=44)
        assert normalize_manifest(m) is m

        with pytest.raises(TypeError, match="Unsupported input type"):
            normalize_manifest(12345)  # type: ignore

    def test_sorting_determinism(self) -> None:
        unsorted_dict = {
            "api_version": 44,
            "modules": {
                "ui": {
                    "functions": {
                        "showWindow": {"since": 1, "args": [], "ret": "none", "mutating": True},
                        "getFocused": {"since": 1, "args": [], "ret": "bool", "mutating": False},
                    }
                },
                "channels": {
                    "functions": {
                        "selectChannel": {"since": 1, "args": [], "ret": "none", "mutating": True},
                        "channelCount": {"since": 1, "args": [], "ret": "int", "mutating": False},
                    }
                },
            },
            "callbacks": {
                "OnSysEx": {"since": 1},
                "OnInit": {"since": 1},
            },
            "flags": {
                "FPT_Stop": 105,
                "FPT_Play": 104,
            },
        }

        m1 = normalize_manifest(unsorted_dict)
        json1 = m1.to_json(indent=2)

        m2 = normalize_manifest(unsorted_dict)
        json2 = m2.to_json(indent=2)

        assert json1 == json2

        mod_keys = list(m1.to_dict()["modules"].keys())
        assert mod_keys == ["channels", "ui"]

        fn_keys = list(m1.to_dict()["modules"]["channels"]["functions"].keys())
        assert fn_keys == ["channelCount", "selectChannel"]

        cb_keys = list(m1.to_dict()["callbacks"].keys())
        assert cb_keys == ["OnInit", "OnSysEx"]

        fl_keys = list(m1.to_dict()["flags"].keys())
        assert fl_keys == ["FPT_Play", "FPT_Stop"]
