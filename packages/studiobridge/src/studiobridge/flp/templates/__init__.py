"""Template-seeded project instantiation, baseline seeds, and stock fragment library."""

from __future__ import annotations

from studiobridge.core.errors import (
    TemplateFragmentUnavailable,
    TemplateFragmentUnavailableError,
)
from studiobridge.flp.templates.instantiator import (
    Fragment,
    FragmentProvenance,
    TemplateLibrary,
    get_seed_path,
    get_seeds_dir,
    instantiate,
    instantiate_channel,
    instantiate_project,
    list_seed_templates,
    verify_seed_integrity,
)

__all__ = [
    "Fragment",
    "FragmentProvenance",
    "TemplateFragmentUnavailable",
    "TemplateFragmentUnavailableError",
    "TemplateLibrary",
    "get_seed_path",
    "get_seeds_dir",
    "instantiate",
    "instantiate_channel",
    "instantiate_project",
    "list_seed_templates",
    "verify_seed_integrity",
]
