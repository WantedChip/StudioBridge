"""Atomic FLP project writer with fsync, temporary files, and backup safety.

Implements safe offline file writing per 07_l0e_flp_engine.md §3.4,
12_crosscutting.md §1, §7, [FLP-31], and [FLP-32].
"""

from __future__ import annotations

import os
import secrets
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from studiobridge.core.errors import (
    FlpInvariantViolationError,
    FlpVersionUnsupportedError,
    FlpWriteRiskError,
)
from studiobridge.flp.codec.reader import FlpFile
from studiobridge.flp.mutate.serializer import serialize_project
from studiobridge.flp.schema.resolver import resolve_profile
from studiobridge.flp.validate.invariants import check_invariants

if TYPE_CHECKING:
    from studiobridge.flp.model.project import Project


def atomic_save(
    project: Project,
    dest_path: Path | str,
    *,
    in_place: bool = False,
    force_unknown_version: bool = False,
    make_backup: bool = True,
) -> Path:
    """Save FLP Project to destination path atomically with verification [FLP-31, FLP-32].

    Safety workflow:
    1. Version gate check ([FLP-32]): Rejects unknown/newer FL versions without force.
    2. In-place overwrite protection: Refuses in-place overwrite unless in_place=True
       and creates a verified timestamped backup (<filename>.bak-YYYYmmddHHMMSS).
    3. Pre-save invariant check: Halts and raises E_FLP_INVARIANT if project violates invariants.
    4. Write to temporary file (<filename>.<pid>.<hex>.tmp) in destination folder.
    5. Flush and os.fsync(), closing file handles before replacement (Windows file lock safe).
    6. Verify temporary file: Re-parses from disk and runs invariant validation.
    7. Atomic replacement (os.replace) into destination file.

    Args:
        project: Project object model instance to serialize.
        dest_path: Destination file path.
        in_place: Allow overwriting existing destination file.
        force_unknown_version: Allow writing to projects from unverified FL versions.
        make_backup: When overwriting in place, create timestamped backup.

    Returns:
        Path object pointing to the written destination file.

    Raises:
        FlpVersionUnsupportedError: If version is unknown and force_unknown_version is False.
        FlpWriteRiskError: If in-place overwrite attempted without in_place=True.
        FlpInvariantViolationError: If structural invariant checks fail before or after write.
    """
    dest = Path(dest_path).resolve()

    # 1. Version gate validation ([FLP-32])
    res = resolve_profile(project.version)
    if not force_unknown_version and (
        res.risk == "unknown_version" or res.read_only or not res.is_exact_match
    ):
        msg = (
            f"FLP version '{project.version}' is unknown or unsupported "
            f"(risk='{res.risk or 'unknown_version'}'). Writes are blocked "
            f"per [FLP-32] to prevent project corruption. Use force_unknown_version=True."
        )
        raise FlpVersionUnsupportedError(
            message=msg,
            code="E_FLP_VERSION",
            details={
                "version": project.version,
                "risk": res.risk or "unknown_version",
                "profile_id": res.profile.id,
            },
        )

    # 2. In-place overwrite protection
    dest_exists = dest.is_file()
    if dest_exists:
        if not in_place:
            raise FlpWriteRiskError(
                message=(
                    f"Refusing in-place overwrite of existing file '{dest}' without in_place=True. "
                    f"Pass in_place=True or specify a new destination filename [FLP-31]."
                ),
                code="E_FLP_WRITE_RISK",
                details={"dest_path": str(dest)},
            )
        if make_backup:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            backup_path = dest.with_name(f"{dest.name}.bak-{timestamp}")
            shutil.copy2(dest, backup_path)
            if not backup_path.is_file() or backup_path.stat().st_size != dest.stat().st_size:
                raise FlpWriteRiskError(
                    message=(
                        f"Failed to create verified backup '{backup_path}' before in-place write"
                    ),
                    code="E_FLP_WRITE_RISK",
                    details={"dest": str(dest), "backup": str(backup_path)},
                )

    # 3. Pre-save invariant check
    check_invariants(project)

    # 4. Write output to temporary file in target directory
    dest_dir = dest.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_name = f"{dest.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    temp_path = dest_dir / temp_name

    mutator = getattr(project, "_mutator", None)
    flp_file = serialize_project(project, mutator=mutator)

    try:
        with open(temp_path, "wb") as f:
            flp_file.serialize(destination=f)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    # 5. Verification on temporary file before replacement
    try:
        reparsed_flp = FlpFile.from_file(temp_path)
        from studiobridge.flp.model.project import Project as ProjectModel

        reparsed_project = ProjectModel._hydrate(reparsed_flp)
        check_invariants(reparsed_project)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise FlpInvariantViolationError(
            message=f"Post-write re-parse verification failed on temporary file: {exc}",
            details={"temp_path": str(temp_path), "dest": str(dest)},
        ) from exc

    # 6. Atomic replacement
    try:
        os.replace(temp_path, dest)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    # 7. Update project internal source tracking
    project.file_path = dest
    project.source_file = reparsed_flp

    return dest
