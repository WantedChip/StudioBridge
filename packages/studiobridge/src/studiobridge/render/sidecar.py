"""Structured render metadata sidecar generator and reader [06_l0d §12].

Emits and parses `{filename}.render.json` sidecar metadata files alongside rendered
audio files (and compatibility alias `{filename}.meta.json`), recording provenance
(job_id, source project hash, FL Studio build), format parameters, signal quality
metrics (peak, RMS, clipping count, silence ratio), validation status, and ISO timestamps.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studiobridge.render.validate import AudioMetrics


@dataclass
class SidecarMetadata:
    """Structured render artifact metadata stored alongside exported audio."""

    job_id: str
    source: str
    source_hash: str
    fl_version: str
    fl_build: str
    fl_architecture: str
    is_emulated: bool
    formats: list[str]
    output_files: list[str]
    duration_s: float
    validation_status: str  # "passed", "failed", "unvalidated"
    created_at: float
    completed_at: float
    source_size_bytes: int = 0
    peak_linear: float = 0.0
    peak_dbfs: float = -120.0
    rms_linear: float = 0.0
    rms_dbfs: float = -120.0
    clipping_count: int = 0
    silence_ratio: float = 0.0
    format_parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    settings_warning: str = (
        "Export settings were inherited from the last FL Studio interactive session."
    )
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary suitable for JSON serialization."""
        return asdict(self)


def resolve_sidecar_paths(target_path: Path | str) -> tuple[Path, Path]:
    """Resolve primary (.render.json) and compatibility alias (.meta.json) paths.

    If given an audio file (e.g. `out/MyProject.wav`), returns:
        (`out/MyProject.render.json`, `out/MyProject.meta.json`).
    If given `out/MyProject.render.json`, returns:
        (`out/MyProject.render.json`, `out/MyProject.meta.json`).
    If given `out/MyProject.meta.json`, returns:
        (`out/MyProject.render.json`, `out/MyProject.meta.json`).
    """
    path = Path(target_path)
    name = path.name

    if name.endswith(".render.json"):
        stem = name[:-12]
        primary = path
        alias = path.with_name(f"{stem}.meta.json")
    elif name.endswith(".meta.json"):
        stem = name[:-10]
        primary = path.with_name(f"{stem}.render.json")
        alias = path
    elif name.endswith(".json"):
        primary = path
        alias = path.with_suffix(".meta.json")
    else:
        # Audio file path (e.g. track.wav)
        stem = path.stem
        primary = path.parent / f"{stem}.render.json"
        alias = path.parent / f"{stem}.meta.json"

    return primary, alias


def build_sidecar_dict(
    job_id: str,
    source: str,
    source_hash: str,
    fl_build: str,
    duration_s: float,
    formats: list[str],
    output_files: list[str],
    validation_status: str = "passed",
    fl_version: str = "",
    fl_architecture: str = "x64",
    is_emulated: bool = False,
    source_size_bytes: int = 0,
    metrics: AudioMetrics | None = None,
    created_at: float | None = None,
    completed_at: float | None = None,
    format_parameters: dict[str, Any] | None = None,
    settings_warning: str = (
        "Export settings were inherited from the last FL Studio interactive session."
    ),
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sidecar metadata dictionary with standard fields and acoustic metrics."""
    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = datetime.now(timezone.utc).timestamp()

    peak_linear = metrics.peak_linear if metrics else 0.0
    peak_dbfs = metrics.peak_dbfs if metrics else -120.0
    rms_linear = metrics.rms_linear if metrics else 0.0
    rms_dbfs = metrics.rms_dbfs if metrics else -120.0
    clipping_count = metrics.clipping_count if metrics else 0
    silence_ratio = metrics.silence_ratio if metrics else 0.0
    metrics_dict = metrics.to_dict() if metrics else {}

    data: dict[str, Any] = {
        "job_id": job_id,
        "source": str(source),
        "source_hash": source_hash,
        "source_size_bytes": source_size_bytes,
        "fl_version": fl_version,
        "fl_build": fl_build,
        "fl_architecture": fl_architecture,
        "is_emulated": is_emulated,
        "formats": formats,
        "format_parameters": format_parameters or {"formats": formats},
        "output_files": output_files,
        "duration_s": round(duration_s, 4),
        "peak_linear": round(peak_linear, 6),
        "peak_dbfs": round(peak_dbfs, 2),
        "rms_linear": round(rms_linear, 6),
        "rms_dbfs": round(rms_dbfs, 2),
        "clipping_count": clipping_count,
        "silence_ratio": round(silence_ratio, 4),
        "validation_status": validation_status,
        "timestamp": now_iso,
        "created_at": created_at or now_ts,
        "completed_at": completed_at or now_ts,
        "settings_warning": settings_warning,
        "metrics": metrics_dict,
    }

    if extra:
        data.update(extra)

    return data


def write_sidecar(
    audio_path: Path | str,
    sidecar_data: dict[str, Any] | SidecarMetadata,
    create_alias: bool = True,
) -> Path:
    """Emit {filename}.render.json sidecar metadata alongside audio files.

    Args:
        audio_path: Audio file path or sidecar file path.
        sidecar_data: Metadata dictionary or SidecarMetadata dataclass.
        create_alias: If True, also write compatibility alias {filename}.meta.json.

    Returns:
        Path to the primary generated .render.json file.
    """
    primary_path, alias_path = resolve_sidecar_paths(audio_path)
    primary_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(sidecar_data, SidecarMetadata):
        data = sidecar_data.to_dict()
    else:
        data = dict(sidecar_data)

    if "timestamp" not in data:
        data["timestamp"] = datetime.now(timezone.utc).isoformat()

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    primary_path.write_text(json_str, encoding="utf-8")

    if create_alias and alias_path != primary_path:
        alias_path.write_text(json_str, encoding="utf-8")

    return primary_path


def read_sidecar(sidecar_path: Path | str) -> dict[str, Any]:
    """Read and parse sidecar metadata JSON file.

    Args:
        sidecar_path: Path to .render.json, .meta.json, or base audio file.

    Returns:
        Parsed sidecar metadata dictionary.

    Raises:
        FileNotFoundError: If no sidecar metadata file is found.
        json.JSONDecodeError: If sidecar contains malformed JSON.
    """
    path = Path(sidecar_path)
    name = path.name

    if name.endswith(".json") and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    primary, alias = resolve_sidecar_paths(path)
    if primary.is_file():
        return json.loads(primary.read_text(encoding="utf-8"))
    if alias.is_file():
        return json.loads(alias.read_text(encoding="utf-8"))

    # Also check if exact name + .render.json exists (e.g. track.wav.render.json)
    ext_sidecar = path.parent / f"{path.name}.render.json"
    if ext_sidecar.is_file():
        return json.loads(ext_sidecar.read_text(encoding="utf-8"))

    raise FileNotFoundError(f"Sidecar metadata file not found for: '{sidecar_path}'")
