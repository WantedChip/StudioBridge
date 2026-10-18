"""Unit tests for API drift detection, live introspection comparison, and coverage checking."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from studiobridge.cli import ExitCode, cli_entry
from studiobridge.manifest.drift import (
    check_api_coverage,
    compare_manifest_files,
    compare_manifests,
    compare_with_introspection,
    load_baseline_manifest,
)
from studiobridge.manifest.schema import (
    ArgDoc,
    CallbackDoc,
    FunctionDoc,
    Manifest,
    ModuleDoc,
)


@pytest.fixture
def baseline_manifest() -> Manifest:
    """Fixture providing a fresh copy of the bundled api_v44 baseline manifest."""
    return load_baseline_manifest()


def test_drift_baseline_identical(baseline_manifest: Manifest) -> None:
    """Verify comparing baseline against an identical copy detects zero drift."""
    cand = copy.deepcopy(baseline_manifest)
    report = compare_manifests(baseline_manifest, cand)

    assert not report.has_drift
    assert not report.has_breaking
    assert report.breaking_count == 0
    assert report.non_breaking_count == 0
    assert len(report.changes) == 0

    text = report.format_text()
    assert "No drift detected" in text
    md = report.format_markdown()
    assert "- **Drift Detected:** `No`" in md


def test_drift_function_added_and_removed(baseline_manifest: Manifest) -> None:
    """Verify detecting added function (non-breaking) and removed function (breaking)."""
    cand = copy.deepcopy(baseline_manifest)

    # 1. Add new function to mixer
    cand.modules["mixer"].functions["superBoost"] = FunctionDoc(
        name="superBoost",
        since=45,
        args=[ArgDoc(name="amount", type="float")],
        ret="none",
        summary="Boost volume level",
    )

    # 2. Remove existing function from channels
    assert "soloChannel" in cand.modules["channels"].functions
    del cand.modules["channels"].functions["soloChannel"]

    report = compare_manifests(baseline_manifest, cand)
    assert report.has_drift
    assert report.has_breaking
    assert report.breaking_count >= 1
    assert report.non_breaking_count >= 1

    added_changes = [
        c for c in report.changes if c.change_type == "added" and c.target == "mixer.superBoost"
    ]
    assert len(added_changes) == 1
    assert not added_changes[0].is_breaking

    removed_changes = [
        c
        for c in report.changes
        if c.change_type == "removed" and c.target == "channels.soloChannel"
    ]
    assert len(removed_changes) == 1
    assert removed_changes[0].is_breaking


def test_drift_parameter_variations(baseline_manifest: Manifest) -> None:
    """Verify parameter additions (optional vs required), removals, type changes, and ranges."""
    cand = copy.deepcopy(baseline_manifest)

    # Function under test: mixer.setTrackVolume
    fn = cand.modules["mixer"].functions["setTrackVolume"]

    # 1. Add optional parameter (non-breaking)
    fn.args.append(ArgDoc(name="smoothTime", type="float", optional=True, default=0.0))

    # 2. Add required parameter to another function (breaking)
    mute_fn = cand.modules["mixer"].functions["muteTrack"]
    mute_fn.args.append(ArgDoc(name="force", type="bool", optional=False))

    # 3. Change existing parameter type on channelCount (int -> str: breaking)
    ch_fn = cand.modules["channels"].functions["channelCount"]
    ch_fn.args[0].type = "str"

    report = compare_manifests(baseline_manifest, cand)
    assert report.has_drift

    # Check optional param added
    opt_added = [c for c in report.changes if c.target == "mixer.setTrackVolume.smoothTime"]
    assert len(opt_added) == 1
    assert not opt_added[0].is_breaking

    # Check required param added
    req_added = [c for c in report.changes if c.target == "mixer.muteTrack.force"]
    assert len(req_added) == 1
    assert req_added[0].is_breaking

    # Check type change
    type_mod = [c for c in report.changes if c.target == "channels.channelCount.mode"]
    assert len(type_mod) == 1
    assert type_mod[0].is_breaking
    assert type_mod[0].old_value == "int"
    assert type_mod[0].new_value == "str"


def test_drift_parameter_range_narrowing(baseline_manifest: Manifest) -> None:
    """Verify narrowing parameter range is breaking, whereas widening is non-breaking."""
    cand = copy.deepcopy(baseline_manifest)

    fn = cand.modules["mixer"].functions["setTrackVolume"]
    # Original range for index: [0, 126]
    # Narrow range to [0, 64] -> breaking
    fn.args[0].range = [0, 64]

    # Original range for volume: [0.0, 1.0]
    # Widen range to [-1.0, 2.0] -> non-breaking
    fn.args[1].range = [-1.0, 2.0]

    report = compare_manifests(baseline_manifest, cand)
    idx_change = [c for c in report.changes if c.target == "mixer.setTrackVolume.index"][0]
    assert idx_change.is_breaking

    vol_change = [c for c in report.changes if c.target == "mixer.setTrackVolume.volume"][0]
    assert not vol_change.is_breaking


def test_drift_return_type_changed(baseline_manifest: Manifest) -> None:
    """Verify modifying function return type is breaking."""
    cand = copy.deepcopy(baseline_manifest)

    # channels.channelCount returns int -> change to bool
    cand.modules["channels"].functions["channelCount"].ret = "bool"

    report = compare_manifests(baseline_manifest, cand)
    ret_changes = [c for c in report.changes if c.category == "return_type"]
    assert len(ret_changes) == 1
    assert ret_changes[0].is_breaking
    assert ret_changes[0].old_value == "int"
    assert ret_changes[0].new_value == "bool"


def test_drift_constants_callbacks_and_flags(baseline_manifest: Manifest) -> None:
    """Verify drift detection for constants, callbacks, and flags."""
    baseline_manifest.modules["general"].constants["MIDI_CMD_NOTEON"] = 0x90
    cand = copy.deepcopy(baseline_manifest)

    # 1. Add constant to mixer (non-breaking)
    cand.modules["mixer"].constants["NEW_MIXER_CONST"] = 999
    # 2. Modify constant in general (breaking)
    cand.modules["general"].constants["MIDI_CMD_NOTEON"] = 0x91
    # 3. Add flag (non-breaking)
    cand.flags["FPT_Extra"] = 9999
    # 4. Remove flag (breaking)
    if "FPT_Save" in cand.flags:
        del cand.flags["FPT_Save"]
    # 5. Add callback (non-breaking)
    cand.callbacks["OnCustomEvent"] = CallbackDoc(name="OnCustomEvent", since=45)
    # 6. Remove callback (breaking)
    if "OnSysEx" in cand.callbacks:
        del cand.callbacks["OnSysEx"]

    report = compare_manifests(baseline_manifest, cand)

    const_add = [c for c in report.changes if c.target == "mixer.NEW_MIXER_CONST"]
    assert len(const_add) == 1 and not const_add[0].is_breaking

    const_mod = [c for c in report.changes if c.target == "general.MIDI_CMD_NOTEON"]
    assert len(const_mod) == 1 and const_mod[0].is_breaking

    flag_add = [c for c in report.changes if c.target == "flags.FPT_Extra"]
    assert len(flag_add) == 1 and not flag_add[0].is_breaking

    cb_add = [c for c in report.changes if c.target == "callbacks.OnCustomEvent"]
    assert len(cb_add) == 1 and not cb_add[0].is_breaking

    if "OnSysEx" in baseline_manifest.callbacks:
        cb_rem = [c for c in report.changes if c.target == "callbacks.OnSysEx"]
        assert len(cb_rem) == 1 and cb_rem[0].is_breaking


def test_drift_module_addition_and_removal(baseline_manifest: Manifest) -> None:
    """Verify removing an entire module is breaking and adding a module is non-breaking."""
    cand = copy.deepcopy(baseline_manifest)

    # Remove ui module
    assert "ui" in cand.modules
    del cand.modules["ui"]

    # Add new module
    cand.modules["hardware"] = ModuleDoc(
        name="hardware",
        functions={"syncLeds": FunctionDoc(name="syncLeds", ret="none")},
        constants={"LED_ON": 1},
    )

    report = compare_manifests(baseline_manifest, cand)
    ui_removed = [c for c in report.changes if c.category == "module" and c.target == "ui"]
    assert len(ui_removed) == 1 and ui_removed[0].is_breaking

    hw_added = [c for c in report.changes if c.category == "module" and c.target == "hardware"]
    assert len(hw_added) == 1 and not hw_added[0].is_breaking


def test_compare_manifest_files(tmp_path: Path, baseline_manifest: Manifest) -> None:
    """Verify compare_manifest_files loads and compares two JSON files on disk."""
    f1 = tmp_path / "base.json"
    f2 = tmp_path / "cand.json"

    cand = copy.deepcopy(baseline_manifest)
    cand.modules["mixer"].functions["customFn"] = FunctionDoc(name="customFn", ret="none")

    f1.write_text(baseline_manifest.to_json(), encoding="utf-8")
    f2.write_text(cand.to_json(), encoding="utf-8")

    report = compare_manifest_files(f1, f2)
    assert report.has_drift
    assert any(c.target == "mixer.customFn" for c in report.changes)


def test_live_diff_matching(baseline_manifest: Manifest) -> None:
    """Verify live introspection with matching functions reports zero diff."""
    # Synthetic runtime introspect payload mirroring baseline
    introspect_data = {
        "build_hint": "26.1.3",
        "modules": {
            mname: {
                "functions": list(mod.functions.keys()),
                "constants": list(mod.constants.keys()),
            }
            for mname, mod in baseline_manifest.modules.items()
        },
    }

    report = compare_with_introspection(baseline_manifest, introspect_data)
    assert not report.has_diff
    assert len(report.missing_in_runtime) == 0
    assert len(report.undocumented_in_runtime) == 0
    assert len(report.matching_functions) == sum(
        len(m.functions) for m in baseline_manifest.modules.values()
    )

    text = report.format_text()
    assert "Runtime introspection perfectly matches manifest" in text


def test_live_diff_missing_and_undocumented(baseline_manifest: Manifest) -> None:
    """Verify live introspection accurately detects missing and undocumented functions/constants."""
    introspect_data = {
        "build_hint": "26.2.0-beta",
        "modules": {
            "mixer": {
                # Missing setTrackVolume, has undocumented hiddenMixerCmd
                "functions": ["getTrackVolume", "hiddenMixerCmd"],
                "constants": ["UNDOCUMENTED_CONST"],
            },
            # Entirely new module discovered at runtime
            "experimental": {
                "functions": ["vst3Scan"],
            },
        },
    }

    report = compare_with_introspection(baseline_manifest, introspect_data)
    assert report.has_diff
    assert "mixer.setTrackVolume" in report.missing_in_runtime
    assert "mixer.hiddenMixerCmd" in report.undocumented_in_runtime
    assert "experimental.vst3Scan" in report.undocumented_in_runtime
    assert "mixer.UNDOCUMENTED_CONST" in report.undocumented_constants

    md = report.format_markdown()
    assert "Missing in Runtime" in md
    assert "Undocumented in Runtime" in md


def test_api_coverage_baseline_complete(baseline_manifest: Manifest) -> None:
    """Verify baseline manifest fixture achieves 100% type coverage."""
    report = check_api_coverage(baseline_manifest)

    assert report.is_complete
    assert report.function_coverage_pct == 100.0
    assert report.parameter_coverage_pct == 100.0
    assert report.total_functions == 119
    assert report.fully_typed_functions == 119
    assert len(report.untyped_functions) == 0
    assert len(report.untyped_parameters) == 0
    assert len(report.issues) == 0

    text = report.format_text()
    assert "PASSED (100% Covered)" in text


def test_api_coverage_untyped_function_and_arg() -> None:
    """Verify check_api_coverage catches missing/invalid return and parameter types."""
    fn_bad_ret = FunctionDoc(name="untypedRet", ret="none")
    object.__setattr__(fn_bad_ret, "ret", "unknown")

    arg_bad_type = ArgDoc(name="paramA", type="int")
    object.__setattr__(arg_bad_type, "type", "any")
    fn_bad_arg = FunctionDoc(name="untypedParam", ret="int", args=[arg_bad_type])

    good_fn = FunctionDoc(name="goodFn", ret="bool", args=[ArgDoc(name="freq", type="float")])

    manifest = Manifest(
        api_version=45,
        modules={
            "synth": ModuleDoc(
                name="synth",
                functions={
                    "untypedRet": fn_bad_ret,
                    "untypedParam": fn_bad_arg,
                    "goodFn": good_fn,
                },
            )
        },
    )

    report = check_api_coverage(manifest)
    assert not report.is_complete
    assert report.total_functions == 3
    assert report.fully_typed_functions == 1
    assert "synth.untypedRet" in report.untyped_functions
    assert "synth.untypedParam" in report.untyped_functions
    assert "synth.untypedParam.paramA" in report.untyped_parameters
    assert len(report.issues) == 2


def test_cli_manifest_coverage(capsys) -> None:
    """Verify CLI `sbridge manifest coverage` command returns 0 on baseline."""
    code = cli_entry(["manifest", "coverage"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    assert "100.0%" in captured.out


def test_cli_manifest_coverage_failure(tmp_path: Path, capsys) -> None:
    """Verify CLI `sbridge manifest coverage` returns 1 when untyped functions exist."""
    bad_manifest = {
        "schema": 1,
        "manifest_schema": 1,
        "api_version": 99,
        "modules": {
            "test": {
                "functions": {
                    "bad": {
                        "since": 1,
                        "ret": "unknown",
                        "args": [],
                    }
                }
            }
        },
    }
    p = tmp_path / "bad_manifest.json"
    p.write_text(json.dumps(bad_manifest), encoding="utf-8")

    code = cli_entry(["manifest", "coverage", "--manifest", str(p)])
    assert code == ExitCode.ERROR
    captured = capsys.readouterr()
    assert "FAILED" in captured.out


def test_cli_manifest_check_drift_dry_run(capsys) -> None:
    """Verify CLI `sbridge manifest check-drift --dry-run` runs cleanly without modifying files."""
    code = cli_entry(["manifest", "check-drift", "--dry-run"])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    assert "API Drift Report" in captured.out


def test_cli_manifest_check_drift_fail_flags(tmp_path: Path) -> None:
    """Verify CLI `sbridge manifest check-drift` respects --fail-on-drift and --fail-on-breaking."""
    base = load_baseline_manifest()
    cand = copy.deepcopy(base)
    cand.modules["mixer"].functions["newFn"] = FunctionDoc(name="newFn", ret="none")

    cand_path = tmp_path / "cand.json"
    cand_path.write_text(cand.to_json(), encoding="utf-8")

    # Drift is present but non-breaking:
    # 1. With --fail-on-breaking -> returns OK (0) because it's non-breaking
    code_breaking = cli_entry(
        ["manifest", "check-drift", "--candidate", str(cand_path), "--fail-on-breaking"]
    )
    assert code_breaking == ExitCode.OK

    # 2. With --fail-on-drift -> returns ERROR (1)
    code_drift = cli_entry(
        ["manifest", "check-drift", "--candidate", str(cand_path), "--fail-on-drift"]
    )
    assert code_drift == ExitCode.ERROR


def test_cli_manifest_live_diff(tmp_path: Path, capsys) -> None:
    """Verify CLI `sbridge manifest live-diff --introspect <path>` outputs comparison report."""
    introspect = {
        "build_hint": "26.1.3",
        "modules": {
            "mixer": ["getTrackVolume", "setTrackVolume", "unlistedHelper"],
        },
    }
    i_path = tmp_path / "introspect.json"
    i_path.write_text(json.dumps(introspect), encoding="utf-8")

    code = cli_entry(["manifest", "live-diff", "--introspect", str(i_path)])
    assert code == ExitCode.OK
    captured = capsys.readouterr()
    assert "Live Introspection Diff" in captured.out
    assert "unlistedHelper" in captured.out
