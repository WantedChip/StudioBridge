"""API manifest schema, documentation scraper, and AST normalizer.

Provides machine-readable typed descriptors and parsing utilities for FL Studio's
official Python MIDI controller scripting API per 05_l0c_device_script_manifest.md §11–§14.
"""

from __future__ import annotations

from studiobridge.manifest.normalizer import (
    STANDARD_VERIFIERS,
    TYPE_ALIASES,
    infer_arg_range,
    infer_arg_type,
    infer_ret_type,
    normalize_manifest,
    normalize_raw_function,
    normalize_raw_module,
    parse_python_signature,
    resolve_type_alias,
)
from studiobridge.manifest.schema import (
    ALLOWED_PARAM_TYPES,
    ALLOWED_RET_TYPES,
    MANIFEST_JSON_SCHEMA,
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
from studiobridge.manifest.scraper import (
    DEFAULT_CACHE_DIR,
    HTMLTableExtractor,
    RawFunction,
    RawModule,
    ScraperError,
    fetch_or_cache,
    generate_original_summary,
    parse_html_table_doc,
)

__all__ = [
    "ALLOWED_PARAM_TYPES",
    "ALLOWED_RET_TYPES",
    "ArgDoc",
    "CallbackDoc",
    "DEFAULT_CACHE_DIR",
    "FunctionDoc",
    "HTMLTableExtractor",
    "MANIFEST_JSON_SCHEMA",
    "MANIFEST_SCHEMA_VERSION",
    "Manifest",
    "ManifestValidationError",
    "ModuleDoc",
    "RawFunction",
    "RawModule",
    "STANDARD_VERIFIERS",
    "ScraperError",
    "TYPE_ALIASES",
    "VerifySpec",
    "fetch_or_cache",
    "generate_original_summary",
    "infer_arg_range",
    "infer_arg_type",
    "infer_conservative_mutating",
    "infer_ret_type",
    "normalize_manifest",
    "normalize_raw_function",
    "normalize_raw_module",
    "parse_html_table_doc",
    "parse_python_signature",
    "resolve_type_alias",
    "validate_manifest_dict",
]
