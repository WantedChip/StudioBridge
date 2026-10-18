"""API manifest schema models, JSON schema definition, and validators.

Defines typed dataclasses and serialization for Manifest, ModuleDoc, FunctionDoc,
ArgDoc, VerifySpec, CallbackDoc, and constant/flag mappings per
05_l0c_device_script_manifest.md §13.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

MANIFEST_SCHEMA_VERSION: int = 1

ALLOWED_PARAM_TYPES: frozenset[str] = frozenset(
    {"int", "float", "bool", "str", "enum", "flags", "bytes", "none"}
)

ALLOWED_RET_TYPES: frozenset[str] = frozenset(
    {"int", "float", "bool", "str", "enum", "flags", "bytes", "none", "list", "dict"}
)

ALLOWED_COMPARE_MODES: frozenset[str] = frozenset({"exact", "approx"})
ALLOWED_SETTLE_MODES: frozenset[str] = frozenset({"immediate", "idle1", "idle2"})
ALLOWED_UNDO_MODES: frozenset[str] = frozenset({"none", "auto", "manual"})
ALLOWED_PLANES: frozenset[str] = frozenset({"live", "offline"})

_MUTATING_PREFIX_RE = re.compile(r"^(get|is|count|find)", re.IGNORECASE)


def infer_conservative_mutating(name: str) -> bool:
    """Infer whether a function is mutating based on conservative name prefix defaults.

    Conservative rule: Function names not starting with get|is|count|find default to
    mutating=True, verify=None.
    """
    return not bool(_MUTATING_PREFIX_RE.match(name))


class ManifestValidationError(ValueError):
    """Raised when an API manifest or element fails schema validation."""


@dataclass
class ArgDoc:
    """Documentation and typing descriptor for a function or callback argument."""

    name: str
    type: str = "int"
    optional: bool = False
    default: Any = None
    range: tuple[int | float, int | float] | list[int | float] | None = None
    since: int | None = None
    doc: str = ""
    enum_name: str | None = None

    def __post_init__(self) -> None:
        if self.type not in ALLOWED_PARAM_TYPES:
            raise ManifestValidationError(
                f"Invalid parameter type '{self.type}' for argument '{self.name}'. "
                f"Allowed types: {sorted(ALLOWED_PARAM_TYPES)}"
            )
        if self.range is not None:
            if not isinstance(self.range, (list, tuple)) or len(self.range) != 2:
                raise ManifestValidationError(
                    f"Argument range for '{self.name}' must be a 2-element sequence, "
                    f"got {self.range}"
                )
            self.range = [self.range[0], self.range[1]]

    def to_dict(self) -> dict[str, Any]:
        """Convert argument descriptor to a clean dictionary."""
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
        }
        if self.optional:
            d["optional"] = True
        if self.default is not None:
            d["default"] = self.default
        if self.range is not None:
            d["range"] = list(self.range)
        if self.since is not None:
            d["since"] = self.since
        if self.doc:
            d["doc"] = self.doc
        if self.enum_name is not None:
            d["enum_name"] = self.enum_name
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArgDoc:
        """Construct ArgDoc from dictionary."""
        return cls(
            name=data["name"],
            type=data.get("type", "int"),
            optional=data.get("optional", False),
            default=data.get("default"),
            range=data.get("range"),
            since=data.get("since"),
            doc=data.get("doc", ""),
            enum_name=data.get("enum_name"),
        )


@dataclass
class VerifySpec:
    """Specification for verified writes via paired getter read-back."""

    getter: str
    args: list[Any] = field(default_factory=list)
    compare: str = "exact"
    tol: float | None = None
    settle: str = "immediate"

    def __post_init__(self) -> None:
        if self.compare not in ALLOWED_COMPARE_MODES:
            raise ManifestValidationError(
                f"Invalid compare mode '{self.compare}'. Allowed: {sorted(ALLOWED_COMPARE_MODES)}"
            )
        if self.settle not in ALLOWED_SETTLE_MODES:
            raise ManifestValidationError(
                f"Invalid settle mode '{self.settle}'. Allowed: {sorted(ALLOWED_SETTLE_MODES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert verify spec to dictionary."""
        d: dict[str, Any] = {
            "getter": self.getter,
            "args": list(self.args),
            "compare": self.compare,
            "settle": self.settle,
        }
        if self.tol is not None:
            d["tol"] = self.tol
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerifySpec:
        """Construct VerifySpec from dictionary."""
        return cls(
            getter=data["getter"],
            args=data.get("args", []),
            compare=data.get("compare", "exact"),
            tol=data.get("tol"),
            settle=data.get("settle", "immediate"),
        )


@dataclass
class FunctionDoc:
    """Descriptor for an FL Studio API function."""

    name: str
    since: int = 1
    args: list[ArgDoc] = field(default_factory=list)
    ret: str = "none"
    mutating: bool | None = None
    protected: bool = False
    verify: VerifySpec | None = None
    undo: str = "none"
    plane: str = "live"
    summary: str = ""
    undocumented: bool = False
    present_in_build: bool = True

    def __post_init__(self) -> None:
        if self.mutating is None:
            self.mutating = infer_conservative_mutating(self.name)
        if self.ret not in ALLOWED_RET_TYPES:
            raise ManifestValidationError(
                f"Invalid return type '{self.ret}' for function '{self.name}'. "
                f"Allowed: {sorted(ALLOWED_RET_TYPES)}"
            )
        if self.undo not in ALLOWED_UNDO_MODES:
            raise ManifestValidationError(
                f"Invalid undo mode '{self.undo}'. Allowed: {sorted(ALLOWED_UNDO_MODES)}"
            )
        if self.plane not in ALLOWED_PLANES:
            raise ManifestValidationError(
                f"Invalid plane '{self.plane}'. Allowed: {sorted(ALLOWED_PLANES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert FunctionDoc to a cleanly ordered dictionary."""
        d: dict[str, Any] = {
            "since": self.since,
            "args": [a.to_dict() for a in self.args],
            "ret": self.ret,
            "mutating": self.mutating if self.mutating is not None else True,
            "protected": self.protected,
        }
        if self.verify is not None:
            d["verify"] = self.verify.to_dict()
        if self.undo != "none":
            d["undo"] = self.undo
        if self.plane != "live":
            d["plane"] = self.plane
        if self.summary:
            d["summary"] = self.summary
        if self.undocumented:
            d["undocumented"] = True
        if not self.present_in_build:
            d["present_in_build"] = False
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> FunctionDoc:
        """Construct FunctionDoc from dictionary."""
        args = [ArgDoc.from_dict(a) for a in data.get("args", [])]
        verify_data = data.get("verify")
        verify = VerifySpec.from_dict(verify_data) if verify_data else None
        return cls(
            name=name,
            since=data.get("since", 1),
            args=args,
            ret=data.get("ret", "none"),
            mutating=data.get("mutating"),
            protected=data.get("protected", False),
            verify=verify,
            undo=data.get("undo", "none"),
            plane=data.get("plane", "live"),
            summary=data.get("summary", ""),
            undocumented=data.get("undocumented", False),
            present_in_build=data.get("present_in_build", True),
        )


@dataclass
class CallbackDoc:
    """Descriptor for an FL Studio script callback handler."""

    name: str
    since: int = 1
    args: list[ArgDoc] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert CallbackDoc to dictionary."""
        d: dict[str, Any] = {"since": self.since}
        if self.args:
            d["args"] = [a.to_dict() for a in self.args]
        if self.summary:
            d["summary"] = self.summary
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> CallbackDoc:
        """Construct CallbackDoc from dictionary."""
        args = [ArgDoc.from_dict(a) for a in data.get("args", [])]
        return cls(
            name=name,
            since=data.get("since", 1),
            args=args,
            summary=data.get("summary", ""),
        )


@dataclass
class ModuleDoc:
    """Descriptor for an FL Studio API module."""

    name: str
    summary: str = ""
    since: int = 1
    functions: dict[str, FunctionDoc] = field(default_factory=dict)
    constants: dict[str, int | str | float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert ModuleDoc to dictionary with sorted functions and constants."""
        d: dict[str, Any] = {}
        if self.summary:
            d["summary"] = self.summary
        if self.since != 1:
            d["since"] = self.since
        d["functions"] = {
            fname: self.functions[fname].to_dict() for fname in sorted(self.functions.keys())
        }
        if self.constants:
            d["constants"] = {
                cname: self.constants[cname] for cname in sorted(self.constants.keys())
            }
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ModuleDoc:
        """Construct ModuleDoc from dictionary."""
        functions: dict[str, FunctionDoc] = {}
        for fname, f_data in data.get("functions", {}).items():
            functions[fname] = FunctionDoc.from_dict(fname, f_data)
        constants = dict(data.get("constants", {}))
        return cls(
            name=name,
            summary=data.get("summary", ""),
            since=data.get("since", 1),
            functions=functions,
            constants=constants,
        )


@dataclass
class Manifest:
    """Full FL Studio API manifest representing a specific API version.

    Supports both 'schema' and 'manifest_schema' (default 1) per spec §13.
    """

    api_version: int
    fl_version_hint: str = ""
    generated: str = ""
    schema: int = MANIFEST_SCHEMA_VERSION
    manifest_schema: int = MANIFEST_SCHEMA_VERSION
    modules: dict[str, ModuleDoc] = field(default_factory=dict)
    callbacks: dict[str, CallbackDoc] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SCHEMA_VERSION:
            self.schema = MANIFEST_SCHEMA_VERSION
        if self.manifest_schema != MANIFEST_SCHEMA_VERSION:
            self.manifest_schema = MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert full manifest to a sorted, deterministic dictionary."""
        return {
            "schema": self.schema,
            "manifest_schema": self.manifest_schema,
            "api_version": self.api_version,
            "fl_version_hint": self.fl_version_hint,
            "generated": self.generated,
            "modules": {
                mname: self.modules[mname].to_dict() for mname in sorted(self.modules.keys())
            },
            "callbacks": {
                cname: self.callbacks[cname].to_dict() for cname in sorted(self.callbacks.keys())
            },
            "flags": {fname: self.flags[fname] for fname in sorted(self.flags.keys())},
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize manifest to deterministic byte-identical JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False) + "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        """Construct Manifest from dictionary."""
        schema_ver = data.get("manifest_schema", data.get("schema", MANIFEST_SCHEMA_VERSION))
        api_version = int(data["api_version"])
        fl_version_hint = str(data.get("fl_version_hint", ""))
        generated = str(data.get("generated", ""))

        modules: dict[str, ModuleDoc] = {}
        for mname, m_data in data.get("modules", {}).items():
            modules[mname] = ModuleDoc.from_dict(mname, m_data)

        callbacks: dict[str, CallbackDoc] = {}
        for cname, c_data in data.get("callbacks", {}).items():
            callbacks[cname] = CallbackDoc.from_dict(cname, c_data)

        flags: dict[str, int] = {k: int(v) for k, v in data.get("flags", {}).items()}

        return cls(
            api_version=api_version,
            fl_version_hint=fl_version_hint,
            generated=generated,
            schema=schema_ver,
            manifest_schema=schema_ver,
            modules=modules,
            callbacks=callbacks,
            flags=flags,
        )

    @classmethod
    def from_json(cls, text: str) -> Manifest:
        """Deserialize Manifest from a JSON string."""
        data = json.loads(text)
        return cls.from_dict(data)

    def validate(self) -> list[str]:
        """Validate structural integrity and invariants of this Manifest."""
        errors: list[str] = []
        if self.api_version < 1:
            errors.append(f"api_version must be >= 1, got {self.api_version}")

        # Check getter verification invariant:
        # Every verify.getter must exist within the target module or named module
        for mname, mod in self.modules.items():
            for fname, fn in mod.functions.items():
                if fn.verify:
                    getter_target = fn.verify.getter
                    if "." in getter_target:
                        g_mod, g_fn = getter_target.split(".", 1)
                    else:
                        g_mod, g_fn = mname, getter_target

                    if g_mod not in self.modules:
                        errors.append(
                            f"Function '{mname}.{fname}' verify getter module '{g_mod}' "
                            f"not found in manifest"
                        )
                    elif g_fn not in self.modules[g_mod].functions:
                        errors.append(
                            f"Function '{mname}.{fname}' verify getter '{getter_target}' "
                            f"not found in module '{g_mod}'"
                        )

        return errors


def validate_manifest_dict(data: dict[str, Any]) -> list[str]:
    """Validate a raw manifest dictionary against the schema and return a list of errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Manifest root must be an object"]

    if "api_version" not in data:
        errors.append("Missing required field 'api_version'")
    elif not isinstance(data["api_version"], int) or data["api_version"] < 1:
        errors.append(f"Field 'api_version' must be an integer >= 1, got {data['api_version']}")

    modules = data.get("modules")
    if modules is None or not isinstance(modules, dict):
        errors.append("Field 'modules' must be an object")
    else:
        for mname, m_data in modules.items():
            if not isinstance(m_data, dict):
                errors.append(f"Module '{mname}' must be an object")
                continue
            funcs = m_data.get("functions", {})
            if not isinstance(funcs, dict):
                errors.append(f"Module '{mname}.functions' must be an object")
                continue
            for fname, f_data in funcs.items():
                if not isinstance(f_data, dict):
                    errors.append(f"Function '{mname}.{fname}' must be an object")
                    continue
                ret = f_data.get("ret", "none")
                if ret not in ALLOWED_RET_TYPES:
                    errors.append(f"Function '{mname}.{fname}' invalid ret type '{ret}'")
                for arg in f_data.get("args", []):
                    if not isinstance(arg, dict) or "name" not in arg:
                        errors.append(
                            f"Function '{mname}.{fname}' contains invalid argument descriptor"
                        )
                        continue
                    arg_type = arg.get("type", "int")
                    if arg_type not in ALLOWED_PARAM_TYPES:
                        errors.append(
                            f"Function '{mname}.{fname}' arg '{arg.get('name')}' "
                            f"invalid type '{arg_type}'"
                        )

    return errors


MANIFEST_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "StudioBridgeAPIManifest",
    "type": "object",
    "required": ["api_version", "modules"],
    "properties": {
        "schema": {"type": "integer", "const": 1},
        "manifest_schema": {"type": "integer", "const": 1},
        "api_version": {"type": "integer", "minimum": 1},
        "fl_version_hint": {"type": "string"},
        "generated": {"type": "string"},
        "modules": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "since": {"type": "integer"},
                    "functions": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "required": ["since", "args", "ret", "mutating"],
                            "properties": {
                                "since": {"type": "integer"},
                                "ret": {"type": "string", "enum": sorted(ALLOWED_RET_TYPES)},
                                "mutating": {"type": "boolean"},
                                "protected": {"type": "boolean"},
                                "undo": {"type": "string", "enum": sorted(ALLOWED_UNDO_MODES)},
                                "plane": {"type": "string", "enum": sorted(ALLOWED_PLANES)},
                                "summary": {"type": "string"},
                                "undocumented": {"type": "boolean"},
                                "present_in_build": {"type": "boolean"},
                                "args": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["name", "type"],
                                        "properties": {
                                            "name": {"type": "string"},
                                            "type": {
                                                "type": "string",
                                                "enum": sorted(ALLOWED_PARAM_TYPES),
                                            },
                                            "optional": {"type": "boolean"},
                                            "default": {},
                                            "range": {
                                                "type": "array",
                                                "minItems": 2,
                                                "maxItems": 2,
                                            },
                                            "since": {"type": "integer"},
                                            "doc": {"type": "string"},
                                            "enum_name": {"type": "string"},
                                        },
                                    },
                                },
                                "verify": {
                                    "type": "object",
                                    "required": ["getter"],
                                    "properties": {
                                        "getter": {"type": "string"},
                                        "args": {"type": "array"},
                                        "compare": {
                                            "type": "string",
                                            "enum": sorted(ALLOWED_COMPARE_MODES),
                                        },
                                        "tol": {"type": ["number", "null"]},
                                        "settle": {
                                            "type": "string",
                                            "enum": sorted(ALLOWED_SETTLE_MODES),
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "constants": {
                        "type": "object",
                        "additionalProperties": {"type": ["integer", "string", "number"]},
                    },
                },
            },
        },
        "callbacks": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "since": {"type": "integer"},
                    "summary": {"type": "string"},
                    "args": {"type": "array"},
                },
            },
        },
        "flags": {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        },
    },
}
