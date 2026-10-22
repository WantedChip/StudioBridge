"""JSON schemas and pure-Python schema validation for MCP tools and CLI commands.

Provides schema retrieval and self-contained validation adhering to the Model Context
Protocol tool input/output specifications without external dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).resolve().parent


def get_schema_path(tool_name: str) -> Path:
    """Return the absolute path to a tool's JSON schema file."""
    clean_name = tool_name.replace("studiobridge_", "")
    return SCHEMAS_DIR / f"{clean_name}.json"


def get_schema(tool_name: str) -> dict[str, Any]:
    """Load and return the JSON schema definition for a tool."""
    path = get_schema_path(tool_name)
    if not path.is_file():
        raise FileNotFoundError(f"Schema not found for tool '{tool_name}' at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(data: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Lightweight pure-Python JSON schema validator.

    Verifies:
    - type constraints (object, array, string, number, integer, boolean, null)
    - required properties
    - property definitions
    - array items
    - enums
    - minimum / maximum bounds
    """
    if not isinstance(schema, dict):
        return

    expected_type = schema.get("type")
    if expected_type is not None:
        if isinstance(expected_type, list):
            valid = any(_matches_type(data, t) for t in expected_type)
            if not valid:
                raise ValueError(
                    f"Validation failed at '{path}': expected one of {expected_type}, "
                    f"got {type(data).__name__}"
                )
        else:
            if not _matches_type(data, expected_type):
                raise ValueError(
                    f"Validation failed at '{path}': expected type '{expected_type}', "
                    f"got {type(data).__name__}"
                )

    # Enum verification
    if "enum" in schema and data not in schema["enum"]:
        raise ValueError(
            f"Validation failed at '{path}': value {data!r} is not in enum {schema['enum']}"
        )

    # Numeric bounds
    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            raise ValueError(
                f"Validation failed at '{path}': value {data} < minimum {schema['minimum']}"
            )
        if "maximum" in schema and data > schema["maximum"]:
            raise ValueError(
                f"Validation failed at '{path}': value {data} > maximum {schema['maximum']}"
            )

    # Object properties & required checks
    if isinstance(data, dict):
        required = schema.get("required", [])
        for req_prop in required:
            if req_prop not in data:
                raise ValueError(
                    f"Validation failed at '{path}': missing required property '{req_prop}'"
                )

        properties = schema.get("properties", {})
        for prop_name, prop_val in data.items():
            if prop_name in properties:
                validate_schema(prop_val, properties[prop_name], path=f"{path}.{prop_name}")
            elif schema.get("additionalProperties") is False:
                raise ValueError(
                    f"Validation failed at '{path}': unknown property '{prop_name}' "
                    f"when additionalProperties is false"
                )

    # Array items verification
    if isinstance(data, list):
        item_schema = schema.get("items")
        if item_schema is not None and isinstance(item_schema, dict):
            for idx, item in enumerate(data):
                validate_schema(item, item_schema, path=f"{path}[{idx}]")


def _matches_type(val: Any, type_name: str) -> bool:
    """Check if value matches a JSON schema type name."""
    if type_name == "null":
        return val is None
    if val is None:
        return False
    if type_name == "string":
        return isinstance(val, str)
    if type_name == "boolean":
        return isinstance(val, bool)
    if type_name == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if type_name == "number":
        return (isinstance(val, (int, float))) and not isinstance(val, bool)
    if type_name == "object":
        return isinstance(val, dict)
    if type_name == "array":
        return isinstance(val, list)
    return True


__all__ = [
    "SCHEMAS_DIR",
    "get_schema",
    "get_schema_path",
    "validate_schema",
]
