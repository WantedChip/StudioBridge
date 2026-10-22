"""Quirks overlay parser and merger with [MAN-02] citation validation.

Parses YAML/JSON quirks overlays specifying paired getters, verification tolerances,
safety protections, and empirical hardware notes per 05_l0c_device_script_manifest.md §15.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.manifest.schema import (
    ArgDoc,
    FunctionDoc,
    Manifest,
    ManifestValidationError,
    ModuleDoc,
    VerifySpec,
)

OVERLAYS_DIR: Path = Path(__file__).parent / "overlays"
DEFAULT_QUIRKS_FILE: Path = OVERLAYS_DIR / "fl_quirks.yaml"


class OverlayValidationError(ManifestValidationError):
    """Raised when a quirks overlay fails [MAN-02] or structural validation."""


@dataclass
class OverlayEntry:
    """A single quirks overlay entry modifying a function's specification."""

    fn: str
    evidence: list[str] = field(default_factory=list)
    test: str = ""
    note: str = ""
    severity: str = "warn"
    verify: VerifySpec | dict[str, Any] | None = None
    mutating: bool | None = None
    protected: bool = False
    undo: str | None = None
    args: list[ArgDoc] | list[dict[str, Any]] | None = None
    ret: str | None = None
    undocumented: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.evidence, str):
            self.evidence = [self.evidence] if self.evidence.strip() else []
        elif isinstance(self.evidence, (list, tuple)):
            self.evidence = [str(e).strip() for e in self.evidence if str(e).strip()]
        else:
            self.evidence = []

        self.test = str(self.test).strip() if self.test else ""

    def validate_man02(self) -> list[str]:
        """Validate [MAN-02] invariant: evidence citation and live test link."""
        errors: list[str] = []
        if not self.fn or "." not in self.fn:
            errors.append(f"Overlay entry has invalid fn '{self.fn}'; must be 'module.function'")

        if not self.evidence or not any(str(e).strip() for e in self.evidence):
            errors.append(
                f"[MAN-02] Overlay entry '{self.fn}' must cite evidence (non-empty citation)"
            )

        if not self.test or not self.test.strip():
            errors.append(
                f"[MAN-02] Overlay entry '{self.fn}' must link to a live test or spike "
                f"(e.g. tests/live/... or spike:Sx)"
            )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        d: dict[str, Any] = {
            "fn": self.fn,
            "evidence": list(self.evidence),
            "test": self.test,
        }
        if self.note:
            d["note"] = self.note
        if self.severity != "warn":
            d["severity"] = self.severity
        if self.verify is not None:
            if isinstance(self.verify, VerifySpec):
                d["verify"] = self.verify.to_dict()
            else:
                d["verify"] = dict(self.verify)
        if self.mutating is not None:
            d["mutating"] = self.mutating
        if self.protected:
            d["protected"] = True
        if self.undo:
            d["undo"] = self.undo
        if self.ret:
            d["ret"] = self.ret
        if self.undocumented:
            d["undocumented"] = True
        if self.extra:
            d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverlayEntry:
        """Construct an OverlayEntry from raw dictionary data."""
        data_copy = dict(data)
        fn = str(data_copy.pop("fn", ""))
        evidence = data_copy.pop("evidence", [])
        test = str(data_copy.pop("test", ""))
        note = str(data_copy.pop("note", ""))
        severity = str(data_copy.pop("severity", "warn"))
        verify_data = data_copy.pop("verify", None)
        mutating = data_copy.pop("mutating", None)
        protected = bool(data_copy.pop("protected", False))
        undo = data_copy.pop("undo", None)
        args = data_copy.pop("args", None)
        ret = data_copy.pop("ret", None)
        undocumented = bool(data_copy.pop("undocumented", False))

        return cls(
            fn=fn,
            evidence=evidence,
            test=test,
            note=note,
            severity=severity,
            verify=verify_data,
            mutating=mutating,
            protected=protected,
            undo=undo,
            args=args,
            ret=ret,
            undocumented=undocumented,
            extra=data_copy,
        )


@dataclass
class QuirksOverlay:
    """Collection of quirks overlay entries with validation and application."""

    entries: list[OverlayEntry] = field(default_factory=list)

    def get(self, fn: str) -> OverlayEntry | None:
        """Find and return an overlay entry by function name or None."""
        for entry in self.entries:
            if entry.fn == fn:
                return entry
        return None

    def validate(self) -> list[str]:
        """Validate all entries against [MAN-02] rules."""
        errors: list[str] = []
        for entry in self.entries:
            errors.extend(entry.validate_man02())
        return errors

    def apply(self, manifest: Manifest) -> Manifest:
        """Apply overlay entries onto a Manifest in-place and return it."""
        errors = self.validate()
        if errors:
            raise OverlayValidationError(
                "Quirks overlay failed [MAN-02] validation:\n- " + "\n- ".join(errors)
            )

        for entry in self.entries:
            mod_name, fn_name = entry.fn.split(".", 1)
            if mod_name not in manifest.modules:
                if entry.undocumented:
                    manifest.modules[mod_name] = ModuleDoc(name=mod_name)
                else:
                    continue

            mod = manifest.modules[mod_name]
            if fn_name not in mod.functions:
                if entry.undocumented:
                    fn_doc = FunctionDoc(
                        name=fn_name,
                        mutating=entry.mutating,
                        protected=entry.protected,
                        summary=entry.note,
                        undocumented=True,
                    )
                    mod.functions[fn_name] = fn_doc
                else:
                    continue
            else:
                fn_doc = mod.functions[fn_name]

            if entry.mutating is not None:
                fn_doc.mutating = entry.mutating
            if entry.protected:
                fn_doc.protected = entry.protected
            if entry.undo is not None:
                fn_doc.undo = entry.undo
            if entry.ret is not None:
                fn_doc.ret = entry.ret
            if entry.undocumented:
                fn_doc.undocumented = True

            if entry.note:
                if fn_doc.summary:
                    fn_doc.summary = f"{fn_doc.summary} (Quirk: {entry.note})"
                else:
                    fn_doc.summary = entry.note

            if entry.verify is not None:
                if isinstance(entry.verify, VerifySpec):
                    fn_doc.verify = entry.verify
                elif isinstance(entry.verify, dict):
                    v_dict = dict(entry.verify)
                    getter = v_dict.get("getter")
                    if not getter:
                        getter = fn_doc.verify.getter if fn_doc.verify else f"{mod_name}.{fn_name}"

                    if getter and "." not in getter:
                        getter = f"{mod_name}.{getter}"

                    compare = v_dict.get(
                        "compare", fn_doc.verify.compare if fn_doc.verify else "exact"
                    )
                    tol = v_dict.get("tol", fn_doc.verify.tol if fn_doc.verify else None)
                    settle = v_dict.get(
                        "settle", fn_doc.verify.settle if fn_doc.verify else "immediate"
                    )
                    args = v_dict.get("args", fn_doc.verify.args if fn_doc.verify else [0])

                    fn_doc.verify = VerifySpec(
                        getter=getter,
                        args=args,
                        compare=compare,
                        tol=tol,
                        settle=settle,
                    )

        return manifest


def _parse_yaml_scalar(token: str) -> Any:
    """Parse a single YAML scalar token (string, number, bool, null, flow list/dict)."""
    token = token.strip()
    if not token:
        return ""

    # Quoted string
    if (token.startswith('"') and token.endswith('"')) or (
        token.startswith("'") and token.endswith("'")
    ):
        return token[1:-1]

    # Booleans
    if token.lower() in ("true", "yes", "on"):
        return True
    if token.lower() in ("false", "no", "off"):
        return False
    if token.lower() in ("null", "none", "~"):
        return None

    # Flow sequence [a, b, c]
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        items: list[Any] = []
        for part in _split_flow_items(inner):
            items.append(_parse_yaml_scalar(part))
        return items

    # Flow mapping {a: 1, b: 2}
    if token.startswith("{") and token.endswith("}"):
        inner = token[1:-1].strip()
        if not inner:
            return {}
        mapping: dict[str, Any] = {}
        for part in _split_flow_items(inner):
            if ":" in part:
                k, v = part.split(":", 1)
                mapping[k.strip()] = _parse_yaml_scalar(v.strip())
        return mapping

    # Integers
    try:
        return int(token)
    except ValueError:
        pass

    # Floats
    try:
        return float(token)
    except ValueError:
        pass

    return token


def _split_flow_items(text: str) -> list[str]:
    """Split comma-separated items inside flow sequence or mapping, respecting quotes and braces."""
    items: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    bracket_depth = 0
    brace_depth = 0

    for ch in text:
        if in_quote:
            if ch == in_quote:
                in_quote = None
            current.append(ch)
        else:
            if ch in ('"', "'"):
                in_quote = ch
                current.append(ch)
            elif ch == "[":
                bracket_depth += 1
                current.append(ch)
            elif ch == "]":
                bracket_depth -= 1
                current.append(ch)
            elif ch == "{":
                brace_depth += 1
                current.append(ch)
            elif ch == "}":
                brace_depth -= 1
                current.append(ch)
            elif ch == "," and bracket_depth == 0 and brace_depth == 0:
                item = "".join(current).strip()
                if item:
                    items.append(item)
                current = []
            else:
                current.append(ch)

    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def parse_overlay_yaml(text: str) -> list[dict[str, Any]]:
    """Parse YAML or JSON text defining quirks overlay entries into a list of dicts.

    Supports PyYAML if installed, falling back to a pure-Python parser for block
    sequences of mappings, inline collections, and scalar values.
    """
    text = text.strip()
    if not text:
        return []

    # If it starts with JSON array or object
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    # Try PyYAML if available
    try:
        import yaml  # type: ignore[import-untyped,import-not-found]

        loaded = yaml.safe_load(text)
        if isinstance(loaded, list):
            return loaded
        if isinstance(loaded, dict):
            return [loaded]
    except (ImportError, Exception):
        pass

    # Pure-Python line-by-line YAML parser for quirks format
    lines = text.splitlines()
    entries: list[dict[str, Any]] = []
    current_entry: dict[str, Any] | None = None
    current_block_key: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        # Skip empty lines and comment lines
        if not stripped or stripped.startswith("#"):
            continue

        # Strip trailing comments if not inside quotes
        comment_pos = -1
        in_quote = False
        quote_char = ""
        for i, ch in enumerate(line):
            if ch in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = ch
                elif ch == quote_char:
                    in_quote = False
            elif ch == "#" and not in_quote:
                comment_pos = i
                break
        if comment_pos >= 0:
            line = line[:comment_pos].rstrip()
            stripped = line.strip()
            if not stripped:
                continue

        indent = len(line) - len(line.lstrip(" "))

        # Top-level list item (indent == 0)
        if indent == 0 and stripped.startswith("- "):
            if current_entry is not None:
                entries.append(current_entry)
            current_entry = {}
            current_block_key = None
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                k, v = rest.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v:
                    current_entry[k] = _parse_yaml_scalar(v)
                else:
                    current_block_key = k
            continue

        if current_entry is None:
            continue

        # Sub-item inside block list (e.g. evidence item)
        if indent > 0 and stripped.startswith("- "):
            item_val = _parse_yaml_scalar(stripped[2:].strip())
            if current_block_key is not None:
                if current_block_key not in current_entry or not isinstance(
                    current_entry[current_block_key], list
                ):
                    current_entry[current_block_key] = []
                current_entry[current_block_key].append(item_val)
            continue

        # Key-value pair
        if ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()

            if indent >= 4 and current_block_key is not None:
                # Key inside nested mapping (e.g. verify:\n  getter: ...)
                if current_block_key not in current_entry or not isinstance(
                    current_entry[current_block_key], dict
                ):
                    current_entry[current_block_key] = {}
                current_entry[current_block_key][k] = _parse_yaml_scalar(v)
            else:
                if v:
                    current_entry[k] = _parse_yaml_scalar(v)
                    current_block_key = None
                else:
                    current_block_key = k

    if current_entry is not None:
        entries.append(current_entry)

    return entries


def load_overlay_file(path: str | Path) -> QuirksOverlay:
    """Load a quirks overlay file (YAML or JSON) and return a validated QuirksOverlay."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Overlay file not found: {p}")
    text = p.read_text(encoding="utf-8")
    raw_entries = parse_overlay_yaml(text)
    entries = [OverlayEntry.from_dict(d) for d in raw_entries]
    overlay = QuirksOverlay(entries=entries)
    errors = overlay.validate()
    if errors:
        raise OverlayValidationError(
            f"Quirks overlay '{p.name}' failed [MAN-02] validation:\n- " + "\n- ".join(errors)
        )
    return overlay


def load_default_overlay() -> QuirksOverlay:
    """Load the canonical hand-written quirks overlay from package assets."""
    if not DEFAULT_QUIRKS_FILE.exists():
        raise FileNotFoundError(f"Default quirks file not found at {DEFAULT_QUIRKS_FILE}")
    return load_overlay_file(DEFAULT_QUIRKS_FILE)


def apply_overlay(manifest: Manifest, overlay: QuirksOverlay) -> Manifest:
    """Convenience helper to apply quirks overlay to a manifest."""
    return overlay.apply(manifest)
