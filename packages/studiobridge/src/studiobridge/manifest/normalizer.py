"""API manifest signature normalizer, type inference, and AST processor.

Normalizes function signatures, resolves type aliases, parses enum constants,
handles per-argument version footnotes and optional arguments, and produces
deterministic, byte-identical Manifest objects and JSON representations per
05_l0c_device_script_manifest.md §13–§14.
"""

from __future__ import annotations

import ast
import contextlib
import re
from typing import Any

from studiobridge.manifest.schema import (
    ALLOWED_PARAM_TYPES,
    ALLOWED_RET_TYPES,
    ArgDoc,
    FunctionDoc,
    Manifest,
    ModuleDoc,
    VerifySpec,
    infer_conservative_mutating,
)
from studiobridge.manifest.scraper import RawFunction, RawModule

TYPE_ALIASES: dict[str, str] = {
    "int": "int",
    "integer": "int",
    "long": "int",
    "short": "int",
    "idx": "int",
    "index": "int",
    "count": "int",
    "number": "int",
    "num": "int",
    "mode": "int",
    "color": "int",
    "float": "float",
    "double": "float",
    "real": "float",
    "number_float": "float",
    "bool": "bool",
    "boolean": "bool",
    "str": "str",
    "string": "str",
    "text": "str",
    "name": "str",
    "bytes": "bytes",
    "bytearray": "bytes",
    "none": "none",
    "void": "none",
    "null": "none",
    "enum": "enum",
    "flags": "flags",
}

# Standard verified write pairs
STANDARD_VERIFIERS: dict[str, dict[str, Any]] = {
    "mixer.setTrackVolume": {
        "getter": "getTrackVolume",
        "args": ["$0"],
        "compare": "approx",
        "tol": 0.005,
        "settle": "idle1",
    },
    "mixer.setTrackPan": {
        "getter": "getTrackPan",
        "args": ["$0"],
        "compare": "approx",
        "tol": 0.005,
        "settle": "idle1",
    },
    "mixer.setTrackName": {
        "getter": "getTrackName",
        "args": ["$0"],
        "compare": "exact",
        "settle": "immediate",
    },
    "mixer.muteTrack": {
        "getter": "isTrackMuted",
        "args": ["$0"],
        "compare": "exact",
        "settle": "immediate",
    },
    "channels.setChannelVolume": {
        "getter": "getChannelVolume",
        "args": ["$0"],
        "compare": "approx",
        "tol": 0.005,
        "settle": "idle1",
    },
    "channels.setChannelPan": {
        "getter": "getChannelPan",
        "args": ["$0"],
        "compare": "approx",
        "tol": 0.005,
        "settle": "idle1",
    },
    "channels.setChannelName": {
        "getter": "getChannelName",
        "args": ["$0"],
        "compare": "exact",
        "settle": "immediate",
    },
    "patterns.setPatternName": {
        "getter": "getPatternName",
        "args": ["$0"],
        "compare": "exact",
        "settle": "immediate",
    },
    "transport.setSongPos": {
        "getter": "getSongPos",
        "args": [],
        "compare": "approx",
        "tol": 0.01,
        "settle": "idle1",
    },
}


def resolve_type_alias(raw_type: str) -> str:
    """Resolve a raw type string to one of the canonical schema parameter types."""
    clean = raw_type.strip().lower()
    clean = re.sub(r"^(?:typing\.|builtins\.)", "", clean)
    clean = re.sub(r"\[.*?\]", "", clean)  # e.g. Optional[int] -> Optional -> int
    if clean in TYPE_ALIASES:
        return TYPE_ALIASES[clean]
    # Check substring matches
    for k, v in TYPE_ALIASES.items():
        if k in clean:
            return v
    return "int"


def infer_arg_type(name: str, default: Any = None, raw_type: str | None = None) -> str:
    """Infer the canonical parameter type from annotation, default value, or argument name."""
    if raw_type:
        resolved = resolve_type_alias(raw_type)
        if resolved in ALLOWED_PARAM_TYPES:
            return resolved

    if default is not None:
        if isinstance(default, bool):
            return "bool"
        elif isinstance(default, float):
            return "float"
        elif isinstance(default, int):
            return "int"
        elif isinstance(default, str):
            return "str"
        elif isinstance(default, (bytes, bytearray)):
            return "bytes"

    lower_name = name.lower()
    if (
        lower_name.startswith(("is_", "has_", "can_"))
        or bool(re.match(r"^(is|has|can)[A-Z0-9_]", name))
        or lower_name in ("enabled", "muted", "solo", "active", "visible", "handled")
    ):
        return "bool"
    if any(
        k in lower_name
        for k in ("volume", "vol", "pan", "pitch", "pos", "speed", "tempo", "val", "ratio", "tol")
    ):
        return "float"
    if any(
        k in lower_name
        for k in (
            "idx",
            "index",
            "count",
            "num",
            "number",
            "mode",
            "track",
            "channel",
            "pattern",
            "color",
            "slot",
            "window",
            "port",
            "id",
            "ppq",
        )
    ):
        return "int"
    if any(k in lower_name for k in ("name", "text", "title", "path", "str")):
        return "str"
    if any(k in lower_name for k in ("data", "sysex", "bytes", "msg")):
        return "bytes"

    return "int"


def infer_arg_range(
    module: str, func_name: str, arg_name: str, arg_type: str
) -> list[int | float] | None:
    """Infer valid parameter range for common FL Studio parameters."""
    arg_lower = arg_name.lower()
    mod_lower = module.lower()

    if arg_type == "float":
        if "pan" in arg_lower:
            return [-1.0, 1.0]
        if any(term in arg_lower for term in ("vol", "volume", "pos")):
            return [0.0, 1.0]
    elif arg_type == "int":
        if "track" in arg_lower or ("index" in arg_lower and mod_lower == "mixer"):
            return [0, 126]
        if "pattern" in arg_lower or ("index" in arg_lower and mod_lower == "patterns"):
            return [1, 999]
        if "channel" in arg_lower or ("index" in arg_lower and mod_lower == "channels"):
            return [0, 999]
    return None


def infer_ret_type(func_name: str, raw_return: str | None = None) -> str:
    """Infer the canonical return type for a function."""
    if raw_return:
        resolved = resolve_type_alias(raw_return)
        if resolved in ALLOWED_RET_TYPES:
            return resolved

    lower_fn = func_name.lower()
    # Explicit mutators / action functions always return none
    if lower_fn.startswith(
        (
            "set",
            "mute",
            "solo",
            "select",
            "start",
            "stop",
            "record",
            "jump",
            "save",
            "undo",
            "redo",
            "show",
            "hide",
            "arm",
            "enable",
            "link",
            "jog",
            "scroll",
            "snap",
            "dispatch",
            "forward",
            "process",
            "restore",
            "clear",
        )
    ):
        return "none"

    if lower_fn.startswith(("is", "has", "can")):
        return "bool"
    if lower_fn.endswith(("count", "number", "index", "version", "ppq", "color", "port")):
        return "int"
    if lower_fn.endswith(("volume", "pan", "pos", "length", "speed")):
        return "float"
    if lower_fn.endswith(("name", "text", "title")):
        return "str"
    if lower_fn.startswith("get"):
        # Look at what comes after get
        subject = lower_fn[3:]
        if any(term in subject for term in ("volume", "pan", "pos", "speed", "length")):
            return "float"
        if any(term in subject for term in ("count", "num", "color", "version", "ppq")):
            return "int"
        if any(term in subject for term in ("name", "text", "title")):
            return "str"

    return "none"


def parse_python_signature(sig_str: str) -> tuple[str, list[ArgDoc], str]:
    """Parse a Python function signature or def statement using the Python AST."""
    sig_clean = sig_str.strip()
    if not sig_clean.startswith("def "):
        sig_clean = f"def {sig_clean}: pass"
    elif not sig_clean.endswith(": pass") and not sig_clean.endswith(":"):
        sig_clean = f"{sig_clean}: pass"
    elif sig_clean.endswith(":"):
        sig_clean = f"{sig_clean} pass"

    tree = ast.parse(sig_clean)
    fn_node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))

    func_name = fn_node.name

    ret_type = "none"
    if fn_node.returns:
        ret_repr = ast.unparse(fn_node.returns)
        ret_type = resolve_type_alias(ret_repr)

    args: list[ArgDoc] = []
    defaults = list(fn_node.args.defaults)
    num_positional = len(fn_node.args.args)
    num_defaults = len(defaults)
    default_start_idx = num_positional - num_defaults

    for idx, arg_node in enumerate(fn_node.args.args):
        pname = arg_node.arg
        has_default = idx >= default_start_idx
        default_val: Any = None
        if has_default:
            default_node = defaults[idx - default_start_idx]
            try:
                default_val = ast.literal_eval(default_node)
            except Exception:
                default_val = ast.unparse(default_node)

        raw_type = ast.unparse(arg_node.annotation) if arg_node.annotation else None
        arg_type = infer_arg_type(pname, default=default_val, raw_type=raw_type)

        args.append(
            ArgDoc(
                name=pname,
                type=arg_type,
                optional=has_default,
                default=default_val,
            )
        )

    return func_name, args, ret_type


def normalize_raw_function(
    raw_fn: RawFunction,
    module_name: str,
    overlay_verifier: VerifySpec | None = None,
) -> FunctionDoc:
    """Normalize a RawFunction descriptor into a schema-compliant FunctionDoc."""
    func_name = raw_fn.name
    ret_type = infer_ret_type(func_name, raw_fn.raw_return)
    mutating = infer_conservative_mutating(func_name)

    args: list[ArgDoc] = []
    for raw_arg in raw_fn.raw_args:
        pname = raw_arg.get("name", "arg")
        raw_type = raw_arg.get("type")
        default_str = raw_arg.get("default")
        default_val: Any = None
        if default_str is not None:
            try:
                default_val = ast.literal_eval(default_str)
            except Exception:
                default_val = default_str

        is_optional = raw_arg.get("optional") in ("true", True) or default_val is not None
        arg_type = infer_arg_type(pname, default=default_val, raw_type=raw_type)
        arg_range = infer_arg_range(module_name, func_name, pname, arg_type)

        since_val: int | None = None
        if "since" in raw_arg:
            with contextlib.suppress(ValueError):
                since_val = int(raw_arg["since"])

        args.append(
            ArgDoc(
                name=pname,
                type=arg_type,
                optional=is_optional,
                default=default_val,
                range=arg_range,
                since=since_val,
                doc=raw_arg.get("doc", ""),
            )
        )

    # Resolve verify spec
    verifier = overlay_verifier
    if verifier is None:
        full_key = f"{module_name}.{func_name}"
        if full_key in STANDARD_VERIFIERS:
            v_info = STANDARD_VERIFIERS[full_key]
            verifier = VerifySpec(
                getter=v_info["getter"],
                args=v_info.get("args", []),
                compare=v_info.get("compare", "exact"),
                tol=v_info.get("tol"),
                settle=v_info.get("settle", "immediate"),
            )

    return FunctionDoc(
        name=func_name,
        since=raw_fn.since,
        args=args,
        ret=ret_type,
        mutating=mutating,
        protected=False,
        verify=verifier,
        summary=raw_fn.summary,
    )


def normalize_raw_module(raw_mod: RawModule) -> ModuleDoc:
    """Normalize a RawModule into a schema-compliant ModuleDoc with sorted members."""
    functions: dict[str, FunctionDoc] = {}
    for r_fn in raw_mod.functions:
        fn_doc = normalize_raw_function(r_fn, raw_mod.name)
        functions[fn_doc.name] = fn_doc

    return ModuleDoc(
        name=raw_mod.name,
        summary=raw_mod.summary,
        since=1,
        functions=functions,
        constants=dict(raw_mod.constants),
    )


def normalize_manifest(
    raw_manifest_or_dict: Any,
    api_version: int = 44,
    fl_version_hint: str = "26.1.3",
    generated: str = "2026-10-04",
) -> Manifest:
    """Normalize raw descriptors or dictionary into a deterministic Manifest instance."""
    if isinstance(raw_manifest_or_dict, Manifest):
        return raw_manifest_or_dict

    if isinstance(raw_manifest_or_dict, dict):
        # Already structured dictionary, round-trip through schema
        manifest = Manifest.from_dict(raw_manifest_or_dict)
        if api_version:
            manifest.api_version = api_version
        if fl_version_hint:
            manifest.fl_version_hint = fl_version_hint
        if generated:
            manifest.generated = generated
        return manifest

    raise TypeError(f"Unsupported input type for normalize_manifest: {type(raw_manifest_or_dict)}")
