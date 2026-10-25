"""Piano roll script generator, templates, and note application orchestration."""

from studiobridge.pianoroll.generator import (
    PyscriptGenerator,
    generate_pyscript,
    generate_pyscript_jobs,
)
from studiobridge.pianoroll.templates import (
    DEFAULT_DEVICE_NAME,
    format_notes_literal,
    render_apply_script,
)
from studiobridge.pianoroll.types import (
    DEFAULT_BEATS_PER_BAR,
    DEFAULT_PPQ,
    MAX_PAYLOAD_BYTES,
    NOTE_NAMES,
    SUBDIVISION_BEAT_RATIOS,
    VALID_APPLY_MODES,
    ApplyMode,
    Note,
    PyscriptJob,
    midi_to_note_name,
    normalize_color,
    normalize_filter,
    normalize_pan,
    normalize_release,
    normalize_velocity,
    note_name_to_midi,
    subdivision_to_ticks,
    ticks_to_subdivision,
)

__all__ = [
    "DEFAULT_BEATS_PER_BAR",
    "DEFAULT_DEVICE_NAME",
    "DEFAULT_PPQ",
    "MAX_PAYLOAD_BYTES",
    "NOTE_NAMES",
    "SUBDIVISION_BEAT_RATIOS",
    "VALID_APPLY_MODES",
    "ApplyMode",
    "Note",
    "PyscriptGenerator",
    "PyscriptJob",
    "format_notes_literal",
    "generate_pyscript",
    "generate_pyscript_jobs",
    "midi_to_note_name",
    "normalize_color",
    "normalize_filter",
    "normalize_pan",
    "normalize_release",
    "normalize_velocity",
    "note_name_to_midi",
    "render_apply_script",
    "subdivision_to_ticks",
    "ticks_to_subdivision",
]
