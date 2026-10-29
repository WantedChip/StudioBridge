"""Code generators for device script allowlist, typed constants, emulator stubs, and SDK stubs.

Generates:
1. packages/studiobridge/src/studiobridge/device/assets/_sb_api.py (runtime ALLOW dictionary).
2. packages/studiobridge/src/studiobridge/fl/consts.py (typed enums and constants).
3. packages/studiobridge/src/studiobridge/fl/__init__.py (constant exports).
4. packages/studiobridge/src/studiobridge/device/emulator/stubs.py (emulator module stubs).
5. packages/studiobridge/src/studiobridge/sdk/_generated/*.py and *.pyi (PEP 484/561 type stubs).
"""

from __future__ import annotations

import keyword
import textwrap
from pathlib import Path
from typing import Any

from studiobridge.manifest.schema import ArgDoc, Manifest, ModuleDoc

# Python type mapping from manifest type descriptors
TYPE_MAP_PYTHON: dict[str, str] = {
    "int": "int",
    "float": "float",
    "bool": "bool",
    "str": "str",
    "bytes": "bytes",
    "list": "list[Any]",
    "dict": "dict[str, Any]",
    "none": "None",
    "enum": "int",
    "flags": "int",
}

DEFAULT_VALUES: dict[str, Any] = {
    "int": 0,
    "float": 0.0,
    "bool": False,
    "str": '""',
    "bytes": 'b""',
    "list": "[]",
    "dict": "{}",
    "none": "None",
    "enum": 0,
    "flags": 0,
}


def _safe_param_name(name: str) -> str:
    """Escape Python keywords by appending an underscore."""
    if keyword.iskeyword(name) or name in ("self", "cls"):
        return f"{name}_"
    return name


def _format_default_value(arg: ArgDoc) -> str:
    """Format an argument default value for Python code."""
    if arg.default is not None:
        if isinstance(arg.default, str):
            return repr(arg.default)
        return str(arg.default)
    type_str = arg.type
    if type_str == "int":
        return "0"
    if type_str == "float":
        return "0.0"
    if type_str == "bool":
        return "False"
    if type_str == "str":
        return '""'
    return "None"


def generate_sb_api(manifest: Manifest) -> str:
    """Generate Python 3.9 compliant _sb_api.py defining ALLOW table and coercion rules.

    Strictly pure Python syntax without external dependencies per [DEV-01].
    """
    lines: list[str] = [
        '"""_sb_api.py - FL Studio API allowlist and argument/return coercion.',
        "",
        "Pure Python 3.9 syntax with zero external dependencies.",
        "Generated deterministically by studiobridge.manifest.codegen. Do not edit manually.",
        '"""',
        "",
        "ALLOW = {",
    ]

    for mod_name in sorted(manifest.modules.keys()):
        mod = manifest.modules[mod_name]
        lines.append(f'    "{mod_name}": {{')
        for fn_name in sorted(mod.functions.keys()):
            fn = mod.functions[fn_name]
            lines.append(f'        "{fn_name}": {{')

            # args
            lines.append('            "args": [')
            for arg in fn.args:
                parts: list[str] = [
                    f'"name": "{arg.name}"',
                    f'"type": "{arg.type}"',
                ]
                if arg.optional:
                    parts.append('"optional": True')
                if arg.default is not None:
                    if isinstance(arg.default, str):
                        parts.append(f'"default": {repr(arg.default)}')
                    else:
                        parts.append(f'"default": {arg.default}')
                if arg.range is not None:
                    parts.append(f'"min": {arg.range[0]}')
                    parts.append(f'"max": {arg.range[1]}')
                lines.append(f"                {{{', '.join(parts)}}},")
            lines.append("            ],")

            # ret & mutating
            lines.append(f'            "ret": "{fn.ret}",')
            lines.append(f'            "mutating": {fn.mutating},')

            # protected
            if fn.protected:
                lines.append('            "protected": True,')

            # verify
            if fn.verify:
                getter = fn.verify.getter
                if "." not in getter:
                    getter = f"{mod_name}.{getter}"
                lines.append(f'            "getter": "{getter}",')

                # Resolve getter_args: if numeric or '$0' format
                g_args: list[int] = []
                for a in fn.verify.args:
                    if isinstance(a, int):
                        g_args.append(a)
                    elif isinstance(a, str) and a.startswith("$") and a[1:].isdigit():
                        g_args.append(int(a[1:]))
                if not g_args and fn.args and not getter.endswith(".getSongPos"):
                    g_args = [0]
                lines.append(f'            "getter_args": {g_args},')
                lines.append(f'            "compare": "{fn.verify.compare}",')
                if fn.verify.tol is not None:
                    lines.append(f'            "tol": {fn.verify.tol},')
                lines.append(f'            "settle": "{fn.verify.settle}",')

            lines.append("        },")
        lines.append("    },")

    lines.extend(
        [
            "}",
            "",
            "",
            "def coerce_args(module_name, func_name, raw_args):",
            '    """Validate and coerce raw arguments against the allowlist signature.',
            "",
            "    Raises:",
            "        KeyError: If module or function is not allowlisted (mapped to E_UNAVAILABLE).",
            "        ValueError: If argument count or types/bounds violate constraints",
            "            (mapped to E_ARGS).",
            '    """',
            "    mod_table = ALLOW.get(module_name)",
            "    if mod_table is None:",
            "        raise KeyError(f\"Module '{module_name}' not allowlisted\")",
            "",
            "    spec = mod_table.get(func_name)",
            "    if spec is None:",
            "        raise KeyError(f\"Function '{module_name}.{func_name}' not allowlisted\")",
            "",
            '    arg_specs = spec.get("args", [])',
            "    raw_args = list(raw_args) if isinstance(raw_args, (list, tuple)) else []",
            "",
            '    min_args = sum(1 for a in arg_specs if not a.get("optional", False))',
            "    max_args = len(arg_specs)",
            "",
            "    if len(raw_args) < min_args or len(raw_args) > max_args:",
            "        raise ValueError(",
            '            f"Expected between {min_args} and {max_args} arguments for "',
            '            f"{module_name}.{func_name}, got {len(raw_args)}"',
            "        )",
            "",
            "    coerced = []",
            "    for idx in range(len(raw_args)):",
            "        arg_spec = arg_specs[idx]",
            "        val = raw_args[idx]",
            '        if val is None and arg_spec.get("optional", False):',
            '            val = arg_spec.get("default")',
            "        if val is None:",
            "            arg_n = arg_spec['name']",
            "            raise ValueError(f\"Argument '{arg_n}' cannot be None\")",
            '        arg_type = arg_spec.get("type", "int")',
            "        try:",
            '            if arg_type == "int":',
            "                val = int(val)",
            '                min_v = arg_spec.get("min")',
            '                max_v = arg_spec.get("max")',
            "                if min_v is not None and val < min_v:",
            "                    an = arg_spec['name']",
            '                    raise ValueError(f"Argument {an} ({val}) < min {min_v}")',
            "                if max_v is not None and val > max_v:",
            "                    an = arg_spec['name']",
            '                    raise ValueError(f"Argument {an} ({val}) > max {max_v}")',
            '            elif arg_type == "float":',
            "                val = float(val)",
            '                min_v = arg_spec.get("min")',
            '                max_v = arg_spec.get("max")',
            "                if min_v is not None and val < min_v:",
            "                    an = arg_spec['name']",
            '                    raise ValueError(f"Argument {an} ({val}) < min {min_v}")',
            "                if max_v is not None and val > max_v:",
            "                    an = arg_spec['name']",
            '                    raise ValueError(f"Argument {an} ({val}) > max {max_v}")',
            '            elif arg_type == "bool":',
            "                val = bool(val)",
            '            elif arg_type == "str":',
            "                val = str(val)",
            "        except (TypeError, ValueError) as exc:",
            "            raise ValueError(",
            "                f\"Invalid value for argument '{arg_spec['name']}' of \"",
            '                f"{module_name}.{func_name}: {exc}"',
            "            ) from exc",
            "        coerced.append(val)",
            "",
            "    return coerced",
            "",
            "",
            "def normalize_ret(ret_type, val):",
            '    """Normalize return value according to manifest expectations."""',
            '    if ret_type == "none":',
            "        return None",
            '    elif ret_type == "bool":',
            "        return bool(val)",
            '    elif ret_type == "int":',
            "        return int(val)",
            '    elif ret_type == "float":',
            "        return round(float(val), 6)",
            '    elif ret_type == "str":',
            "        return str(val)",
            "    elif isinstance(val, (list, tuple)):",
            "        return list(val)",
            "    return val",
            "",
            "",
            "def get_verify_getter(module_name, func_name, coerced_args):",
            '    """Resolve paired getter function and argument list for verification."""',
            "    spec = ALLOW.get(module_name, {}).get(func_name, {})",
            '    getter_spec = spec.get("getter")',
            "    if not getter_spec:",
            "        return None, []",
            '    getter_args_map = spec.get("getter_args", [])',
            "    getter_args = [",
            "        coerced_args[idx] for idx in getter_args_map if idx < len(coerced_args)",
            "    ]",
            "    return getter_spec, getter_args",
            "",
            "",
            "def is_protected(module_name, func_name):",
            '    """Check if a function has the protected safety flag enabled."""',
            "    mod = ALLOW.get(module_name, {})",
            '    return bool(mod.get(func_name, {}).get("protected", False))',
            "",
        ]
    )

    return "\n".join(lines)


def generate_fl_consts(manifest: Manifest) -> str:
    """Generate typed constants and enums for studiobridge.fl.consts."""
    lines: list[str] = [
        '"""Typed constants and enums for FL Studio MIDI scripting API.',
        "",
        "Exports FPT_* global transport commands, midi.* event constants, UF_* undo flags,",
        "PME_* flags, and REC_* flags.",
        "Generated deterministically by studiobridge.manifest.codegen. Do not edit manually.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from enum import IntEnum, IntFlag",
        "",
    ]

    # 1. Global transport FPT commands
    fpt_entries: dict[str, int] = {
        "FPT_Jog": 0,
        "FPT_Jog2": 1,
        "FPT_TrackJog": 2,
        "FPT_TempoJog": 3,
        "FPT_TapTempo": 4,
        "FPT_Tempo": 5,
        "FPT_FPT": 6,
        "FPT_Song": 7,
        "FPT_Pattern": 8,
        "FPT_Play": 9,
        "FPT_Stop": 10,
        "FPT_Record": 11,
        "FPT_Rewind": 12,
        "FPT_FastForward": 13,
        "FPT_Loop": 14,
        "FPT_Mute": 15,
        "FPT_Mode": 16,
        "FPT_Undo": 17,
        "FPT_UndoJog": 18,
        "FPT_PunchIn": 19,
        "FPT_PunchOut": 20,
        "FPT_CountDown": 21,
        "FPT_WaitKey": 22,
        "FPT_Metronome": 23,
        "FPT_LoopRecord": 24,
        "FPT_Save": 25,
        "FPT_SaveNew": 26,
        "FPT_StepEdit": 27,
        "FPT_F1": 40,
        "FPT_F2": 41,
        "FPT_F3": 42,
        "FPT_F4": 43,
        "FPT_F5": 44,
        "FPT_F6": 45,
        "FPT_F7": 46,
        "FPT_F8": 47,
        "FPT_F9": 48,
        "FPT_F10": 49,
        "FPT_Enter": 50,
        "FPT_Escape": 51,
        "FPT_Yes": 52,
        "FPT_No": 53,
        "FPT_Cut": 60,
        "FPT_Copy": 61,
        "FPT_Paste": 62,
        "FPT_Insert": 63,
        "FPT_Delete": 64,
        "FPT_NextWindow": 70,
        "FPT_WindowJog": 71,
        "FPT_MixerWindowJog": 72,
        "FPT_ChannelWindowJog": 73,
        "FPT_ArrangerWindowJog": 74,
    }
    # Merge flags from manifest
    for k, v in manifest.flags.items():
        if k.startswith("FPT_"):
            fpt_entries[k] = v

    lines.append("class FPT(IntEnum):")
    lines.append('    """Global transport command enum for transport.globalTransport()."""')
    lines.append("")
    for name, val in sorted(fpt_entries.items(), key=lambda x: (x[1], x[0])):
        lines.append(f"    {name} = {val}")
    lines.append("")
    lines.append("")

    # 2. Undo flags UF
    uf_entries: dict[str, int] = {
        "UF_None": 0,
        "UF_Cancel": 1,
        "UF_Reopen": 2,
        "UF_Direct": 4,
        "UF_Knob": 8,
        "UF_Audio": 16,
        "UF_Plugin": 32,
    }
    lines.append("class UF(IntFlag):")
    lines.append('    """Undo flags for general.saveUndo()."""')
    lines.append("")
    for name, val in sorted(uf_entries.items(), key=lambda x: x[1]):
        lines.append(f"    {name} = {val}")
    lines.append("")
    lines.append("")

    # 3. Parameter-edit flags PME
    pme_entries: dict[str, int] = {
        "PME_None": 0,
        "PME_Live": 1,
        "PME_Internal": 2,
        "PME_Ghost": 4,
        "PME_Auto": 8,
        "PME_Process": 16,
        "PME_FromMIDI": 32,
    }
    lines.append("class PME(IntFlag):")
    lines.append('    """Parameter edit / process message event flags."""')
    lines.append("")
    for name, val in sorted(pme_entries.items(), key=lambda x: x[1]):
        lines.append(f"    {name} = {val}")
    lines.append("")
    lines.append("")

    # 4. Recording flags REC
    rec_entries: dict[str, int] = {
        "REC_None": 0,
        "REC_Audio": 1,
        "REC_Score": 2,
        "REC_Automation": 4,
    }
    lines.append("class REC(IntFlag):")
    lines.append('    """Recording destination flags."""')
    lines.append("")
    for name, val in sorted(rec_entries.items(), key=lambda x: x[1]):
        lines.append(f"    {name} = {val}")
    lines.append("")
    lines.append("")

    # 5. MIDI event message constants
    midi_entries: dict[str, int] = {
        "MIDI_NOTEOFF": 0x80,
        "MIDI_NOTEON": 0x90,
        "MIDI_KEYAFTERTOUCH": 0xA0,
        "MIDI_CONTROLCHANGE": 0xB0,
        "MIDI_PROGRAMCHANGE": 0xC0,
        "MIDI_CHANNELAFTERTOUCH": 0xD0,
        "MIDI_PITCHBEND": 0xE0,
        "MIDI_SYSTEMMESSAGE": 0xF0,
        "MIDI_SYSEX": 0xF0,
        "MIDI_TIME_CODE": 0xF1,
        "MIDI_SONG_POS_POINTER": 0xF2,
        "MIDI_SONG_SELECT": 0xF3,
        "MIDI_TUNE_REQUEST": 0xF6,
        "MIDI_EOX": 0xF7,
        "MIDI_TIMING_CLOCK": 0xF8,
        "MIDI_START": 0xFA,
        "MIDI_CONTINUE": 0xFB,
        "MIDI_STOP": 0xFC,
        "MIDI_ACTIVE_SENSING": 0xFE,
        "MIDI_SYSTEM_RESET": 0xFF,
        "TrkId_Master": 0,
    }
    lines.append("class MidiMsg(IntEnum):")
    lines.append('    """Standard MIDI status bytes and event message identifiers."""')
    lines.append("")
    for name, val in sorted(midi_entries.items(), key=lambda x: (x[1], x[0])):
        lines.append(f"    {name} = {hex(val) if val >= 0x80 else val}")
    lines.append("")
    lines.append("")

    # Namespace class midi
    lines.append("class midi:")
    lines.append('    """Namespace matching FL Studio\'s built-in midi module constants."""')
    lines.append("")
    for name, val in sorted(midi_entries.items(), key=lambda x: (x[1], x[0])):
        lines.append(f"    {name}: int = {hex(val) if val >= 0x80 else val}")
    lines.append("")
    lines.append("")

    # Top-level exports
    for name in sorted(fpt_entries.keys()):
        lines.append(f"{name} = FPT.{name}")
    for name in sorted(uf_entries.keys()):
        lines.append(f"{name} = UF.{name}")
    for name in sorted(pme_entries.keys()):
        lines.append(f"{name} = PME.{name}")
    for name in sorted(rec_entries.keys()):
        lines.append(f"{name} = REC.{name}")
    for name in sorted(midi_entries.keys()):
        lines.append(f"{name} = midi.{name}")

    lines.append("")
    lines.append("__all__ = [")
    lines.append('    "FPT",')
    lines.append('    "UF",')
    lines.append('    "PME",')
    lines.append('    "REC",')
    lines.append('    "MidiMsg",')
    lines.append('    "midi",')
    all_consts = sorted(
        set(fpt_entries.keys())
        | set(uf_entries.keys())
        | set(pme_entries.keys())
        | set(rec_entries.keys())
        | set(midi_entries.keys())
    )
    for c in all_consts:
        lines.append(f'    "{c}",')
    lines.append("]")
    lines.append("")

    return "\n".join(lines)


def generate_fl_init() -> str:
    """Generate packages/studiobridge/src/studiobridge/fl/__init__.py."""
    return (
        '"""FL Studio constants, flags, and types.\n'
        "\n"
        "Exports typed constants and enums.\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "from studiobridge.fl import consts\n"
        "from studiobridge.fl.consts import (\n"
        "    FPT,\n"
        "    PME,\n"
        "    REC,\n"
        "    UF,\n"
        "    MidiMsg,\n"
        "    midi,\n"
        ")\n"
        "\n"
        "__all__ = [\n"
        '    "FPT",\n'
        '    "PME",\n'
        '    "REC",\n'
        '    "UF",\n'
        '    "MidiMsg",\n'
        '    "consts",\n'
        '    "midi",\n'
        "]\n"
    )


def generate_emulator_stubs(manifest: Manifest) -> str:
    """Generate emulator module stubs in studiobridge.device.emulator.stubs.

    Isolated from higher layers per [DEV-30] and import-linter rules.
    """
    lines: list[str] = [
        '"""Emulator module stubs generated from FL Studio API manifest.',
        "",
        "Provides default no-op stub implementations for all manifest functions.",
        "Isolated from higher layers per [DEV-30].",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import types",
        "from typing import Any",
        "",
        "def _default_stub(*args: Any, **kwargs: Any) -> Any:",
        "    return None",
        "",
        "def create_manifest_stubs() -> dict[str, types.ModuleType]:",
        '    """Create a dictionary of all manifest module stubs."""',
        "    stubs: dict[str, types.ModuleType] = {}",
        "",
    ]

    for mod_name in sorted(manifest.modules.keys()):
        mod = manifest.modules[mod_name]
        lines.append(f"    # Module: {mod_name}")
        lines.append(f'    mod_{mod_name} = types.ModuleType("{mod_name}")')
        for fn_name in sorted(mod.functions.keys()):
            fn = mod.functions[fn_name]
            ret_val = DEFAULT_VALUES.get(fn.ret, "None")
            param_names = [_safe_param_name(a.name) for a in fn.args]
            param_str = ", ".join(f"{p}: Any = None" for p in param_names)
            lines.append(f"    def _{mod_name}_{fn_name}({param_str}) -> Any:")
            lines.append(f"        return {ret_val}")
            lines.append(f"    mod_{mod_name}.{fn_name} = _{mod_name}_{fn_name}  # type: ignore")

        for c_name, c_val in sorted(mod.constants.items()):
            lines.append(f"    mod_{mod_name}.{c_name} = {repr(c_val)}  # type: ignore")

        lines.append(f'    stubs["{mod_name}"] = mod_{mod_name}')
        lines.append("")

    lines.append("    return stubs")
    lines.append("")
    lines.append("STUB_MODULES: dict[str, types.ModuleType] = create_manifest_stubs()")
    lines.append("")

    return "\n".join(lines)


def generate_sdk_module(mod_name: str, mod: ModuleDoc) -> tuple[str, str]:
    """Generate Python implementation (.py) and PEP 484/561 type stub (.pyi) for an SDK module."""
    # 1. Implementation .py
    py_lines: list[str] = [
        f'"""Generated raw FL Studio API binding for \'{mod_name}\'.',
        "",
        f"Module summary: {mod.summary}",
        "Generated by studiobridge.manifest.codegen. Do not edit manually.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from collections.abc import Callable",
        "from typing import Any",
        "",
        "_raw_caller: Callable[[str, str, tuple[Any, ...]], Any] | None = None",
        "",
        "",
        "def set_raw_caller(caller: Callable[[str, str, tuple[Any, ...]], Any] | None) -> None:",
        '    """Configure active raw caller dispatch callable."""',
        "    global _raw_caller",
        "    _raw_caller = caller",
        "",
        "",
        "def _call(func_name: str, *args: Any) -> Any:",
        "    if _raw_caller is None:",
        f'        raise RuntimeError("No active raw caller registered for {mod_name}")',
        f'    return _raw_caller("{mod_name}", func_name, args)',
        "",
    ]

    # 2. Type stub .pyi
    pyi_lines: list[str] = [
        f'"""Type stubs for FL Studio \'{mod_name}\' module.',
        "",
        f"Module summary: {mod.summary}",
        "Generated by studiobridge.manifest.codegen. Do not edit manually.",
        '"""',
        "",
        "from collections.abc import Callable",
        "from typing import Any",
        "",
        "def set_raw_caller(",
        "    caller: Callable[[str, str, tuple[Any, ...]], Any] | None,",
        ") -> None: ...",
        "",
    ]

    for fn_name in sorted(mod.functions.keys()):
        fn = mod.functions[fn_name]
        ret_type = TYPE_MAP_PYTHON.get(fn.ret, "Any")

        # Parameter lists for .py and .pyi
        py_params: list[str] = []
        pyi_params: list[str] = []
        forward_args: list[str] = []

        for arg in fn.args:
            p_name = _safe_param_name(arg.name)
            p_type = TYPE_MAP_PYTHON.get(arg.type, "Any")
            forward_args.append(p_name)

            if arg.optional:
                default_str = _format_default_value(arg)
                py_params.append(f"{p_name}: {p_type} = {default_str}")
                pyi_params.append(f"{p_name}: {p_type} = ...")
            else:
                py_params.append(f"{p_name}: {p_type}")
                pyi_params.append(f"{p_name}: {p_type}")

        py_param_str = ", ".join(py_params)
        pyi_param_str = ", ".join(pyi_params)
        forward_str = ", ".join(forward_args)

        summary_text = (fn.summary or fn_name).strip()
        doc_lines = ['    """' + (summary_text if len(summary_text) <= 80 else "")]
        if len(summary_text) > 80:
            for p in textwrap.wrap(summary_text, width=80):
                doc_lines.append(f"    {p}")
        doc_lines.append("")
        doc_lines.append(f"    Since API version: {fn.since}.")
        doc_lines.append(f"    Mutating: {fn.mutating}.")
        doc_lines.append('    """')
        doc = "\n".join(doc_lines)

        # Append to .py
        py_lines.append("")
        py_lines.append("")
        py_lines.append(f"def {fn_name}({py_param_str}) -> {ret_type}:")
        py_lines.append(doc)
        if forward_str:
            py_lines.append(f'    return _call("{fn_name}", {forward_str})')
        else:
            py_lines.append(f'    return _call("{fn_name}")')

        # Append to .pyi
        pyi_lines.append("")
        pyi_lines.append("")
        pyi_lines.append(f"def {fn_name}({pyi_param_str}) -> {ret_type}:")
        pyi_lines.append(doc)
        pyi_lines.append("    ...")

    return "\n".join(py_lines) + "\n", "\n".join(pyi_lines) + "\n"


def generate_sdk_stubs(manifest: Manifest, output_dir: Path | str) -> dict[str, tuple[str, str]]:
    """Generate all SDK raw binding modules and .pyi stubs into output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results: dict[str, tuple[str, str]] = {}
    mod_names = sorted(manifest.modules.keys())

    # Write __init__.py
    init_lines = [
        '"""Generated raw FL Studio API bindings and type stubs.',
        "",
        "Generated by studiobridge.manifest.codegen. Do not edit manually.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
    ]
    init_lines.append("from studiobridge.sdk._generated import (")
    for m in mod_names:
        init_lines.append(f"    {m},")
    init_lines.append(")")
    init_lines.append("")
    init_lines.append("__all__ = [")
    for m in mod_names:
        init_lines.append(f'    "{m}",')
    init_lines.append("]")
    init_lines.append("")

    (out / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")
    (out / "py.typed").write_text("# Marker file for PEP 561.\n", encoding="utf-8")

    for mod_name in mod_names:
        mod = manifest.modules[mod_name]
        py_code, pyi_code = generate_sdk_module(mod_name, mod)
        (out / f"{mod_name}.py").write_text(py_code, encoding="utf-8")
        (out / f"{mod_name}.pyi").write_text(pyi_code, encoding="utf-8")
        results[mod_name] = (py_code, pyi_code)

    return results


def generate_all(manifest: Manifest, repo_root: Path | str | None = None) -> list[Path]:
    """Orchestrate full code generation across all target paths.

    Emits:
    - _sb_api.py (device allowlist)
    - consts.py & fl/__init__.py
    - emulator stubs.py
    - sdk/_generated/*.py & *.pyi
    """
    if repo_root is not None:
        pkg_root = Path(repo_root) / "packages" / "studiobridge" / "src" / "studiobridge"
    else:
        # __file__ is in packages/studiobridge/src/studiobridge/manifest/codegen.py
        pkg_root = Path(__file__).resolve().parents[1]

    created: list[Path] = []

    # 1. Device _sb_api.py
    sb_api_path = pkg_root / "device" / "assets" / "_sb_api.py"
    sb_api_path.parent.mkdir(parents=True, exist_ok=True)
    sb_api_content = generate_sb_api(manifest)
    sb_api_path.write_text(sb_api_content, encoding="utf-8")
    created.append(sb_api_path)

    # 2. FL consts.py & fl/__init__.py
    fl_dir = pkg_root / "fl"
    fl_dir.mkdir(parents=True, exist_ok=True)
    consts_path = fl_dir / "consts.py"
    consts_path.write_text(generate_fl_consts(manifest), encoding="utf-8")
    created.append(consts_path)

    fl_init_path = fl_dir / "__init__.py"
    fl_init_path.write_text(generate_fl_init(), encoding="utf-8")
    created.append(fl_init_path)

    # 3. Emulator stubs.py
    stubs_path = pkg_root / "device" / "emulator" / "stubs.py"
    stubs_path.parent.mkdir(parents=True, exist_ok=True)
    stubs_path.write_text(generate_emulator_stubs(manifest), encoding="utf-8")
    created.append(stubs_path)

    # 4. SDK _generated
    sdk_gen_dir = pkg_root / "sdk" / "_generated"
    generate_sdk_stubs(manifest, sdk_gen_dir)
    created.append(sdk_gen_dir)

    # Automatically format generated files with ruff if present
    try:
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, "-m", "ruff", "format", str(pkg_root)],
            capture_output=True,
            check=False,
        )
    except Exception:
        pass

    return created
