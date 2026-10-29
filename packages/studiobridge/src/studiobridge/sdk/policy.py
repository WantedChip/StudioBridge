"""Safety policy parser and boundary rule validator.

Implements local policy enforcement [SAF-04]:
- Local policy parsing from .sbridge-policy.toml / .sbridge_policy.toml.
- Deny list (deny_ops) checking.
- Parameter bounds: max_volume_db, max_volume, max_volume_delta_db, max_tempo, min_tempo.
- Raises PolicyDeniedError (subclass of SafetyError) with code E_POLICY on violation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

from studiobridge.core.errors import PolicyDeniedError
from studiobridge.core.paths import get_app_data_dir
from studiobridge.sdk.units import Db, Percent, Volume

POLICY_FILE_NAMES: list[str] = [
    ".sbridge-policy.toml",
    ".sbridge_policy.toml",
    "sbridge-policy.toml",
]


@dataclass
class Policy:
    """Active safety policy configuration."""

    deny_ops: set[str] = field(default_factory=set)
    max_volume_db: float | None = None
    max_volume: float | None = None
    max_volume_delta_db: float | None = None
    max_tempo: float | None = None
    min_tempo: float | None = None
    protect_tempo: bool = False
    allow_protected: bool = False
    source_path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_path: Path | None = None) -> Policy:
        """Construct Policy from dictionary (e.g. parsed TOML)."""
        # Look for [policy] section or top-level keys
        section = data.get("policy", data)
        if not isinstance(section, dict):
            section = data

        bounds = section.get("bounds", section.get("limits", {}))
        if not isinstance(bounds, dict):
            bounds = {}

        # 1. Deny list
        deny_list = (
            section.get("deny_ops")
            or section.get("denied_operations")
            or section.get("blacklist")
            or []
        )
        deny_ops = {str(item).strip() for item in deny_list if str(item).strip()}

        # 2. Volume bounds
        max_vol_db = section.get("max_volume_db", bounds.get("max_volume_db"))
        max_vol_raw = section.get("max_volume", bounds.get("max_volume"))
        max_vol_delta_db = section.get("max_volume_delta_db", bounds.get("max_volume_delta_db"))

        max_tempo = section.get("max_tempo", bounds.get("max_tempo"))
        min_tempo = section.get("min_tempo", bounds.get("min_tempo"))
        protect_tempo = bool(section.get("protect_tempo", bounds.get("protect_tempo", False)))
        allow_protected = bool(section.get("allow_protected", False))

        return cls(
            deny_ops=deny_ops,
            max_volume_db=float(max_vol_db) if max_vol_db is not None else None,
            max_volume=float(max_vol_raw) if max_vol_raw is not None else None,
            max_volume_delta_db=(float(max_vol_delta_db) if max_vol_delta_db is not None else None),
            max_tempo=float(max_tempo) if max_tempo is not None else None,
            min_tempo=float(min_tempo) if min_tempo is not None else None,
            protect_tempo=protect_tempo,
            allow_protected=allow_protected,
            source_path=source_path,
        )

    @classmethod
    def from_toml(cls, text: str, source_path: Path | None = None) -> Policy:
        """Parse Policy from TOML string."""
        data = tomllib.loads(text)
        return cls.from_dict(data, source_path=source_path)

    @classmethod
    def load(cls, path: Path | str | None = None) -> Policy:
        """Load policy from specified file, search workspace root, or user default.

        Resolution order:
        1. Explicit path if supplied.
        2. .sbridge-policy.toml or .sbridge_policy.toml in current directory or parents.
        3. %LOCALAPPDATA%\\studiobridge\\policy.toml.
        4. Default empty/permissive policy.
        """
        if path is not None:
            p = Path(path)
            if p.exists() and p.is_file():
                return cls.from_toml(p.read_text(encoding="utf-8"), source_path=p)
            raise FileNotFoundError(f"Policy file not found: {path}")

        # Search current working directory and parent paths
        try:
            cwd = Path.cwd().resolve()
            for directory in [cwd, *cwd.parents]:
                for candidate_name in POLICY_FILE_NAMES:
                    candidate = directory / candidate_name
                    if candidate.exists() and candidate.is_file():
                        return cls.from_toml(
                            candidate.read_text(encoding="utf-8"), source_path=candidate
                        )
        except Exception:
            pass

        # Check user application data directory
        user_policy = get_app_data_dir() / "policy.toml"
        if user_policy.exists() and user_policy.is_file():
            try:
                return cls.from_toml(
                    user_policy.read_text(encoding="utf-8"), source_path=user_policy
                )
            except Exception:
                pass

        return cls()

    def check(
        self,
        op: str,
        args: dict[str, Any] | None = None,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate an operation and arguments against this policy.

        Raises:
            PolicyDeniedError: If operation is on deny list or parameter exceeds limits.
        """
        call_args = args or {}
        ctx = context or {}

        # 1. Deny list check
        if op in self.deny_ops:
            raise PolicyDeniedError(
                f"Operation '{op}' is denied by active safety policy ([SAF-04]).",
                code="E_POLICY",
                details={"operation": op, "deny_ops": sorted(self.deny_ops)},
                remedy="Update .sbridge-policy.toml or remove operation from deny list.",
            )

        # 2. Volume checks
        if any(
            op.startswith(prefix)
            for prefix in (
                "mixer.setTrackVolume",
                "mixer.set_volume",
                "channels.setChannelVolume",
                "channels.set_volume",
            )
        ):
            vol_val = call_args.get("volume") if "volume" in call_args else call_args.get("val")
            if vol_val is not None:
                # Convert unit types to raw float
                raw_vol: float | None = None
                if isinstance(vol_val, (Volume, Db, Percent)):
                    raw_vol = float(Volume(vol_val))
                elif isinstance(vol_val, (int, float)):
                    raw_vol = float(vol_val)

                if raw_vol is not None:
                    # Check max_volume (normalized raw)
                    if self.max_volume is not None and raw_vol > self.max_volume:
                        raise PolicyDeniedError(
                            f"Volume {raw_vol:.3f} exceeds policy limit "
                            f"max_volume={self.max_volume:.3f}.",
                            code="E_POLICY",
                            details={"volume": raw_vol, "max_volume": self.max_volume},
                            remedy=f"Constrain volume to <= {self.max_volume}.",
                        )

                    # Check max_volume_db
                    vol_db = Volume(raw_vol).to_db().value
                    if self.max_volume_db is not None and vol_db > (self.max_volume_db + 0.05):
                        raise PolicyDeniedError(
                            f"Volume {vol_db:.1f} dB exceeds policy limit "
                            f"max_volume_db={self.max_volume_db:.1f} dB.",
                            code="E_POLICY",
                            details={
                                "volume_db": vol_db,
                                "max_volume_db": self.max_volume_db,
                            },
                            remedy=f"Constrain volume to <= {self.max_volume_db} dB.",
                        )

                    # Check max_volume_delta_db
                    if self.max_volume_delta_db is not None and any(
                        k in ctx for k in ("before", "current_volume", "before_volume")
                    ):
                        before_val = (
                            ctx.get("before")
                            if "before" in ctx
                            else ctx.get("current_volume", ctx.get("before_volume"))
                        )
                        before_raw: float | None = None
                        if isinstance(before_val, (Volume, Db, Percent)):
                            before_raw = float(Volume(before_val))
                        elif isinstance(before_val, (int, float)):
                            before_raw = float(before_val)

                        if before_raw is not None:
                            before_db = Volume(before_raw).to_db().value
                            delta_db = abs(vol_db - before_db)
                            if delta_db > (self.max_volume_delta_db + 0.05):
                                raise PolicyDeniedError(
                                    f"Volume change {delta_db:.1f} dB exceeds policy max delta="
                                    f"{self.max_volume_delta_db:.1f} dB.",
                                    code="E_POLICY",
                                    details={
                                        "delta_db": delta_db,
                                        "max_volume_delta_db": self.max_volume_delta_db,
                                    },
                                    remedy=(
                                        f"Apply volume change in smaller steps <= "
                                        f"{self.max_volume_delta_db} dB."
                                    ),
                                )

        # 3. Tempo checks
        if any(op.startswith(prefix) for prefix in ("transport.setTempo", "transport.set_tempo")):
            tempo_val = (
                call_args.get("bpm")
                if "bpm" in call_args
                else call_args.get("tempo", call_args.get("val"))
            )
            if tempo_val is not None:
                try:
                    t = float(tempo_val)
                    if self.max_tempo is not None and t > self.max_tempo:
                        raise PolicyDeniedError(
                            f"Tempo {t:.1f} BPM exceeds policy max_tempo={self.max_tempo:.1f} BPM.",
                            code="E_POLICY",
                            details={"tempo": t, "max_tempo": self.max_tempo},
                            remedy=f"Constrain tempo to <= {self.max_tempo} BPM.",
                        )
                    if self.min_tempo is not None and t < self.min_tempo:
                        raise PolicyDeniedError(
                            f"Tempo {t:.1f} BPM is below policy min_tempo="
                            f"{self.min_tempo:.1f} BPM.",
                            code="E_POLICY",
                            details={"tempo": t, "min_tempo": self.min_tempo},
                            remedy=f"Constrain tempo to >= {self.min_tempo} BPM.",
                        )
                except (ValueError, TypeError):
                    pass


__all__ = [
    "POLICY_FILE_NAMES",
    "Policy",
]
