"""Pure-Python YAML and JSON loader for FLP schema profiles with zero native C dependencies.

Implements clean-room parsing of YAML profile specifications supporting nested
mappings, integer keys, scalar types, and comments per [FLP-10].
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _parse_yaml_scalar(raw: str) -> Any:
    """Parse a YAML scalar string into int, float, bool, None, or str."""
    s = raw.strip()
    if not s:
        return ""

    # Quoted string
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]

    # Booleans & Null
    s_lower = s.lower()
    if s_lower in ("true", "yes", "on"):
        return True
    if s_lower in ("false", "no", "off"):
        return False
    if s_lower in ("null", "none", "~"):
        return None

    # Integers
    try:
        return int(s)
    except ValueError:
        pass

    # Floats
    try:
        return float(s)
    except ValueError:
        pass

    return s


def parse_yaml_dict(text: str) -> dict[str | int, Any]:
    """Parse a YAML string representing a dictionary into a Python dict.

    Uses PyYAML if available; falls back to a pure-Python indentation-based parser
    supporting comments, nested mappings, integer keys, and typed scalars.
    """
    text = text.strip()
    if not text:
        return {}

    # Check for pure JSON
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # Try PyYAML if available
    try:
        import yaml  # type: ignore[import-untyped,import-not-found]

        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded
    except (ImportError, Exception):
        pass

    # Pure-Python indentation-based block mapping parser
    lines = text.splitlines()
    cleaned_lines: list[tuple[int, str]] = []

    for raw_line in lines:
        stripped = raw_line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue

        # Strip inline comments (outside quotes)
        in_quote = False
        quote_char = ""
        comment_idx = -1
        for i, ch in enumerate(stripped):
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quote = False
            elif ch == "#" and not in_quote:
                comment_idx = i
                break

        if comment_idx != -1:
            stripped = stripped[:comment_idx].rstrip()
            if not stripped:
                continue

        indent = len(stripped) - len(stripped.lstrip(" "))
        content = stripped.lstrip(" ")
        cleaned_lines.append((indent, content))

    if not cleaned_lines:
        return {}

    def _parse_block(start_idx: int, expected_indent: int) -> tuple[dict[str | int, Any], int]:
        result: dict[str | int, Any] = {}
        idx = start_idx

        while idx < len(cleaned_lines):
            indent, line = cleaned_lines[idx]

            if indent < expected_indent:
                # Returned to outer block
                break
            if indent > expected_indent:
                # Unexpected indentation jump
                break

            if ":" not in line:
                idx += 1
                continue

            k_part, v_part = line.split(":", 1)
            raw_key = _parse_yaml_scalar(k_part)
            key: str | int = raw_key if isinstance(raw_key, (int, str)) else str(raw_key)
            val_str = v_part.strip()

            if val_str:
                # Inline scalar value
                result[key] = _parse_yaml_scalar(val_str)
                idx += 1
            else:
                # Nested block starting on next line
                next_idx = idx + 1
                if next_idx < len(cleaned_lines) and cleaned_lines[next_idx][0] > indent:
                    child_indent = cleaned_lines[next_idx][0]
                    child_dict, next_idx = _parse_block(next_idx, child_indent)
                    result[key] = child_dict
                    idx = next_idx
                else:
                    result[key] = {}
                    idx = next_idx

        return result, idx

    parsed_root, _ = _parse_block(0, cleaned_lines[0][0])
    return parsed_root


def load_yaml_file(path: Path | str) -> dict[str | int, Any]:
    """Read and parse a YAML file from disk into a Python dictionary."""
    p = Path(path)
    content = p.read_text(encoding="utf-8")
    return parse_yaml_dict(content)
