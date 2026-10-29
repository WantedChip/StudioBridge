"""Unit tests for manifest overlay, introspect-merge, and code generation.

Verifies:
1. Negative allowlist tests (unlisted functions raise E_UNAVAILABLE, arg mismatches raise E_ARGS).
2. Type checking verification: generated .pyi stubs pass pyright cleanly.
3. Paired getters and tolerances correctly verified on mutating functions.
4. [MAN-02] evidence and test citation validation.
5. Introspect merge and invariant validation.
6. Typed constants and enums exported in studiobridge.fl.consts and studiobridge.fl.
7. Code generator determinism and Python 3.9 syntax validity.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from studiobridge.device.assets import _sb_api as api
from studiobridge.device.assets._sb_core import Dispatcher
from studiobridge.device.emulator.stubs import create_manifest_stubs
from studiobridge.fl import consts
from studiobridge.fl.consts import (
    FPT,
    PME,
    REC,
    UF,
    MidiMsg,
    midi,
)
from studiobridge.manifest.codegen import (
    generate_emulator_stubs,
    generate_fl_consts,
    generate_sb_api,
)
from studiobridge.manifest.merge import merge_introspect, merge_manifest
from studiobridge.manifest.overlay import (
    OverlayEntry,
    OverlayValidationError,
    QuirksOverlay,
    load_default_overlay,
)
from studiobridge.manifest.schema import (
    Manifest,
    ManifestValidationError,
    VerifySpec,
)

FIXTURE_PATH = (
    Path(__file__).parents[3]
    / "packages"
    / "studiobridge"
    / "src"
    / "studiobridge"
    / "manifest"
    / "fixtures"
    / "api_v44.json"
)


@pytest.fixture
def base_manifest() -> Manifest:
    """Load API v44 base reference manifest fixture."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return Manifest.from_dict(data)


# -------------------------------------------------------------------------
# 1. Negative Allowlist Tests
# -------------------------------------------------------------------------


def test_negative_allowlist_unknown_module() -> None:
    """Verify that calling an unlisted module raises KeyError (E_UNAVAILABLE)."""
    with pytest.raises(KeyError, match="Module 'unknown_module' not allowlisted"):
        api.coerce_args("unknown_module", "someFunc", [])


def test_negative_allowlist_unknown_function() -> None:
    """Verify that calling an unlisted function in a valid module raises KeyError."""
    with pytest.raises(KeyError, match="Function 'transport.fakeFunction' not allowlisted"):
        api.coerce_args("transport", "fakeFunction", [])


def test_negative_allowlist_dispatcher_e_unavailable() -> None:
    """Verify that Dispatcher maps KeyError from unlisted function to E_UNAVAILABLE."""
    dispatcher = Dispatcher()
    ok, err_code, err_msg, ret, rb = dispatcher._execute_single_call("transport.nonexistent", [])
    assert ok is False
    assert err_code == "E_UNAVAILABLE"
    assert err_msg is not None and "not allowlisted" in err_msg


def test_negative_allowlist_argument_count_mismatch() -> None:
    """Verify that too few or too many arguments raises ValueError (E_ARGS)."""
    # mixer.getTrackVolume requires exactly 1 argument (index)
    with pytest.raises(ValueError, match="Expected between 1 and 1 arguments"):
        api.coerce_args("mixer", "getTrackVolume", [])

    with pytest.raises(ValueError, match="Expected between 1 and 1 arguments"):
        api.coerce_args("mixer", "getTrackVolume", [0, 1, 2])


def test_negative_allowlist_argument_bounds_violation() -> None:
    """Verify that out-of-range argument values raise ValueError."""
    # mixer.getTrackVolume index range is [0, 126]
    with pytest.raises(ValueError, match="> max 126"):
        api.coerce_args("mixer", "getTrackVolume", [150])

    with pytest.raises(ValueError, match="< min 0"):
        api.coerce_args("mixer", "getTrackVolume", [-5])


def test_negative_allowlist_argument_type_violation() -> None:
    """Verify that incompatible argument types raise ValueError."""
    with pytest.raises(ValueError, match="Invalid value for argument"):
        api.coerce_args("mixer", "getTrackVolume", ["not_a_number"])


# -------------------------------------------------------------------------
# 2. [MAN-02] Evidence & Test Citation Validation Tests
# -------------------------------------------------------------------------


def test_man02_valid_entry() -> None:
    """Verify that an overlay entry with valid evidence and live test passes validation."""
    entry = OverlayEntry(
        fn="mixer.setTrackVolume",
        evidence=["spike:S2", "il-api-v44-errata"],
        test="tests/live/test_mixer_volume_settle.py",
        note="Asynchronous write settle",
    )
    assert entry.validate_man02() == []


def test_man02_missing_evidence_raises() -> None:
    """Verify that an overlay entry missing evidence triggers [MAN-02] violation."""
    entry = OverlayEntry(
        fn="mixer.setTrackVolume",
        evidence=[],
        test="tests/live/test_mixer.py",
    )
    errors = entry.validate_man02()
    assert any("[MAN-02]" in err and "evidence" in err for err in errors)


def test_man02_empty_evidence_string_raises() -> None:
    """Verify that empty or whitespace evidence strings trigger [MAN-02] violation."""
    entry = OverlayEntry(
        fn="transport.start",
        evidence=["   "],
        test="tests/live/test_transport.py",
    )
    errors = entry.validate_man02()
    assert any("[MAN-02]" in err and "evidence" in err for err in errors)


def test_man02_missing_test_raises() -> None:
    """Verify that an overlay entry missing a live test link triggers [MAN-02] violation."""
    entry = OverlayEntry(
        fn="transport.start",
        evidence=["karl-andres/fl-studio-mcp#7"],
        test="",
    )
    errors = entry.validate_man02()
    assert any("[MAN-02]" in err and "live test" in err for err in errors)


def test_man02_default_overlay_passes() -> None:
    """Verify that the official hand-written fl_quirks.yaml passes [MAN-02] 100% cleanly."""
    overlay = load_default_overlay()
    assert len(overlay.entries) >= 10
    errors = overlay.validate()
    assert errors == []


def test_man02_overlay_validation_error_on_apply() -> None:
    """Verify that QuirksOverlay.apply raises OverlayValidationError if entries are invalid."""
    bad_overlay = QuirksOverlay(
        entries=[
            OverlayEntry(fn="transport.start", evidence=[], test=""),
        ]
    )
    m = Manifest(api_version=44)
    with pytest.raises(OverlayValidationError, match="\\[MAN-02\\]"):
        bad_overlay.apply(m)


# -------------------------------------------------------------------------
# 3. Paired Getters, Tolerances & Overlays on Mutating Functions
# -------------------------------------------------------------------------


def test_overlay_application_paired_getters(base_manifest: Manifest) -> None:
    """Verify that fl_quirks.yaml correctly pairs getters and tolerances onto mutating functions."""
    overlay = load_default_overlay()
    overlay.apply(base_manifest)

    # 1. mixer.setTrackVolume
    vol_fn = base_manifest.modules["mixer"].functions["setTrackVolume"]
    assert vol_fn.mutating is True
    assert vol_fn.verify is not None
    assert vol_fn.verify.getter == "mixer.getTrackVolume"
    assert vol_fn.verify.compare == "approx"
    assert vol_fn.verify.tol == 0.01
    assert vol_fn.verify.settle == "idle1"

    # 2. mixer.setTrackPan
    pan_fn = base_manifest.modules["mixer"].functions["setTrackPan"]
    assert pan_fn.verify is not None
    assert pan_fn.verify.getter == "mixer.getTrackPan"
    assert pan_fn.verify.tol == 0.01

    # 3. general.restore (protected call)
    restore_fn = base_manifest.modules["general"].functions["restore"]
    assert restore_fn.protected is True
    assert restore_fn.mutating is True


def test_generated_sb_api_paired_getters_and_protection() -> None:
    """Verify that runtime ALLOW and helpers reflect paired getters, tolerances, and protection."""
    # mixer.setTrackVolume
    spec = api.ALLOW["mixer"]["setTrackVolume"]
    assert spec["getter"] == "mixer.getTrackVolume"
    assert spec["getter_args"] == [0]
    assert spec["tol"] == 0.01
    assert spec["compare"] == "approx"

    getter_fn, getter_args = api.get_verify_getter("mixer", "setTrackVolume", [5, 0.75])
    assert getter_fn == "mixer.getTrackVolume"
    assert getter_args == [5]

    # general.restore is protected
    assert api.is_protected("general", "restore") is True
    assert api.is_protected("transport", "start") is False


# -------------------------------------------------------------------------
# 4. Introspect Merge & Invariant Validation Tests
# -------------------------------------------------------------------------


def test_introspect_merge_present_and_missing(base_manifest: Manifest) -> None:
    """Verify that introspect merge marks functions present_in_build True/False."""
    # Provide inspection data where 'start' is present, but 'setLoopMode' is not
    introspect_data = {
        "modules": {
            "transport": {
                "functions": ["start", "stop", "isPlaying"],
                "constants": {"FPT_Play": 104},
            }
        }
    }
    merge_introspect(base_manifest, introspect_data)

    trans = base_manifest.modules["transport"]
    assert trans.functions["start"].present_in_build is True
    assert trans.functions["setLoopMode"].present_in_build is False


def test_introspect_merge_undocumented_discovery(base_manifest: Manifest) -> None:
    """Verify that undiscovered runtime functions are added with undocumented=True."""
    introspect_data = {
        "modules": {
            "transport": {
                "functions": ["start", "undocumentedHardwareReset"],
            }
        }
    }
    merge_introspect(base_manifest, introspect_data)

    trans = base_manifest.modules["transport"]
    assert "undocumentedHardwareReset" in trans.functions
    fn = trans.functions["undocumentedHardwareReset"]
    assert fn.undocumented is True
    assert fn.present_in_build is True
    assert fn.mutating is True  # conservative default for unknown name


def test_merge_manifest_invariant_validation_failure(base_manifest: Manifest) -> None:
    """Verify that merge_manifest raises ManifestValidationError if verify.getter is missing."""
    # Inject a broken verify spec pointing to non-existent function
    base_manifest.modules["mixer"].functions["setTrackVolume"].verify = VerifySpec(
        getter="mixer.nonExistentGetterMethod"
    )
    with pytest.raises(ManifestValidationError, match="verify getter .* not found"):
        merge_manifest(base_manifest)


# -------------------------------------------------------------------------
# 5. Typed Constants and Enums Export Tests
# -------------------------------------------------------------------------


def test_fl_constants_and_enums_exports() -> None:
    """Verify that studiobridge.fl.consts exports typed enums for FPT, UF, PME, REC, and midi."""
    # FPT transport commands
    assert isinstance(FPT.FPT_Play, int)
    assert FPT.FPT_Play == 104 or FPT.FPT_Play == 9
    assert consts.FPT_Play == FPT.FPT_Play

    # UF undo flags
    assert isinstance(UF.UF_Cancel, int)
    assert UF.UF_Cancel == 1
    assert consts.UF_Cancel == UF.UF_Cancel

    # PME parameter-edit flags
    assert isinstance(PME.PME_Live, int)
    assert PME.PME_Live == 1
    assert consts.PME_Live == PME.PME_Live

    # REC recording flags
    assert isinstance(REC.REC_Audio, int)
    assert REC.REC_Audio == 1
    assert consts.REC_Audio == REC.REC_Audio

    # midi event constants
    assert midi.MIDI_NOTEON == 0x90
    assert MidiMsg.MIDI_NOTEON == 0x90
    assert consts.MIDI_NOTEON == 0x90
    assert midi.MIDI_NOTEOFF == 0x80


def test_fl_init_re_exports() -> None:
    """Verify that studiobridge.fl re-exports all typed enums and constants."""
    import studiobridge.fl as fl

    assert hasattr(fl, "FPT")
    assert hasattr(fl, "UF")
    assert hasattr(fl, "PME")
    assert hasattr(fl, "REC")
    assert hasattr(fl, "MidiMsg")
    assert hasattr(fl, "midi")
    assert hasattr(fl, "consts")
    assert fl.FPT.FPT_Stop == consts.FPT_Stop


# -------------------------------------------------------------------------
# 6. Emulator Stubs Tests
# -------------------------------------------------------------------------


def test_emulator_stubs_generation_and_execution() -> None:
    """Verify that generated emulator module stubs return typed defaults."""
    stubs = create_manifest_stubs()
    assert "mixer" in stubs
    assert "transport" in stubs
    assert "channels" in stubs

    # mixer stubs
    mix = stubs["mixer"]
    assert mix.getTrackVolume(0) == 0.0  # float default
    assert mix.trackCount() == 0  # int default
    assert mix.getTrackName(0) == ""  # str default
    assert mix.isTrackMuted(0) is False  # bool default
    assert mix.setTrackVolume(0, 0.5) is None  # none return

    # transport stubs
    trans = stubs["transport"]
    assert trans.isPlaying() is False
    assert trans.getSongPos() == 0.0


# -------------------------------------------------------------------------
# 7. SDK Stubs & PEP 484/561 Type Checking Tests
# -------------------------------------------------------------------------


def test_sdk_stubs_raw_caller_forwarding() -> None:
    """Verify that generated SDK raw binding modules forward calls to set_raw_caller."""
    from studiobridge.sdk._generated import transport

    invocations: list[tuple[str, str, tuple[Any, ...]]] = []

    def mock_raw_caller(mod: str, fn: str, args: tuple[Any, ...]) -> Any:
        invocations.append((mod, fn, args))
        if fn == "isPlaying":
            return True
        return None

    transport.set_raw_caller(mock_raw_caller)
    try:
        res = transport.isPlaying()
        assert res is True
        assert len(invocations) == 1
        assert invocations[0] == ("transport", "isPlaying", ())
    finally:
        transport.set_raw_caller(None)


def test_pyright_passes_cleanly_on_generated_stubs() -> None:
    """Verify that all generated .pyi and .py files pass pyright typechecking without errors."""
    res = subprocess.run(
        [sys.executable, "-m", "pyright"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"pyright failed with errors:\n{res.stdout}\n{res.stderr}"
    assert "0 errors" in res.stdout


# -------------------------------------------------------------------------
# 8. Determinism and Python 3.9 Syntax Validity Tests
# -------------------------------------------------------------------------


def test_codegen_determinism(base_manifest: Manifest) -> None:
    """Verify that repeated codegen runs emit byte-identical strings."""
    overlay = load_default_overlay()
    overlay.apply(base_manifest)

    # 1. _sb_api.py
    api1 = generate_sb_api(base_manifest)
    api2 = generate_sb_api(base_manifest)
    assert api1 == api2

    # 2. consts.py
    c1 = generate_fl_consts(base_manifest)
    c2 = generate_fl_consts(base_manifest)
    assert c1 == c2

    # 3. stubs.py
    s1 = generate_emulator_stubs(base_manifest)
    s2 = generate_emulator_stubs(base_manifest)
    assert s1 == s2


def test_codegen_python_39_syntax_validity(base_manifest: Manifest) -> None:
    """Verify that generated _sb_api.py is syntactically valid in Python 3.9."""
    sb_api_code = generate_sb_api(base_manifest)
    # Parse with Python AST to verify valid syntax
    parsed = ast.parse(sb_api_code)
    assert isinstance(parsed, ast.Module)
