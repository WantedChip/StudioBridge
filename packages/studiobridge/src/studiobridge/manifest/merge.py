"""Introspect merge and invariant validation pipeline.

Merges scraped API manifests with live runtime inspection dumps (from Spike 15)
and quirks overlays per 05_l0c_device_script_manifest.md §14.3–§14.5.
"""

from __future__ import annotations

from typing import Any

from studiobridge.manifest.overlay import QuirksOverlay, load_default_overlay
from studiobridge.manifest.schema import (
    FunctionDoc,
    Manifest,
    ManifestValidationError,
    ModuleDoc,
)


def merge_introspect(manifest: Manifest, introspect_data: dict[str, Any]) -> Manifest:
    """Merge live runtime inspection data with manifest.

    Marks existing functions as present_in_build (True/False) and adds
    undocumented symbols discovered during runtime inspection per 05_l0c §14.3.
    """
    if not isinstance(introspect_data, dict):
        raise ValueError("Introspect data must be a dictionary")

    modules_data = introspect_data.get("modules", introspect_data)
    if not isinstance(modules_data, dict):
        return manifest

    for mod_name, mod_info in modules_data.items():
        introspect_funcs: set[str] = set()
        introspect_consts: dict[str, Any] = {}

        if isinstance(mod_info, list):
            introspect_funcs = {str(item) for item in mod_info}
        elif isinstance(mod_info, dict):
            funcs = mod_info.get("functions", [])
            if isinstance(funcs, list):
                introspect_funcs = {str(f) for f in funcs}
            elif isinstance(funcs, dict):
                introspect_funcs = set(funcs.keys())
            consts = mod_info.get("constants", {})
            if isinstance(consts, dict):
                introspect_consts = dict(consts)

        if mod_name not in manifest.modules:
            manifest.modules[mod_name] = ModuleDoc(name=mod_name)

        mod = manifest.modules[mod_name]

        # Update existing functions
        for fname, fn_doc in mod.functions.items():
            if introspect_funcs:
                fn_doc.present_in_build = fname in introspect_funcs

        # Discover undocumented functions
        for fname in introspect_funcs:
            if fname not in mod.functions:
                mod.functions[fname] = FunctionDoc(
                    name=fname,
                    undocumented=True,
                    present_in_build=True,
                )

        # Merge constants
        for cname, cval in introspect_consts.items():
            if cname not in mod.constants:
                mod.constants[cname] = cval

    return manifest


def merge_manifest(
    manifest: Manifest,
    introspect_data: dict[str, Any] | None = None,
    overlay: QuirksOverlay | None = None,
    apply_default_overlay: bool = False,
) -> Manifest:
    """Pipeline stage: introspect merge -> quirks overlay -> invariant validation.

    Enforces invariants ensuring every paired verify.getter exists in the manifest (05_l0c §14.5).
    """
    if introspect_data:
        merge_introspect(manifest, introspect_data)

    if overlay is not None:
        overlay.apply(manifest)
    elif apply_default_overlay:
        default_overlay = load_default_overlay()
        default_overlay.apply(manifest)

    # Invariant validation
    validation_errors = manifest.validate()
    if validation_errors:
        raise ManifestValidationError(
            "Merged manifest failed invariant validation:\n- " + "\n- ".join(validation_errors)
        )

    return manifest
