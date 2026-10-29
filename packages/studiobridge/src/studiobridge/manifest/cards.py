"""Markdown API reference card generator for documentation and MCP resource endpoints.

Transforms normalized API manifest descriptors into clean, structured Markdown cards
for documentation sites (Starlight) and MCP resource URIs (`studio://api/{module}/{function}`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from studiobridge.manifest.schema import FunctionDoc, Manifest, ModuleDoc

_PYTHON_TYPE_MAP: dict[str, str] = {
    "int": "int",
    "float": "float",
    "bool": "bool",
    "str": "str",
    "none": "None",
    "bytes": "bytes",
    "enum": "int",
    "flags": "int",
    "list": "list",
    "dict": "dict",
}


class ApiCardsDict(dict[str, str]):
    """Dictionary mapping canonical resource URIs to markdown card content.

    Allows transparent access via URI ('studio://api/{mod}/{fn}'), dot notation
    ('{mod}.{fn}'), or path notation ('{mod}/{fn}').
    """

    def __getitem__(self, key: str) -> str:
        if key in self:
            return super().__getitem__(key)
        # Normalize alternative keys
        clean_key = key
        if clean_key.startswith("studio://api/"):
            clean_key = clean_key[len("studio://api/") :]
        parts = clean_key.replace(".", "/").split("/")
        if len(parts) == 2:
            canonical_uri = f"studio://api/{parts[0]}/{parts[1]}"
            if canonical_uri in self:
                return super().__getitem__(canonical_uri)
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        try:
            return self[key]
        except KeyError:
            return default


def _format_signature(module_name: str, fn_name: str, fn_doc: FunctionDoc) -> str:
    """Format Python function signature code block."""
    ret_type = _PYTHON_TYPE_MAP.get(fn_doc.ret, fn_doc.ret)
    param_strs: list[str] = []

    for arg in fn_doc.args:
        p_type = arg.enum_name or _PYTHON_TYPE_MAP.get(arg.type, arg.type)
        if arg.optional:
            if arg.default is not None:
                param_strs.append(f"{arg.name}: {p_type} = {arg.default!r}")
            else:
                param_strs.append(f"{arg.name}: {p_type} = None")
        else:
            param_strs.append(f"{arg.name}: {p_type}")

    one_line = f"def {fn_name}({', '.join(param_strs)}) -> {ret_type}: ..."
    if len(one_line) <= 75 and len(param_strs) <= 2:
        return f"```python\n{one_line}\n```"

    indented_params = "\n".join(f"    {p}," for p in param_strs)
    if indented_params:
        return f"```python\ndef {fn_name}(\n{indented_params}\n) -> {ret_type}: ...\n```"
    return f"```python\ndef {fn_name}() -> {ret_type}: ...\n```"


def generate_card(
    module_name: str,
    fn_name: str,
    fn_doc: FunctionDoc,
    module_doc: ModuleDoc | None = None,
) -> str:
    """Generate Markdown API reference card for a function descriptor.

    The card includes:
    - Resource URI (`studio://api/{module}/{function}`)
    - Python signature block
    - Summary
    - Parameter table (name, type, optional, range, since, description)
    - Return type
    - Metadata table (since, mutating, protected, verify, undo, plane)
    """
    resource_uri = f"studio://api/{module_name}/{fn_name}"
    title = f"{module_name}.{fn_name}"
    sig_block = _format_signature(module_name, fn_name, fn_doc)

    summary = fn_doc.summary.strip()
    if not summary:
        if module_doc and module_doc.summary:
            summary = (
                f"API function belonging to `{module_name}` module ({module_doc.summary.strip()})."
            )
        else:
            summary = f"API function belonging to `{module_name}` module."

    # Parameters table
    if not fn_doc.args:
        params_section = "This function takes no parameters."
    else:
        rows = [
            "| Parameter | Type | Optional | Range | Since | Description |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for arg in fn_doc.args:
            p_name = f"`{arg.name}`"
            type_str = f"`{arg.type}`"
            if arg.enum_name:
                type_str = f"`{arg.type}` ({arg.enum_name})"
            optional_str = "Yes" if arg.optional else "No"
            range_str = f"`[{arg.range[0]}, {arg.range[1]}]`" if arg.range else "—"
            since_str = f"API v{arg.since}" if arg.since else f"API v{fn_doc.since}"
            desc_str = arg.doc.strip().replace("\n", " ") if arg.doc else "—"
            cols = [p_name, type_str, optional_str, range_str, since_str, desc_str]
            rows.append("| " + " | ".join(cols) + " |")
        params_section = "\n".join(rows)

    # Return value
    ret_type_str = _PYTHON_TYPE_MAP.get(fn_doc.ret, fn_doc.ret)

    # Verification description
    if fn_doc.verify is not None:
        v = fn_doc.verify
        details = [f"getter: `{v.getter}`", f"compare: `{v.compare}`", f"settle: `{v.settle}`"]
        if v.tol is not None:
            details.append(f"tol: `{v.tol}`")
        if v.args:
            details.append(f"args: `{v.args}`")
        verify_str = ", ".join(details)
    else:
        verify_str = "None"

    # Metadata table
    meta_rows = [
        "| Property | Value |",
        "| :--- | :--- |",
        f"| Since API Version | API v{fn_doc.since} |",
        f"| Mutating | {'Yes' if fn_doc.mutating else 'No'} |",
        f"| Protected | {'Yes' if fn_doc.protected else 'No'} |",
        f"| Verification | {verify_str} |",
        f"| Undo Mode | `{fn_doc.undo}` |",
        f"| Execution Plane | `{fn_doc.plane}` |",
    ]
    if fn_doc.undocumented:
        meta_rows.append("| Undocumented | Yes (discovered via runtime introspection) |")
    if not fn_doc.present_in_build:
        meta_rows.append("| Present in Build | No (deprecated or missing in current runtime) |")

    metadata_section = "\n".join(meta_rows)

    card = f"""# {title}

**Resource URI:** `{resource_uri}`

## Signature

{sig_block}

## Summary

{summary}

## Parameters

{params_section}

## Return Value

- **Type:** `{ret_type_str}`

## Metadata

{metadata_section}
"""
    return card


def generate_all_cards(
    manifest: Manifest,
    output_dir: Path | str | None = None,
) -> ApiCardsDict:
    """Generate Markdown API reference cards for all functions in the manifest.

    If output_dir is provided, writes each card to `<output_dir>/<module>/<function>.md`.
    Returns an ApiCardsDict mapping resource URIs to markdown strings.
    """
    cards = ApiCardsDict()
    out_base = Path(output_dir) if output_dir is not None else None

    for mod_name in sorted(manifest.modules.keys()):
        mod_doc = manifest.modules[mod_name]
        for fn_name in sorted(mod_doc.functions.keys()):
            fn_doc = mod_doc.functions[fn_name]
            card_md = generate_card(mod_name, fn_name, fn_doc, mod_doc)
            resource_uri = f"studio://api/{mod_name}/{fn_name}"
            cards[resource_uri] = card_md

            if out_base is not None:
                mod_dir = out_base / mod_name
                mod_dir.mkdir(parents=True, exist_ok=True)
                target_file = mod_dir / f"{fn_name}.md"
                target_file.write_text(card_md, encoding="utf-8")

    return cards
