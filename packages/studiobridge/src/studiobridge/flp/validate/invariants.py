"""FLP structural invariant validator and consistency checker.

Implements post-mutation and pre-save structural invariant checks per
07_l0e_flp_engine.md §3.4, 12_crosscutting.md §7, [FLP-05], and [FLP-30].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from studiobridge.core.errors import FlpInvariantViolationError
from studiobridge.flp.codec.reader import EventChunk, HeaderChunk

if TYPE_CHECKING:
    from studiobridge.flp.model.project import Project


def validate_invariants(project: Project) -> list[str]:
    """Inspect project object model and return list of structural invariant violations.

    Checks:
    - Unique and contiguous channel indices (0..N-1)
    - Header channel count matches channel rack count ([FLP-05])
    - Channel targets resolve to valid mixer tracks (0..125)
    - Pattern numbers are positive and unique
    - Pattern note references resolve to valid channel rack indices
    - Note parameters (key 0..127, pos >= 0, len >= 0, vel, pan) are valid
    - Mixer track indices 0..125, track 0 is Master, slot indices 0..9
    - Mixer track routing destinations resolve to valid mixer tracks
    - Playlist items resolve to valid pattern numbers or clip channels
    - Tempo and PPQ bounds
    - Profile-specific record sizes and event order constraints

    Returns:
        List of human-readable violation descriptions. Empty if all invariants hold.
    """
    violations: list[str] = []

    # 1. Header channel count vs actual channel count ([FLP-05])
    if project.source_file is not None and project.source_file.header is not None:
        header_ch = project.source_file.header.channels
        actual_ch = len(project.channels)
        if header_ch != actual_ch:
            violations.append(
                f"Header channel count ({header_ch}) does not match actual channel count "
                f"({actual_ch}) [FLP-05]"
            )

    # 2. Channel rack integrity
    channel_indices: list[int] = [ch.index for ch in project.channels]
    if len(channel_indices) != len(set(channel_indices)):
        violations.append(f"Duplicate channel rack indices detected: {channel_indices}")
    expected_indices = list(range(len(project.channels)))
    if channel_indices != expected_indices:
        violations.append(
            f"Channel rack indices are not contiguous 0..N-1: got {channel_indices}, "
            f"expected {expected_indices}"
        )

    mixer_track_count = len(project.mixer) if project.mixer else 126
    for ch in project.channels:
        if not (0 <= ch.target_mixer_track < mixer_track_count):
            violations.append(
                f"Channel [{ch.index}] '{ch.name}' target mixer track {ch.target_mixer_track} "
                f"out of range (0..{mixer_track_count - 1})"
            )
        if not (0.0 <= ch.volume <= 2.0):
            violations.append(
                f"Channel [{ch.index}] '{ch.name}' volume {ch.volume} out of bounds [0.0, 2.0]"
            )
        if not (-1.0 <= ch.pan <= 1.0):
            violations.append(
                f"Channel [{ch.index}] '{ch.name}' pan {ch.pan} out of bounds [-1.0, 1.0]"
            )

    # 3. Pattern numbers and references
    pattern_numbers = [p.number for p in project.patterns]
    if len(pattern_numbers) != len(set(pattern_numbers)):
        violations.append(f"Duplicate pattern numbers detected: {pattern_numbers}")
    pattern_num_set = set(pattern_numbers)

    for p in project.patterns:
        if p.number < 1:
            violations.append(f"Pattern number {p.number} must be >= 1")
        if p.length < 0:
            violations.append(
                f"Pattern [{p.number}] '{p.name}' length {p.length} cannot be negative"
            )

        for ch_idx, notes in p.notes.items():
            if not (0 <= ch_idx < len(project.channels)):
                violations.append(
                    f"Pattern [{p.number}] '{p.name}' contains notes referencing non-existent "
                    f"channel index {ch_idx} (channels count: {len(project.channels)})"
                )
            for n in notes:
                if not (0 <= n.key <= 127):
                    violations.append(
                        f"Pattern [{p.number}] note key {n.key} out of MIDI range 0..127"
                    )
                if n.pos < 0:
                    violations.append(
                        f"Pattern [{p.number}] note position {n.pos} cannot be negative"
                    )
                if n.len < 0:
                    violations.append(
                        f"Pattern [{p.number}] note duration {n.len} cannot be negative"
                    )
                if not (0.0 <= n.velocity <= 1.0 or 0 <= n.velocity <= 127):
                    violations.append(
                        f"Pattern [{p.number}] note velocity {n.velocity} out of bounds"
                    )
                if not (-1.0 <= n.pan <= 1.0):
                    violations.append(
                        f"Pattern [{p.number}] note pan {n.pan} out of bounds [-1.0, 1.0]"
                    )

    # 4. Mixer tracks and slot bounds
    mixer_indices = [m.index for m in project.mixer]
    if len(mixer_indices) != len(set(mixer_indices)):
        violations.append(f"Duplicate mixer track indices detected: {mixer_indices}")

    for mt in project.mixer:
        if not (0 <= mt.index <= 125):
            violations.append(f"Mixer track index {mt.index} out of range 0..125")
        if not (0.0 <= mt.volume <= 2.0):
            violations.append(
                f"Mixer track [{mt.index}] '{mt.name}' volume {mt.volume} out of bounds [0.0, 2.0]"
            )
        if not (-1.0 <= mt.pan <= 1.0):
            violations.append(
                f"Mixer track [{mt.index}] '{mt.name}' pan {mt.pan} out of bounds [-1.0, 1.0]"
            )
        if not (-1.0 <= mt.stereo_sep <= 1.0):
            violations.append(
                f"Mixer track [{mt.index}] '{mt.name}' stereo separation {mt.stereo_sep} "
                f"out of bounds [-1.0, 1.0]"
            )
        for dest in mt.routing:
            if not (0 <= dest < mixer_track_count):
                violations.append(
                    f"Mixer track [{mt.index}] routes to non-existent track index {dest}"
                )
        if len(mt.slots) > 10:
            violations.append(
                f"Mixer track [{mt.index}] has {len(mt.slots)} effect slots (max 10 allowed)"
            )
        for s in mt.slots:
            if not (0 <= s.index < 10):
                violations.append(
                    f"Mixer track [{mt.index}] slot index {s.index} out of range 0..9"
                )

    # 5. Playlist arrangement integrity
    for idx, item in enumerate(project.arrangement.items):
        if item.track < 1:
            violations.append(f"Playlist item [{idx}] lane track {item.track} must be >= 1")
        if item.start < 0:
            violations.append(
                f"Playlist item [{idx}] start position {item.start} cannot be negative"
            )
        if item.length < 0:
            violations.append(f"Playlist item [{idx}] duration {item.length} cannot be negative")
        if item.pattern_index is not None and item.pattern_index not in pattern_num_set:
            violations.append(
                f"Playlist item [{idx}] references non-existent pattern number {item.pattern_index}"
            )
        if item.clip_ref is not None and not (0 <= item.clip_ref < len(project.channels)):
            violations.append(
                f"Playlist item [{idx}] references non-existent channel index {item.clip_ref} "
                f"(channels count: {len(project.channels)})"
            )

    # 6. Markers
    for m in project.arrangement.markers:
        if m.position_ticks < 0:
            violations.append(
                f"Timeline marker '{m.name}' position {m.position_ticks} cannot be negative"
            )

    # 7. Tempo and PPQ bounds
    if not (10.0 <= project.tempo <= 522.0):
        violations.append(
            f"Project tempo {project.tempo:.2f} BPM out of valid FL Studio range [10.0, 522.0]"
        )
    if project.ppq <= 0:
        violations.append(f"Project PPQ {project.ppq} must be positive")

    # 8. Profile-specific layout constraints (if profile is loaded)
    if project.profile is not None:
        layouts = project.profile.struct_layouts
        # Playlist item raw sizes
        for idx, item in enumerate(project.arrangement.items):
            if item.raw and len(item.raw) != layouts.playlist_item_size:
                violations.append(
                    f"Playlist item [{idx}] raw size {len(item.raw)} does not match profile "
                    f"'{project.profile.id}' layout size {layouts.playlist_item_size} bytes"
                )

    # 9. Chunk ordering and event payload size constraints (if source_file is present)
    if project.source_file is not None:
        header_seen = False
        for chunk in project.source_file.chunks:
            if isinstance(chunk, HeaderChunk):
                header_seen = True
            elif isinstance(chunk, EventChunk) and not header_seen:
                violations.append(
                    "Container violation: FLdt event chunk appears before FLhd header chunk"
                )

        for i, ev in enumerate(project.source_file.events):
            if 0 <= ev.id <= 63 and len(ev.raw) != 1:
                violations.append(
                    f"Event [{i}] ID {ev.id} payload length {len(ev.raw)} != 1 byte required"
                )
            elif 64 <= ev.id <= 127 and len(ev.raw) != 2:
                violations.append(
                    f"Event [{i}] ID {ev.id} payload length {len(ev.raw)} != 2 bytes required"
                )
            elif 128 <= ev.id <= 191 and len(ev.raw) != 4:
                violations.append(
                    f"Event [{i}] ID {ev.id} payload length {len(ev.raw)} != 4 bytes required"
                )

    return violations


def check_invariants(project: Project) -> None:
    """Validate project structural invariants and raise structured exception on violation.

    Raises:
        FlpInvariantViolationError (E_FLP_INVARIANT): If one or more invariants fail.
    """
    violations = validate_invariants(project)
    if violations:
        msg = f"FLP structural invariant violation: {violations[0]}"
        if len(violations) > 1:
            msg += f" (and {len(violations) - 1} more violations)"
        raise FlpInvariantViolationError(
            message=msg,
            details={
                "violations": violations,
                "violation_count": len(violations),
                "project_title": project.title,
                "project_version": project.version,
            },
        )
