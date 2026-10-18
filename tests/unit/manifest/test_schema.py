"""Tests for manifest schema models, validation, and serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studiobridge.manifest.schema import (
    ALLOWED_PARAM_TYPES,
    MANIFEST_SCHEMA_VERSION,
    ArgDoc,
    CallbackDoc,
    FunctionDoc,
    Manifest,
    ManifestValidationError,
    ModuleDoc,
    VerifySpec,
    infer_conservative_mutating,
    validate_manifest_dict,
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


class TestArgDoc:
    """Tests for ArgDoc schema model."""

    def test_allowed_parameter_types(self) -> None:
        for ptype in ALLOWED_PARAM_TYPES:
            arg = ArgDoc(name="test_arg", type=ptype)
            assert arg.type == ptype
            assert arg.name == "test_arg"

    def test_invalid_parameter_type_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid parameter type"):
            ArgDoc(name="bad_arg", type="unsupported_type")

    def test_range_validation(self) -> None:
        arg = ArgDoc(name="vol", type="float", range=[0.0, 1.0])
        assert arg.range == [0.0, 1.0]

        with pytest.raises(ManifestValidationError, match="2-element sequence"):
            ArgDoc(name="bad_range", type="int", range=[1])  # type: ignore

        with pytest.raises(ManifestValidationError, match="2-element sequence"):
            ArgDoc(name="bad_range2", type="int", range="not_a_sequence")  # type: ignore

    def test_serialization_roundtrip(self) -> None:
        arg = ArgDoc(
            name="pickupMode",
            type="int",
            optional=True,
            default=0,
            range=[0, 3],
            since=16,
            doc="Optional pickup mode flag",
            enum_name="PickupModes",
        )
        d = arg.to_dict()
        assert d["name"] == "pickupMode"
        assert d["type"] == "int"
        assert d["optional"] is True
        assert d["default"] == 0
        assert d["range"] == [0, 3]
        assert d["since"] == 16
        assert d["doc"] == "Optional pickup mode flag"
        assert d["enum_name"] == "PickupModes"

        restored = ArgDoc.from_dict(d)
        assert restored.name == arg.name
        assert restored.type == arg.type
        assert restored.optional == arg.optional
        assert restored.default == arg.default
        assert restored.range == arg.range
        assert restored.since == arg.since
        assert restored.doc == arg.doc
        assert restored.enum_name == arg.enum_name


class TestVerifySpec:
    """Tests for VerifySpec model."""

    def test_valid_verify_spec(self) -> None:
        spec = VerifySpec(
            getter="getTrackVolume",
            args=["$0"],
            compare="approx",
            tol=0.005,
            settle="idle1",
        )
        assert spec.getter == "getTrackVolume"
        assert spec.compare == "approx"
        assert spec.tol == 0.005
        assert spec.settle == "idle1"

    def test_invalid_compare_mode_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid compare mode"):
            VerifySpec(getter="getVal", compare="fuzzy")

    def test_invalid_settle_mode_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid settle mode"):
            VerifySpec(getter="getVal", settle="tomorrow")

    def test_serialization_roundtrip(self) -> None:
        spec = VerifySpec(
            getter="getChannelPan",
            args=["$0"],
            compare="approx",
            tol=0.01,
            settle="idle2",
        )
        d = spec.to_dict()
        restored = VerifySpec.from_dict(d)
        assert restored.getter == spec.getter
        assert restored.args == spec.args
        assert restored.compare == spec.compare
        assert restored.tol == spec.tol
        assert restored.settle == spec.settle


class TestFunctionDoc:
    """Tests for FunctionDoc conservative defaults and serialization."""

    @pytest.mark.parametrize(
        ("func_name", "expected_mutating"),
        [
            ("getTrackVolume", False),
            ("getSongPos", False),
            ("isPlaying", False),
            ("isRecording", False),
            ("countTracks", False),
            ("findPlugin", False),
            ("setTrackVolume", True),
            ("start", True),
            ("stop", True),
            ("record", True),
            ("muteTrack", True),
            ("soloTrack", True),
            ("undo", True),
            ("redo", True),
        ],
    )
    def test_conservative_mutating_inference(self, func_name: str, expected_mutating: bool) -> None:
        assert infer_conservative_mutating(func_name) is expected_mutating
        fn = FunctionDoc(name=func_name)
        assert fn.mutating is expected_mutating
        assert fn.verify is None

    def test_explicit_mutating_override(self) -> None:
        fn = FunctionDoc(name="trackCount", mutating=False)
        assert fn.mutating is False

    def test_invalid_ret_type_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid return type"):
            FunctionDoc(name="testFn", ret="bad_type")

    def test_invalid_undo_mode_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid undo mode"):
            FunctionDoc(name="testFn", undo="automatic")

    def test_invalid_plane_raises(self) -> None:
        with pytest.raises(ManifestValidationError, match="Invalid plane"):
            FunctionDoc(name="testFn", plane="cloud")

    def test_serialization_roundtrip(self) -> None:
        fn = FunctionDoc(
            name="setTrackVolume",
            since=1,
            args=[
                ArgDoc(name="index", type="int", range=[0, 126]),
                ArgDoc(name="volume", type="float", range=[0.0, 1.0]),
                ArgDoc(name="pickupMode", type="int", optional=True, default=0, since=16),
            ],
            ret="none",
            mutating=True,
            protected=True,
            verify=VerifySpec(
                getter="getTrackVolume",
                args=["$0"],
                compare="approx",
                tol=0.005,
                settle="idle1",
            ),
            undo="auto",
            plane="live",
            summary="Set track volume level.",
            undocumented=True,
            present_in_build=False,
        )
        d = fn.to_dict()
        assert d["since"] == 1
        assert len(d["args"]) == 3
        assert d["args"][2]["since"] == 16
        assert d["args"][2]["optional"] is True
        assert d["protected"] is True
        assert d["undo"] == "auto"
        assert d["undocumented"] is True
        assert d["present_in_build"] is False
        assert d["verify"]["getter"] == "getTrackVolume"
        assert d["verify"]["tol"] == 0.005

        restored = FunctionDoc.from_dict("setTrackVolume", d)
        assert restored.name == fn.name
        assert restored.since == fn.since
        assert restored.protected is True
        assert restored.undo == "auto"
        assert restored.undocumented is True
        assert restored.present_in_build is False
        assert len(restored.args) == len(fn.args)
        assert restored.args[2].since == 16
        assert restored.verify is not None
        assert restored.verify.getter == "getTrackVolume"


class TestModuleDocAndCallbacks:
    """Tests for ModuleDoc and CallbackDoc."""

    def test_module_doc_roundtrip(self) -> None:
        mod = ModuleDoc(
            name="mixer",
            summary="Mixer module summary",
            since=2,
            functions={"getVol": FunctionDoc(name="getVol", ret="float", mutating=False)},
            constants={"EF_Test": 10},
        )
        d = mod.to_dict()
        assert d["summary"] == "Mixer module summary"
        assert d["since"] == 2
        assert "getVol" in d["functions"]
        assert d["constants"]["EF_Test"] == 10

        restored = ModuleDoc.from_dict("mixer", d)
        assert restored.name == "mixer"
        assert restored.summary == mod.summary
        assert restored.since == 2
        assert "getVol" in restored.functions
        assert restored.constants["EF_Test"] == 10

    def test_callback_doc_roundtrip(self) -> None:
        cb = CallbackDoc(
            name="OnProjectLoad",
            since=16,
            args=[ArgDoc(name="status", type="int")],
            summary="Project load callback",
        )
        d = cb.to_dict()
        assert d["since"] == 16
        assert len(d["args"]) == 1
        assert d["summary"] == "Project load callback"

        restored = CallbackDoc.from_dict("OnProjectLoad", d)
        assert restored.name == "OnProjectLoad"
        assert restored.since == 16
        assert len(restored.args) == 1
        assert restored.summary == "Project load callback"


class TestManifest:
    """Tests for full Manifest model and invariants."""

    def test_manifest_schema_version_defaults(self) -> None:
        m = Manifest(api_version=44)
        assert m.schema == MANIFEST_SCHEMA_VERSION
        assert m.manifest_schema == MANIFEST_SCHEMA_VERSION
        assert m.api_version == 44

    def test_manifest_validation_api_version(self) -> None:
        m = Manifest(api_version=0)
        errors = m.validate()
        assert any("api_version must be >= 1" in e for e in errors)

    def test_manifest_validation_getter_invariants(self) -> None:
        mod = ModuleDoc(
            name="mixer",
            functions={
                "getTrackVolume": FunctionDoc(name="getTrackVolume", ret="float", mutating=False),
                "setTrackVolume": FunctionDoc(
                    name="setTrackVolume",
                    ret="none",
                    mutating=True,
                    verify=VerifySpec(getter="getTrackVolume", args=["$0"]),
                ),
            },
        )
        manifest = Manifest(api_version=44, modules={"mixer": mod})
        errors = manifest.validate()
        assert errors == []

    def test_manifest_validation_missing_getter_fails(self) -> None:
        mod = ModuleDoc(
            name="mixer",
            functions={
                "setTrackVolume": FunctionDoc(
                    name="setTrackVolume",
                    ret="none",
                    mutating=True,
                    verify=VerifySpec(getter="nonExistentGetter", args=["$0"]),
                ),
            },
        )
        manifest = Manifest(api_version=44, modules={"mixer": mod})
        errors = manifest.validate()
        assert len(errors) == 1
        assert "not found in module" in errors[0]

    def test_manifest_validation_cross_module_getter(self) -> None:
        mod_mixer = ModuleDoc(
            name="mixer",
            functions={
                "setSongPos": FunctionDoc(
                    name="setSongPos",
                    ret="none",
                    mutating=True,
                    verify=VerifySpec(getter="transport.getSongPos", args=[]),
                ),
            },
        )
        mod_transport = ModuleDoc(
            name="transport",
            functions={
                "getSongPos": FunctionDoc(name="getSongPos", ret="float", mutating=False),
            },
        )
        # Valid cross module getter
        manifest = Manifest(
            api_version=44, modules={"mixer": mod_mixer, "transport": mod_transport}
        )
        assert manifest.validate() == []

        # Missing cross module
        manifest_missing_mod = Manifest(api_version=44, modules={"mixer": mod_mixer})
        errs = manifest_missing_mod.validate()
        assert any("verify getter module 'transport' not found" in e for e in errs)

    def test_validate_manifest_dict_errors(self) -> None:
        assert validate_manifest_dict("not_a_dict") == ["Manifest root must be an object"]  # type: ignore
        assert any("Missing required field 'api_version'" in e for e in validate_manifest_dict({}))
        assert any(
            "Field 'modules' must be an object" in e
            for e in validate_manifest_dict({"api_version": 1})
        )
        assert any(
            "Module 'bad' must be an object" in e
            for e in validate_manifest_dict({"api_version": 1, "modules": {"bad": 123}})
        )
        assert any(
            "Module 'bad.functions' must be an object" in e
            for e in validate_manifest_dict(
                {"api_version": 1, "modules": {"bad": {"functions": 123}}}
            )
        )
        assert any(
            "Function 'm.f' must be an object" in e
            for e in validate_manifest_dict(
                {"api_version": 1, "modules": {"m": {"functions": {"f": 123}}}}
            )
        )
        assert any(
            "invalid ret type" in e
            for e in validate_manifest_dict(
                {"api_version": 1, "modules": {"m": {"functions": {"f": {"ret": "bad"}}}}}
            )
        )
        assert any(
            "invalid argument descriptor" in e
            for e in validate_manifest_dict(
                {"api_version": 1, "modules": {"m": {"functions": {"f": {"args": ["not_a_dict"]}}}}}
            )
        )
        assert any(
            "invalid type 'invalid_type'" in e
            for e in validate_manifest_dict(
                {
                    "api_version": 1,
                    "modules": {
                        "m": {"functions": {"f": {"args": [{"name": "a", "type": "invalid_type"}]}}}
                    },
                }
            )
        )

    def test_validate_manifest_dict_valid(self) -> None:
        good_dict = {
            "api_version": 44,
            "modules": {
                "general": {
                    "functions": {
                        "getVersion": {
                            "since": 1,
                            "args": [],
                            "ret": "int",
                            "mutating": False,
                        }
                    }
                }
            },
        }
        assert validate_manifest_dict(good_dict) == []


class TestReferenceFixtureAPIv44:
    """Tests validating the canonical reference fixture api_v44.json."""

    def test_fixture_file_exists_and_loads(self) -> None:
        fixture_path = FIXTURES_DIR / "api_v44.json"
        assert fixture_path.exists(), f"Missing reference fixture at {fixture_path}"

        raw_text = fixture_path.read_text(encoding="utf-8")
        raw_dict = json.loads(raw_text)

        dict_errors = validate_manifest_dict(raw_dict)
        assert dict_errors == [], f"Dict validation errors: {dict_errors}"

        manifest = Manifest.from_json(raw_text)
        assert manifest.api_version == 44
        assert manifest.schema == 1
        assert manifest.manifest_schema == 1
        assert manifest.fl_version_hint == "26.1.3"

        # Check all 8 standard modules
        expected_modules = {
            "transport",
            "mixer",
            "channels",
            "patterns",
            "general",
            "ui",
            "device",
            "plugins",
        }
        assert expected_modules.issubset(set(manifest.modules.keys()))

        # Check callbacks
        expected_callbacks = {
            "OnInit",
            "OnDeInit",
            "OnSysEx",
            "OnMidiIn",
            "OnMidiMsg",
            "OnIdle",
            "OnRefresh",
            "OnProjectLoad",
        }
        assert expected_callbacks.issubset(set(manifest.callbacks.keys()))

        # Check flags
        assert "FPT_Save" in manifest.flags
        assert "FPT_Play" in manifest.flags
        assert "FPT_Stop" in manifest.flags

        # Invariant validation
        structural_errors = manifest.validate()
        assert structural_errors == [], f"Structural errors: {structural_errors}"

        # Verify specific function details
        set_vol = manifest.modules["mixer"].functions["setTrackVolume"]
        assert set_vol.verify is not None
        assert set_vol.verify.getter == "getTrackVolume"
        assert set_vol.verify.tol == 0.005
        assert set_vol.verify.settle == "idle1"

        # Check pickupMode per-argument version footnote
        pickup_arg = next(a for a in set_vol.args if a.name == "pickupMode")
        assert pickup_arg.since == 16
        assert pickup_arg.optional is True

    def test_fixture_roundtrip_determinism(self) -> None:
        fixture_path = FIXTURES_DIR / "api_v44.json"
        original_json = fixture_path.read_text(encoding="utf-8")
        manifest = Manifest.from_json(original_json)
        reserialized_json = manifest.to_json(indent=2)
        assert reserialized_json == original_json
