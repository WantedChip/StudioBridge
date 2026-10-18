"""Central brand token mapping and constraints for StudioBridge.

Per 00_INDEX.md §8:
All brand-bearing strings are centralized so a rename is mechanical:

| Token       | Working value                  | Where used                             |
|-------------|--------------------------------|----------------------------------------|
| {DIST}      | studiobridge                   | PyPI/npm names, import package         |
| {CLI}       | sbridge                        | console script                         |
| {PORT_ROOT} | SBridge                        | MIDI endpoint root name (<= 20 chars)  |
| {DEVICE}    | StudioBridge                   | FL device script folder / header name  |
| {MCPNAME}   | io.github.<owner>/studiobridge | MCP registry name                      |
| Wire magic  | bytes 53 42 ("SB")             | Protocol constant; never renamed       |

EXPLICIT INVARIANT:
Wire magic bytes 0x53 0x42 ("SB") are protocol constants and never modified.
They are not brand tokens and must never be altered or mapped during a rename.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

# Protocol constants - NEVER modified by rename tooling
WIRE_MAGIC_BYTES: Final[tuple[int, int]] = (0x53, 0x42)
WIRE_MAGIC: Final[bytes] = b"SB"
WIRE_MAGIC_HEX: Final[str] = "53 42"

# Maximum length for PORT_ROOT to prevent WinMM 31-character truncation
MAX_PORT_ROOT_LENGTH: Final[int] = 20

# Canonical working brand tokens
DEFAULT_DIST: Final[str] = "studiobridge"
DEFAULT_CLI: Final[str] = "sbridge"
DEFAULT_PORT_ROOT: Final[str] = "SBridge"
DEFAULT_DEVICE: Final[str] = "StudioBridge"
DEFAULT_MCPNAME: Final[str] = "io.github.<owner>/studiobridge"


@dataclass(frozen=True)
class BrandTokens:
    """Immutable collection of brand tokens."""

    dist: str = DEFAULT_DIST
    cli: str = DEFAULT_CLI
    port_root: str = DEFAULT_PORT_ROOT
    device: str = DEFAULT_DEVICE
    mcpname: str = DEFAULT_MCPNAME

    def __post_init__(self) -> None:
        """Validate token invariants upon instantiation."""
        validate_tokens(self)

    def as_dict(self) -> dict[str, str]:
        """Return token dictionary with bare token names (e.g. 'DIST')."""
        return {
            "DIST": self.dist,
            "CLI": self.cli,
            "PORT_ROOT": self.port_root,
            "DEVICE": self.device,
            "MCPNAME": self.mcpname,
        }

    def as_template_dict(self) -> dict[str, str]:
        """Return token dictionary with braced template token names (e.g. '{DIST}')."""
        return {
            "{DIST}": self.dist,
            "{CLI}": self.cli,
            "{PORT_ROOT}": self.port_root,
            "{DEVICE}": self.device,
            "{MCPNAME}": self.mcpname,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BrandTokens:
        """Create BrandTokens from dictionary with bare or braced keys."""
        normalized: dict[str, str] = {}
        for k, v in data.items():
            clean_k = k.strip("{}").lower()
            normalized[clean_k] = str(v)

        return cls(
            dist=normalized.get("dist", DEFAULT_DIST),
            cli=normalized.get("cli", DEFAULT_CLI),
            port_root=normalized.get("port_root", DEFAULT_PORT_ROOT),
            device=normalized.get("device", DEFAULT_DEVICE),
            mcpname=normalized.get("mcpname", DEFAULT_MCPNAME),
        )


DEFAULT_TOKENS: Final[dict[str, str]] = {
    "DIST": DEFAULT_DIST,
    "CLI": DEFAULT_CLI,
    "PORT_ROOT": DEFAULT_PORT_ROOT,
    "DEVICE": DEFAULT_DEVICE,
    "MCPNAME": DEFAULT_MCPNAME,
}

TEMPLATE_TOKENS: Final[dict[str, str]] = {f"{{{k}}}": v for k, v in DEFAULT_TOKENS.items()}

# Unauthorized or deprecated tokens that must not be hardcoded in new code
UNAUTHORIZED_TOKENS: Final[tuple[str, ...]] = (
    "Flapi",
    "flapi",
    "PyFLP",
    "pyflp",
    "FLBridge",
    "flbridge",
)

# Approved exception paths where brand names or raw tokens may appear
APPROVED_EXCEPTIONS: Final[tuple[str, ...]] = (
    "tools/tokens.py",
    "tools/rename.py",
    "tests/unit/tools/test_rename.py",
    ".agents/",
)


def validate_tokens(tokens: BrandTokens | Mapping[str, Any] | None = None) -> None:
    """Validate token dictionary or BrandTokens instance against constraints.

    Constraints:
    1. PORT_ROOT length <= 20 chars (assert/error to prevent WinMM 31-char truncation).
    2. DIST must be non-empty and a valid lowercase Python identifier.
    3. CLI must be non-empty and a valid lowercase command name.
    4. DEVICE must be non-empty and a valid identifier.
    5. MCPNAME must be non-empty.
    6. Wire magic bytes 0x53 0x42 ('SB') are immutable protocol constants
       and must never be mapped or overwritten.

    Raises:
        ValueError: If any constraint is violated.
    """
    if tokens is None:
        port_root = DEFAULT_PORT_ROOT
        dist = DEFAULT_DIST
        cli = DEFAULT_CLI
        device = DEFAULT_DEVICE
        mcpname = DEFAULT_MCPNAME
    elif isinstance(tokens, BrandTokens):
        port_root = tokens.port_root
        dist = tokens.dist
        cli = tokens.cli
        device = tokens.device
        mcpname = tokens.mcpname
    elif isinstance(tokens, Mapping):
        normalized: dict[str, str] = {}
        for k, v in tokens.items():
            clean_k = k.strip("{}").lower()
            normalized[clean_k] = str(v)
        port_root = normalized.get("port_root", DEFAULT_PORT_ROOT)
        dist = normalized.get("dist", DEFAULT_DIST)
        cli = normalized.get("cli", DEFAULT_CLI)
        device = normalized.get("device", DEFAULT_DEVICE)
        mcpname = normalized.get("mcpname", DEFAULT_MCPNAME)
    else:
        raise TypeError(f"Expected BrandTokens or Mapping, got {type(tokens).__name__}")

    # 1. Invariant check: wire magic bytes must never be mapped as a brand token
    for name, val in [
        ("DIST", dist),
        ("CLI", cli),
        ("PORT_ROOT", port_root),
        ("DEVICE", device),
        ("MCPNAME", mcpname),
    ]:
        if val in (WIRE_MAGIC_HEX, "0x53", "0x42", "5342", "SB", 'b"SB"', "b'SB'"):
            raise ValueError(
                f"Token {name} has value '{val}' conflicting with protocol wire magic constant. "
                "Wire magic bytes 0x53 0x42 ('SB') are immutable protocol constants."
            )

    # 2. Port root length constraint (<= 20 chars to prevent WinMM 31-char truncation)
    if not port_root:
        raise ValueError("PORT_ROOT must not be empty")
    if len(port_root) > MAX_PORT_ROOT_LENGTH:
        raise ValueError(
            f"PORT_ROOT '{port_root}' exceeds maximum length of {MAX_PORT_ROOT_LENGTH} "
            f"characters (length is {len(port_root)}). WinMM truncates near 31 characters."
        )

    # 3. DIST constraint: valid lowercase Python package identifier
    if not dist:
        raise ValueError("DIST must not be empty")
    if not re.match(r"^[a-z][a-z0-9_]*$", dist):
        raise ValueError(
            f"DIST '{dist}' must be a valid lowercase Python identifier "
            "(alphanumeric and underscores, starting with letter)"
        )

    # 4. CLI constraint: valid lowercase command name
    if not cli:
        raise ValueError("CLI must not be empty")
    if not re.match(r"^[a-z][a-z0-9_-]*$", cli):
        raise ValueError(f"CLI '{cli}' must be a valid lowercase command name")

    # 5. DEVICE constraint: non-empty valid identifier
    if not device:
        raise ValueError("DEVICE must not be empty")
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", device):
        raise ValueError(f"DEVICE '{device}' must be a valid identifier")

    # 6. MCPNAME constraint: non-empty publication name
    if not mcpname:
        raise ValueError("MCPNAME must not be empty")


def check_protocol_constant_protection(
    targets: Mapping[str, Any] | Sequence[str] | BrandTokens,
) -> None:
    """Verify that wire magic constants are never targeted for replacement.

    Raises:
        ValueError: If wire magic bytes are detected as targets.
    """
    keys_to_check: list[str] = []
    if isinstance(targets, BrandTokens):
        keys_to_check = [
            targets.dist,
            targets.cli,
            targets.port_root,
            targets.device,
            targets.mcpname,
        ]
    elif isinstance(targets, Mapping):
        keys_to_check = [str(k) for k in targets] + [str(v) for v in targets.values()]
    elif isinstance(targets, (list, tuple)):
        keys_to_check = [str(t) for t in targets]

    forbidden_magic = {
        "53 42",
        "0x53",
        "0x42",
        "5342",
        "SB",
        'b"SB"',
        "b'SB'",
        "WIRE_MAGIC",
    }

    for item in keys_to_check:
        clean = item.strip("{} '\"")
        if (
            clean in forbidden_magic
            or item in forbidden_magic
            or 'b"SB"' in item
            or "b'SB'" in item
            or "53 42" in item
            or clean == "SB"
        ):
            raise ValueError(
                f"Target '{item}' matches wire protocol constant. "
                "Wire magic bytes 0x53 0x42 ('SB') are protocol constants and never modified."
            )
