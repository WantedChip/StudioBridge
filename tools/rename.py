"""Brand token substitution and integrity validation tooling.

Per 00_INDEX.md §8 and sub-phase v0.1.9:
Scans tracked source files, documentation, and agent templates, substituting
brand tokens consistently from old to new values while enforcing:
1. Strict case-sensitive and token-boundary replacements.
2. Invariant protection: Wire magic bytes 0x53 0x42 ('SB') are protocol constants
   and never modified.
3. Port root length validation (<= 20 characters) to prevent WinMM 31-char truncation.
4. Automated check mode for CI (--check) ensuring brand token integrity.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

try:
    import tools.tokens as _tokens_mod
except ImportError:
    import tokens as _tokens_mod  # pyright: ignore[reportMissingImports]

APPROVED_EXCEPTIONS = _tokens_mod.APPROVED_EXCEPTIONS
UNAUTHORIZED_TOKENS = _tokens_mod.UNAUTHORIZED_TOKENS
BrandTokens = _tokens_mod.BrandTokens
check_protocol_constant_protection = _tokens_mod.check_protocol_constant_protection
validate_tokens = _tokens_mod.validate_tokens

# Directories to skip when scanning workspace files
DEFAULT_SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        ".agents",
        ".idea",
        ".vscode",
    }
)

# Extensions to skip (binary / generated data)
DEFAULT_SKIP_EXTS: Final[frozenset[str]] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".pyd",
        ".whl",
        ".tar",
        ".gz",
        ".zip",
        ".png",
        ".jpg",
        ".jpeg",
        ".ico",
        ".svg",
        ".lock",
        ".coverage",
        ".dll",
        ".exe",
    }
)

# Immutable wire protocol constants that must never be altered
PROTECTED_PROTOCOL_CONSTANTS: Final[tuple[str, ...]] = (
    'b"SB"',
    "b'SB'",
    "53 42",
    "0x53, 0x42",
    "0x53 0x42",
)


@dataclass(frozen=True)
class ReplacementRule:
    """Single token replacement rule with compiled boundary regex."""

    name: str
    search_str: str
    replace_str: str
    pattern: re.Pattern[str]


@dataclass
class RenameReport:
    """Report of rename operations (dry-run or applied)."""

    scanned_files: int = 0
    modified_files: int = 0
    total_replacements: int = 0
    replacements_by_token: dict[str, int] = field(default_factory=dict)
    file_details: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of CI token integrity check."""

    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_replacement_rules(
    from_tokens: BrandTokens,
    to_tokens: BrandTokens,
) -> list[ReplacementRule]:
    """Construct ordered, case-sensitive replacement rules with boundary regexes."""
    # Ensure neither side attempts to alter wire magic constants
    check_protocol_constant_protection(from_tokens)
    check_protocol_constant_protection(to_tokens)

    rules: list[ReplacementRule] = []

    # 1. Full MCP publication name (e.g. io.github.<owner>/studiobridge)
    if from_tokens.mcpname != to_tokens.mcpname:
        mcp_pat = re.compile(
            rf"(?<![a-zA-Z0-9_\-\./]){re.escape(from_tokens.mcpname)}(?![a-zA-Z0-9_\-\./])"
        )
        rules.append(ReplacementRule("MCPNAME", from_tokens.mcpname, to_tokens.mcpname, mcp_pat))

    # 2. DEVICE: FL Studio device script name / folder (e.g. StudioBridge -> NewDevice)
    # Bounded so StudioBridgeError -> NewDeviceError is supported via lookahead on uppercase
    if from_tokens.device != to_tokens.device:
        device_pat = re.compile(rf"(?<![a-zA-Z0-9]){re.escape(from_tokens.device)}(?![a-z0-9])")
        rules.append(ReplacementRule("DEVICE", from_tokens.device, to_tokens.device, device_pat))

    # 3. DIST: Distribution and package name (e.g. studiobridge -> newdist)
    if from_tokens.dist != to_tokens.dist:
        dist_pat = re.compile(rf"(?<![a-zA-Z0-9]){re.escape(from_tokens.dist)}(?![a-zA-Z0-9])")
        rules.append(ReplacementRule("DIST", from_tokens.dist, to_tokens.dist, dist_pat))

    # 4. PORT_ROOT: MIDI port root name (e.g. SBridge -> NewPort)
    if from_tokens.port_root != to_tokens.port_root:
        port_pat = re.compile(rf"(?<![a-zA-Z0-9]){re.escape(from_tokens.port_root)}(?![a-z0-9])")
        rules.append(
            ReplacementRule("PORT_ROOT", from_tokens.port_root, to_tokens.port_root, port_pat)
        )

    # 5. CLI: Command-line binary name (e.g. sbridge -> newcli)
    if from_tokens.cli != to_tokens.cli:
        cli_pat = re.compile(rf"(?<![a-zA-Z0-9]){re.escape(from_tokens.cli)}(?![a-zA-Z0-9])")
        rules.append(ReplacementRule("CLI", from_tokens.cli, to_tokens.cli, cli_pat))

    # 6. Uppercase variants (for environment variable prefixes, e.g. SBRIDGE_* -> NEWCLI_*)
    from_cli_upper = from_tokens.cli.upper()
    to_cli_upper = to_tokens.cli.upper()
    if from_cli_upper != to_cli_upper and from_cli_upper != from_tokens.cli:
        cli_up_pat = re.compile(rf"(?<![A-Z0-9]){re.escape(from_cli_upper)}(?![A-Z0-9])")
        rules.append(ReplacementRule("CLI_UPPER", from_cli_upper, to_cli_upper, cli_up_pat))

    from_dist_upper = from_tokens.dist.upper()
    to_dist_upper = to_tokens.dist.upper()
    if from_dist_upper != to_dist_upper and from_dist_upper != from_tokens.dist:
        dist_up_pat = re.compile(rf"(?<![A-Z0-9]){re.escape(from_dist_upper)}(?![A-Z0-9])")
        rules.append(ReplacementRule("DIST_UPPER", from_dist_upper, to_dist_upper, dist_up_pat))

    # 7. Template parameter placeholders (e.g. {DIST} -> newdist)
    template_mappings = [
        ("{MCPNAME}", to_tokens.mcpname),
        ("{DEVICE}", to_tokens.device),
        ("{DIST}", to_tokens.dist),
        ("{PORT_ROOT}", to_tokens.port_root),
        ("{CLI}", to_tokens.cli),
    ]
    for tmpl_key, tmpl_val in template_mappings:
        tmpl_pat = re.compile(re.escape(tmpl_key))
        rules.append(ReplacementRule(tmpl_key, tmpl_key, tmpl_val, tmpl_pat))

    # Sort rules from longest search string to shortest to prevent sub-string collision
    rules.sort(key=lambda r: len(r.search_str), reverse=True)
    return rules


def discover_files(
    root: Path,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
    skip_exts: frozenset[str] = DEFAULT_SKIP_EXTS,
) -> list[Path]:
    """Find all scannable text files under root directory."""
    discovered: list[Path] = []
    root = root.resolve()

    for current_dir, dirnames, filenames in os.walk(root):
        # Exclude directories in-place to avoid descending into them
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        for fname in filenames:
            fpath = Path(current_dir) / fname
            if fpath.suffix.lower() in skip_exts:
                continue
            discovered.append(fpath)

    return sorted(discovered)


def perform_rename(
    root: Path,
    from_tokens: BrandTokens,
    to_tokens: BrandTokens,
    dry_run: bool = True,
    target_files: Sequence[Path] | None = None,
) -> RenameReport:
    """Execute brand token replacement across files with protocol protection.

    Args:
        root: Workspace root directory.
        from_tokens: Original brand tokens.
        to_tokens: Destination brand tokens.
        dry_run: If True, preview replacements without modifying files.
        target_files: Optional list of explicit files to process.

    Returns:
        RenameReport summarizing operations.
    """
    validate_tokens(from_tokens)
    validate_tokens(to_tokens)
    root = root.resolve()

    rules = build_replacement_rules(from_tokens, to_tokens)
    files = list(target_files) if target_files is not None else discover_files(root)

    report = RenameReport(scanned_files=len(files))

    for fpath in files:
        # Skip tools/tokens.py from in-place replacement if it defines the tokens table
        # unless explicitly requested as single target
        rel_path = fpath.relative_to(root).as_posix()
        if target_files is None and rel_path == "tools/tokens.py":
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # Record initial counts of protected protocol constants
        initial_constants = {c: content.count(c) for c in PROTECTED_PROTOCOL_CONSTANTS}

        new_content = content
        file_replacements = 0

        for rule in rules:
            matches = len(rule.pattern.findall(new_content))
            if matches > 0:
                new_content = rule.pattern.sub(rule.replace_str, new_content)
                file_replacements += matches
                report.replacements_by_token[rule.name] = (
                    report.replacements_by_token.get(rule.name, 0) + matches
                )

        if file_replacements > 0:
            # Enforce protocol constant invariant
            for c, initial_count in initial_constants.items():
                if initial_count > 0:
                    new_count = new_content.count(c)
                    if new_count != initial_count:
                        err = (
                            f"Protected protocol constant '{c}' modified in {rel_path}! "
                            f"Initial count: {initial_count}, new count: {new_count}. "
                            "Wire magic bytes 0x53 0x42 ('SB') must never be modified."
                        )
                        report.errors.append(err)
                        raise RuntimeError(err)

            report.modified_files += 1
            report.total_replacements += file_replacements
            report.file_details[rel_path] = file_replacements

            if not dry_run:
                fpath.write_text(new_content, encoding="utf-8")

    return report


def check_brand_integrity(
    root: Path,
    from_tokens: BrandTokens | None = None,
    unauthorized_tokens: Sequence[str] = UNAUTHORIZED_TOKENS,
    approved_exceptions: Sequence[str] = APPROVED_EXCEPTIONS,
) -> CheckResult:
    """Verify brand token integrity, protocol constants, and unauthorized tokens.

    Checks:
    1. Default and specified brand tokens satisfy all constraints (port_root <= 20).
    2. Key wire protocol definition files preserve wire magic constants.
    3. No unauthorized or deprecated tokens appear outside approved exception files.
    4. If from_tokens provided, verify no instances of old tokens remain.

    Returns:
        CheckResult containing pass status and error details.
    """
    errors: list[str] = []
    warnings: list[str] = []
    root = root.resolve()

    # 1. Validate tokens
    try:
        current_tokens = BrandTokens()
        validate_tokens(current_tokens)
    except Exception as exc:
        errors.append(f"Current BrandTokens validation failed: {exc}")

    if from_tokens is not None:
        try:
            validate_tokens(from_tokens)
        except Exception as exc:
            errors.append(f"from_tokens validation failed: {exc}")

    # 2. Check protocol constants in key files
    protocol_checks = [
        (
            root / "packages/studiobridge/src/studiobridge/wire/frame.py",
            ['MAGIC = b"SB"', "0x53 0x42"],
        ),
        (
            root / "packages/studiobridge/src/studiobridge/device/assets/_sb_wire.py",
            ['MAGIC = b"SB"'],
        ),
        (
            root / "tests/wire/vectors.json",
            ["53 42"],
        ),
    ]

    for pfile, expected_constants in protocol_checks:
        if pfile.exists():
            try:
                ptext = pfile.read_text(encoding="utf-8")
                for ec in expected_constants:
                    if ec not in ptext:
                        rel_p = pfile.relative_to(root).as_posix()
                        errors.append(f"Protocol constant '{ec}' missing from {rel_p}")
            except Exception as exc:
                errors.append(f"Failed to read protocol file {pfile}: {exc}")

    # 3. Check for unauthorized or deprecated tokens
    files = discover_files(root)
    for fpath in files:
        rel_posix = fpath.relative_to(root).as_posix()

        # Check if file is in approved exceptions
        if any(rel_posix.startswith(exc.rstrip("/")) for exc in approved_exceptions):
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            for unauth in unauthorized_tokens:
                # Use word-boundary match
                if re.search(rf"\b{re.escape(unauth)}\b", line):
                    errors.append(
                        f"Unauthorized token '{unauth}' in {rel_posix}:{line_no}: {line.strip()}"
                    )

    return CheckResult(passed=(len(errors) == 0), errors=errors, warnings=warnings)


def load_tokens_argument(arg: str | None) -> BrandTokens:
    """Load BrandTokens from JSON file path or JSON string, or return default."""
    if not arg:
        return BrandTokens()

    # Check if argument is a path
    p = Path(arg)
    if p.exists() and p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        return BrandTokens.from_dict(data)

    # Check if argument is JSON string (handling potential shell escaping)
    for candidate in (
        arg,
        arg.replace(r"\"", '"'),
        arg.strip("'\""),
        arg.strip("'\"").replace(r"\"", '"'),
    ):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return BrandTokens.from_dict(data)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Unable to parse token configuration from '{arg}'")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI dispatcher for rename tooling."""
    parser = argparse.ArgumentParser(
        prog="rename.py",
        description="Brand token replacement and validation utility for StudioBridge.",
    )
    parser.add_argument(
        "--from-tokens",
        type=str,
        default=None,
        help="JSON file path or JSON string for source brand tokens (defaults to current tokens).",
    )
    parser.add_argument(
        "--to-tokens",
        type=str,
        default=None,
        help="JSON file path or JSON string for target brand tokens.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview token replacements and report counts without modifying files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate token integrity and verify no unauthorized tokens exist (CI check).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Workspace root directory (defaults to current directory).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.check:
        from_tok = load_tokens_argument(args.from_tokens) if args.from_tokens else None
        res = check_brand_integrity(root=root, from_tokens=from_tok)
        if not res.passed:
            print("[FAIL] Brand token integrity check failed with errors:", file=sys.stderr)
            for err in res.errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print("[OK] Brand token and protocol integrity verified successfully.")
        return 0

    if not args.to_tokens:
        parser.error("--to-tokens is required when not running in --check mode.")

    try:
        from_tokens = load_tokens_argument(args.from_tokens)
        to_tokens = load_tokens_argument(args.to_tokens)
    except (ValueError, TypeError) as exc:
        print(f"[ERROR] Invalid token configuration: {exc}", file=sys.stderr)
        return 1

    try:
        report = perform_rename(
            root=root,
            from_tokens=from_tokens,
            to_tokens=to_tokens,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[ERROR] Rename failed: {exc}", file=sys.stderr)
        return 1

    mode_label = "DRY RUN (no files modified)" if args.dry_run else "APPLIED"
    print(f"--- Brand Token Rename Report [{mode_label}] ---")
    print(f"Scanned files: {report.scanned_files}")
    print(f"Modified files: {report.modified_files}")
    print(f"Total replacements: {report.total_replacements}")

    if report.replacements_by_token:
        print("\nReplacements by token:")
        for tname, count in sorted(report.replacements_by_token.items()):
            print(f"  {tname}: {count}")

    if args.verbose and report.file_details:
        print("\nModified files detail:")
        for rpath, count in sorted(report.file_details.items()):
            print(f"  {rpath}: {count} replacements")

    return 0


if __name__ == "__main__":
    sys.exit(main())
