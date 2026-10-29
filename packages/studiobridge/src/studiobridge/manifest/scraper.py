"""Documentation scraper and HTML table parser for FL Studio MIDI scripting API.

Extracts factual function signatures, parameter descriptions, return types, version tags,
and constants from official documentation tables while generating original summary text [LEGAL-01].
All raw HTML is cached strictly in .cache/ and never committed to version control.
"""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_CACHE_DIR: Path = Path(".cache/manifest_html")

_SIG_RE = re.compile(
    r"^(?:def\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)(?:\s*->\s*([a-zA-Z_0-9\[\],\s]+))?"
)
_VERSION_RE = re.compile(r"(?:api|version|v|fl\s*studio)?\s*(\d+)", re.IGNORECASE)
_FOOTNOTE_RE = re.compile(r"(?:\*(\d+)|\((\d+)\)|\[(\d+)\]|api\s*(\d+)\+?)", re.IGNORECASE)


@dataclass
class RawFunction:
    """Intermediate extracted raw function descriptor before normalization."""

    name: str
    raw_signature: str
    module: str
    raw_args: list[dict[str, str]] = field(default_factory=list)
    raw_return: str = ""
    since: int = 1
    doc: str = ""
    summary: str = ""
    footnotes: dict[str, int] = field(default_factory=dict)


@dataclass
class RawModule:
    """Intermediate extracted raw module descriptor."""

    name: str
    functions: list[RawFunction] = field(default_factory=list)
    constants: dict[str, int | str | float] = field(default_factory=dict)
    summary: str = ""


class ScraperError(Exception):
    """Raised when HTML parsing or documentation scraping fails."""


class HTMLTableExtractor(HTMLParser):
    """HTML parser to extract tables of function documentation."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._cell_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self._current_table = []
        elif tag_lower == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag_lower in ("td", "th") and self._current_row is not None:
            self._current_cell = []
            self._cell_tag = tag_lower
        elif tag_lower == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if (
            tag_lower in ("td", "th")
            and self._current_cell is not None
            and self._current_row is not None
        ):
            cell_text = "".join(self._current_cell).strip()
            self._current_row.append(cell_text)
            self._current_cell = None
            self._cell_tag = None
        elif (
            tag_lower == "tr" and self._current_row is not None and self._current_table is not None
        ):
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag_lower == "table" and self._current_table is not None:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = None

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def generate_original_summary(module: str, func_name: str, args: list[str], ret: str) -> str:
    """Generate original factual summary text to comply with [LEGAL-01].

    Instead of copying proprietary creative prose from official manual pages,
    we synthesize a clean, factual explanation of the function's responsibility.
    """
    lower_fn = func_name.lower()

    if lower_fn.startswith("get"):
        subject = func_name[3:]
        # Convert camelCase to words
        words = re.sub(r"([A-Z])", r" \1", subject).strip().lower()
        return f"Retrieve the {words} for {module}."
    elif lower_fn.startswith("set"):
        subject = func_name[3:]
        words = re.sub(r"([A-Z])", r" \1", subject).strip().lower()
        return f"Set the {words} for {module}."
    elif lower_fn.startswith("is"):
        subject = func_name[2:]
        words = re.sub(r"([A-Z])", r" \1", subject).strip().lower()
        return f"Query whether {module} {words} is active or true."
    elif lower_fn.endswith("count") or lower_fn.startswith("count"):
        return f"Return the total count of {module} elements."
    elif lower_fn.startswith("mute"):
        return f"Toggle or set mute state for {module}."
    elif lower_fn.startswith("solo"):
        return f"Toggle or set solo state for {module}."
    elif lower_fn.startswith("select"):
        return f"Select the active item in {module}."
    elif lower_fn in ("start", "stop", "record"):
        return f"Perform {func_name} transport command."
    elif lower_fn in ("undo", "redo", "undoup"):
        return f"Execute {func_name} history action in {module}."
    elif lower_fn in ("showwindow", "hidewindow"):
        return f"{func_name[:4].capitalize()} the specified window."

    words = re.sub(r"([A-Z])", r" \1", func_name).strip().lower()
    return f"Execute {words} in {module}."


def fetch_or_cache(
    url: str,
    cache_dir: Path | str | None = None,
    force_refresh: bool = False,
    timeout: float = 15.0,
) -> str:
    """Fetch an HTML page or retrieve from local .cache/ directory.

    Strictly protects against committing raw HTML files [LEGAL-01].
    """
    cache_path_root = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    cache_path_root.mkdir(parents=True, exist_ok=True)

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    sanitized_name = re.sub(r"[^a-zA-Z0-9_-]", "_", url.split("/")[-1] or "page")
    cache_file = cache_path_root / f"{sanitized_name}_{url_hash}.html"

    if not force_refresh and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "StudioBridge-Manifest-Scraper/0.2.0 (FL Studio API Scraper)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_bytes = resp.read()
            html_content = content_bytes.decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")
        raise ScraperError(f"Failed to fetch {url}: {exc}") from exc

    cache_file.write_text(html_content, encoding="utf-8")
    return html_content


def parse_html_table_doc(
    html_content: str,
    module_name: str,
    default_since: int = 1,
) -> RawModule:
    """Parse HTML tables from documentation into a RawModule descriptor.

    Identifies signature syntax, parameter rows, return values, versions,
    and footnotes.
    """
    extractor = HTMLTableExtractor()
    extractor.feed(html_content)

    functions: list[RawFunction] = []
    constants: dict[str, int | str | float] = {}

    for table in extractor.tables:
        if not table:
            continue

        # Look at the first row to determine column mappings
        header = [col.strip().lower() for col in table[0]]
        sig_col: int = 0
        desc_col: int = -1
        ret_col: int = -1
        ver_col: int = -1

        for idx, col_name in enumerate(header):
            if any(term in col_name for term in ("syntax", "function", "name", "method")):
                sig_col = idx
            elif any(term in col_name for term in ("desc", "description", "details", "notes")):
                desc_col = idx
            elif any(term in col_name for term in ("return", "result", "type")):
                ret_col = idx
            elif any(term in col_name for term in ("version", "since", "api")):
                ver_col = idx

        has_header = (
            len(table) > 1
            and "(" not in header[sig_col]
            and sig_col != -1
            and (desc_col != -1 or ret_col != -1 or ver_col != -1)
            and any(
                term in "".join(header)
                for term in (
                    "syntax",
                    "function",
                    "parameters",
                    "name",
                    "desc",
                    "return",
                    "version",
                    "api",
                )
            )
        )
        data_rows = table[1:] if has_header else table

        for row in data_rows:
            if not row or len(row) <= sig_col:
                continue

            raw_sig = " ".join(row[sig_col].split())
            if not raw_sig:
                continue

            # Check if this row is a constant definition, e.g. CONST_NAME = 123
            const_match = re.match(
                r"^([A-Z0-9_]+)\s*=\s*(-?\d+|0x[0-9a-fA-F]+|\"[^\"]*\")", raw_sig
            )
            if const_match:
                cname = const_match.group(1)
                cval_str = const_match.group(2)
                try:
                    cval: int | str | float = (
                        int(cval_str, 0) if not cval_str.startswith('"') else cval_str.strip('"')
                    )
                except ValueError:
                    cval = cval_str
                constants[cname] = cval
                continue

            # Check if it's a function signature
            sig_m = _SIG_RE.match(raw_sig)
            if not sig_m:
                # Might just be function name alone e.g. "setTrackVolume"
                name_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\((.*)\))?", raw_sig)
                if not name_match:
                    continue
                func_name = name_match.group(1)
                args_str = name_match.group(2) or ""
                return_type_annot = ""
            else:
                func_name = sig_m.group(1)
                args_str = sig_m.group(2) or ""
                return_type_annot = sig_m.group(3) or ""

            # Check description column
            doc_text = row[desc_col].strip() if desc_col != -1 and len(row) > desc_col else ""
            ret_text = (
                row[ret_col].strip() if ret_col != -1 and len(row) > ret_col else return_type_annot
            )

            # Check version column
            since_ver = default_since
            if ver_col != -1 and len(row) > ver_col:
                ver_cell = row[ver_col].strip()
                v_m = _VERSION_RE.search(ver_cell)
                if v_m:
                    since_ver = int(v_m.group(1))

            # Parse arguments string into individual raw argument mappings
            raw_args: list[dict[str, str]] = []
            arg_tokens = [a.strip() for a in args_str.split(",") if a.strip()]
            arg_names: list[str] = []

            for token in arg_tokens:
                arg_dict: dict[str, str] = {"raw": token}
                # Check for footnotes or version tags in argument, e.g. pickupMode (API 16+)
                fn_match = _FOOTNOTE_RE.search(token)
                clean_token = re.sub(r"\[.*?\]|\(.*?\)", "", token).strip()

                if "=" in clean_token:
                    pname, pdef = clean_token.split("=", 1)
                    arg_dict["name"] = pname.strip()
                    arg_dict["default"] = pdef.strip()
                    arg_dict["optional"] = "true"
                else:
                    arg_dict["name"] = clean_token.strip()

                if ":" in arg_dict.get("name", ""):
                    pname, ptype = arg_dict["name"].split(":", 1)
                    arg_dict["name"] = pname.strip()
                    arg_dict["type"] = ptype.strip()

                if fn_match:
                    found_v = next(g for g in fn_match.groups() if g is not None)
                    arg_dict["since"] = found_v

                raw_args.append(arg_dict)
                arg_names.append(arg_dict.get("name", ""))

            summary = generate_original_summary(module_name, func_name, arg_names, ret_text)

            functions.append(
                RawFunction(
                    name=func_name,
                    raw_signature=raw_sig,
                    module=module_name,
                    raw_args=raw_args,
                    raw_return=ret_text,
                    since=since_ver,
                    doc=doc_text,
                    summary=summary,
                )
            )

    return RawModule(
        name=module_name,
        functions=functions,
        constants=constants,
        summary=f"Official {module_name} API module descriptors",
    )
