"""Piano-roll script generator and note serializer.

Implements piano-roll script generation [PR-01]..[PR-06].
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Final

from studiobridge.core.errors import ArgumentError, PayloadTooLargeError
from studiobridge.pianoroll.templates.apply_template import (
    DEFAULT_DEVICE_NAME,
    render_apply_script,
)
from studiobridge.pianoroll.types import (
    DEFAULT_PPQ,
    MAX_PAYLOAD_BYTES,
    VALID_APPLY_MODES,
    ApplyMode,
    Note,
    PyscriptJob,
)

DEFAULT_BRAND: Final[str] = DEFAULT_DEVICE_NAME


class PyscriptGenerator:
    """FL Studio piano-roll script (.pyscript) generator.

    Produces complete, self-contained Python scripts for FL Studio's
    flpianoroll engine, serializing complete 11-parameter note tuples,
    handling project PPQ and unit conversions, embedding idempotency markers,
    and automatically chunking large payloads (> 200 KB) into sequential jobs.
    """

    def __init__(
        self,
        default_ppq: int = DEFAULT_PPQ,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
        brand_name: str = DEFAULT_BRAND,
    ) -> None:
        if default_ppq <= 0:
            raise ValueError(f"default_ppq must be positive, got {default_ppq}")
        if max_payload_bytes <= 1024:
            raise ValueError(f"max_payload_bytes must be > 1024, got {max_payload_bytes}")

        self.default_ppq = default_ppq
        self.max_payload_bytes = max_payload_bytes
        self.brand_name = brand_name

    def generate_job_id(self, prefix: str = "sbj") -> str:
        """Generate unique job identifier with UTC date and random hex entropy.

        Format: sbj-YYYYMMDD-XXXX (e.g. 'sbj-20261025-a1b2').
        """
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        token = secrets.token_hex(2)
        return f"{prefix}-{date_str}-{token}"

    def serialize_note(
        self,
        note: Note | Sequence[Any] | Mapping[str, Any],
        ppq: int | None = None,
    ) -> tuple[int, int, int, float, float, float, int, int, float, float, bool]:
        """Convert any note representation into the canonical 11-parameter tuple."""
        effective_ppq = ppq if ppq is not None else self.default_ppq

        if isinstance(note, Note):
            return note.to_tuple()
        if isinstance(note, Mapping):
            return Note.from_dict(note, ppq=effective_ppq).to_tuple()
        if isinstance(note, Sequence):
            if len(note) == 11 and all(isinstance(x, (int, float, bool)) for x in note):
                # Already an 11-tuple; validate and format
                return Note.from_tuple(note).to_tuple()
            return Note.from_tuple(note).to_tuple()

        raise ArgumentError(f"Unsupported note type: {type(note)!r}")

    def serialize_notes(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        ppq: int | None = None,
    ) -> list[tuple[int, int, int, float, float, float, int, int, float, float, bool]]:
        """Serialize a sequence of notes into 11-parameter tuples."""
        return [self.serialize_note(n, ppq=ppq) for n in notes]

    def _to_note_objects(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        ppq: int,
    ) -> list[Note]:
        """Convert heterogeneous note inputs into a list of Note dataclass instances."""
        result: list[Note] = []
        for n in notes:
            if isinstance(n, Note):
                result.append(n)
            elif isinstance(n, Mapping):
                result.append(Note.from_dict(n, ppq=ppq))
            elif isinstance(n, Sequence):
                result.append(Note.from_tuple(n))
            else:
                raise ArgumentError(f"Cannot convert {type(n)!r} to Note")
        return result

    def split_payload(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        max_payload_bytes: int | None = None,
        mode: str = "append",
        time_range: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
    ) -> list[list[Note]]:
        """Split a list of notes into sequential chunks that strictly respect max_payload_bytes."""
        effective_ppq = ppq if ppq is not None else self.default_ppq
        max_bytes = max_payload_bytes if max_payload_bytes is not None else self.max_payload_bytes
        note_objs = self._to_note_objects(notes, ppq=effective_ppq)
        base_job = job_id or self.generate_job_id()

        if not note_objs:
            return [[]]

        # Check template overhead
        overhead_script = render_apply_script(
            job_id=f"{base_job}-99",
            notes=[],
            mode=mode,
            time_range=time_range,
            device_name=self.brand_name,
        )
        overhead = len(overhead_script.encode("utf-8"))
        if max_bytes <= overhead + 100:
            raise ValueError(
                f"max_payload_bytes ({max_bytes}) must be greater than "
                f"script overhead ({overhead} bytes)"
            )

        chunks: list[list[Note]] = []
        start_idx = 0
        total_notes = len(note_objs)

        while start_idx < total_notes:
            is_first_chunk = len(chunks) == 0
            chunk_mode = mode if is_first_chunk else "append"
            chunk_range = time_range if is_first_chunk else None
            chunk_job_id = f"{base_job}-{len(chunks) + 1:02d}"

            # Binary search the maximum number of notes that fit in this chunk
            low = 1
            high = total_notes - start_idx
            best_k = 0

            # First verify single note fits
            single_script = render_apply_script(
                job_id=chunk_job_id,
                notes=note_objs[start_idx : start_idx + 1],
                mode=chunk_mode,
                time_range=chunk_range,
                device_name=self.brand_name,
            )
            if len(single_script.encode("utf-8")) > max_bytes:
                raise PayloadTooLargeError(
                    f"A single note exceeds max_payload_bytes ({max_bytes} bytes).",
                    details={"max_payload_bytes": max_bytes, "note_index": start_idx},
                )

            while low <= high:
                mid = (low + high) // 2
                candidate = note_objs[start_idx : start_idx + mid]
                script = render_apply_script(
                    job_id=chunk_job_id,
                    notes=candidate,
                    mode=chunk_mode,
                    time_range=chunk_range,
                    device_name=self.brand_name,
                )
                size = len(script.encode("utf-8"))
                if size <= max_bytes:
                    best_k = mid
                    low = mid + 1
                else:
                    high = mid - 1

            if best_k == 0:
                raise PayloadTooLargeError(
                    f"Failed to fit note at index {start_idx} into chunk of size {max_bytes} bytes."
                )

            chunks.append(note_objs[start_idx : start_idx + best_k])
            start_idx += best_k

        return chunks

    def generate_jobs(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        mode: ApplyMode | str = "append",
        time_range: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
        max_payload_bytes: int | None = None,
    ) -> list[PyscriptJob]:
        """Generate ordered sequential .pyscript jobs respecting max_payload_bytes ([PR-02]).

        If total payload <= max_payload_bytes, returns a single job.
        If total payload > max_payload_bytes, automatically splits notes into
        sequential jobs where part 1 performs the requested mode ('replace_all',
        'replace_range', or 'append') and subsequent parts perform 'append'.
        """
        if mode not in VALID_APPLY_MODES:
            valid_list = sorted(VALID_APPLY_MODES)
            raise ArgumentError(f"Invalid mode {mode!r}; must be one of {valid_list}")
        if mode == "replace_range" and (time_range is None or len(time_range) != 2):
            raise ArgumentError("Mode 'replace_range' requires time_range=(start_ticks, end_ticks)")

        effective_ppq = ppq if ppq is not None else self.default_ppq
        max_bytes = max_payload_bytes if max_payload_bytes is not None else self.max_payload_bytes
        base_job_id = job_id or self.generate_job_id()

        chunks = self.split_payload(
            notes=notes,
            max_payload_bytes=max_bytes,
            mode=mode,
            time_range=time_range,
            job_id=base_job_id,
            ppq=effective_ppq,
        )

        total_parts = len(chunks)
        jobs: list[PyscriptJob] = []

        for idx, chunk in enumerate(chunks, start=1):
            is_first = idx == 1
            part_mode = mode if is_first else "append"
            part_range = time_range if is_first else None
            part_job_id = base_job_id if total_parts == 1 else f"{base_job_id}-{idx:02d}"

            script_text = render_apply_script(
                job_id=part_job_id,
                notes=chunk,
                mode=part_mode,
                time_range=part_range,
                device_name=self.brand_name,
            )

            job = PyscriptJob(
                job_id=part_job_id,
                script_content=script_text,
                mode=part_mode,
                notes=tuple(chunk),
                part_index=idx,
                total_parts=total_parts,
                time_range=part_range,
            )
            jobs.append(job)

        return jobs

    def generate(
        self,
        notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
        mode: ApplyMode | str = "append",
        time_range: tuple[int, int] | None = None,
        job_id: str | None = None,
        ppq: int | None = None,
        max_payload_bytes: int | None = None,
    ) -> str:
        """Generate a single self-contained FL Studio piano-roll script (.pyscript).

        Args:
            notes: Sequence of notes to bake into the script.
            mode: Edit mode ('append', 'replace_all', or 'replace_range').
            time_range: (start, end) ticks tuple when mode='replace_range'.
            job_id: Idempotency job identifier (auto-generated if omitted).
            ppq: Project pulses per quarter note (default 96).
            max_payload_bytes: Maximum allowed script byte size (default 200 KB).

        Returns:
            The complete .pyscript source code as a string.

        Raises:
            PayloadTooLargeError: If payload exceeds max_payload_bytes.
        """
        jobs = self.generate_jobs(
            notes=notes,
            mode=mode,
            time_range=time_range,
            job_id=job_id,
            ppq=ppq,
            max_payload_bytes=max_payload_bytes,
        )

        if len(jobs) == 1:
            return jobs[0].script_content

        total_bytes = sum(j.byte_size for j in jobs)
        raise PayloadTooLargeError(
            f"Payload of {len(notes)} notes ({total_bytes} bytes) exceeds limit of "
            f"{max_payload_bytes or self.max_payload_bytes} bytes per script. "
            f"Use generate_jobs() to handle {len(jobs)} sequential jobs.",
            details={
                "total_notes": len(notes),
                "total_bytes": total_bytes,
                "parts_required": len(jobs),
            },
        )


def generate_pyscript(
    notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
    mode: ApplyMode | str = "append",
    time_range: tuple[int, int] | None = None,
    job_id: str | None = None,
    ppq: int = DEFAULT_PPQ,
    brand_name: str = DEFAULT_BRAND,
) -> str:
    """Convenience helper to generate a single self-contained .pyscript file."""
    gen = PyscriptGenerator(default_ppq=ppq, brand_name=brand_name)
    return gen.generate(notes=notes, mode=mode, time_range=time_range, job_id=job_id)


def generate_pyscript_jobs(
    notes: Sequence[Note | Sequence[Any] | Mapping[str, Any]],
    mode: ApplyMode | str = "append",
    time_range: tuple[int, int] | None = None,
    job_id: str | None = None,
    ppq: int = DEFAULT_PPQ,
    max_payload_bytes: int = MAX_PAYLOAD_BYTES,
    brand_name: str = DEFAULT_BRAND,
) -> list[PyscriptJob]:
    """Convenience helper to generate one or more sequential .pyscript jobs."""
    gen = PyscriptGenerator(
        default_ppq=ppq,
        max_payload_bytes=max_payload_bytes,
        brand_name=brand_name,
    )
    return gen.generate_jobs(notes=notes, mode=mode, time_range=time_range, job_id=job_id)
