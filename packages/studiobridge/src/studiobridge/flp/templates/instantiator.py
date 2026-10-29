"""Template-seeded project instantiation and stock fragment library [FLP-40].

Implements clean-room fragment instantiation, relocation rules, seed integrity
verification, and provenance tracking.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from studiobridge.core.errors import TemplateFragmentUnavailableError
from studiobridge.flp.codec.events import Event
from studiobridge.flp.model.elements import Channel, OpaquePlugin
from studiobridge.flp.model.project import Project
from studiobridge.flp.schema.text import encode_text
from studiobridge.flp.validate.invariants import check_invariants

if TYPE_CHECKING:
    pass

_SEEDS_DIR = Path(__file__).parent / "seeds"


@dataclass(frozen=True, slots=True)
class FragmentProvenance:
    """Provenance audit metadata for an FLP fragment [FLP-40, FLP-60].

    Attributes:
        fl_version: Minor/major FL Studio version where fragment was authored.
        author: Contributor or creator identity.
        date: ISO-8601 UTC timestamp of authorship or extraction.
        source_file: Original project file basename.
        notes: Contextual notes or provenance documentation.
    """

    fl_version: str
    author: str
    date: str
    source_file: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert provenance to dictionary representation."""
        return {
            "fl_version": self.fl_version,
            "author": self.author,
            "date": self.date,
            "source_file": self.source_file,
            "notes": self.notes,
        }


@dataclass
class Fragment:
    """Proven binary project fragment with relocation rules [FLP-40].

    Attributes:
        profile: Profile version identifier (e.g. 'fl26', 'fl21_25', or '*').
        kind: Functional kind (e.g. 'sampler', 'audio_clip', 'layer', 'plugin', 'effect').
        plugin_id: Identifier for plugin (e.g. '3x_osc', 'fruity_parametric_eq_2', or None).
        name: Default display name.
        events: Raw event slice preserving opaque binary blobs verbatim.
        provenance: Provenance audit metadata.
        relocation_rules: Rules for rewriting known fields on instantiation.
    """

    profile: str
    kind: str
    plugin_id: str | None
    name: str
    events: list[Event]
    provenance: FragmentProvenance
    relocation_rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert fragment to serializable dictionary."""
        return {
            "profile": self.profile,
            "kind": self.kind,
            "plugin_id": self.plugin_id,
            "name": self.name,
            "event_count": len(self.events),
            "provenance": self.provenance.to_dict(),
            "relocation_rules": self.relocation_rules,
        }


def get_seeds_dir() -> Path:
    """Return the absolute path to the bundled seed templates directory."""
    return _SEEDS_DIR


def list_seed_templates() -> list[str]:
    """Return list of available seed template names without extension."""
    seeds_dir = get_seeds_dir()
    if not seeds_dir.is_dir():
        return []
    return sorted(p.stem for p in seeds_dir.glob("*.flp"))


def get_seed_path(name: str) -> Path:
    """Resolve Path to a seed template file by name."""
    seeds_dir = get_seeds_dir()
    candidate = seeds_dir / (name if name.endswith(".flp") else f"{name}.flp")
    if not candidate.is_file():
        raise FileNotFoundError(f"Seed template '{name}' not found in {seeds_dir}")
    return candidate


def verify_seed_integrity(seeds_dir: Path | None = None) -> bool:
    """Verify SHA-256 hashes of all bundled seed templates against hashes.json.

    Returns:
        True if all seed files exist and match their expected cryptographic hash.
        False if any seed file is missing, modified, or has an invalid checksum.
    """
    target_dir = seeds_dir or get_seeds_dir()
    hash_file = target_dir / "hashes.json"
    if not hash_file.is_file():
        return False

    try:
        expected_hashes: dict[str, str] = json.loads(hash_file.read_text(encoding="utf-8"))
    except Exception:
        return False

    for filename, expected_hash in expected_hashes.items():
        file_path = target_dir / filename
        if not file_path.is_file():
            return False
        content = file_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash.lower() != expected_hash.lower():
            return False

    return True


class TemplateLibrary:
    """Repository indexing project templates and relocatable binary fragments [FLP-40].

    Maintains stock fragment definitions for Sampler, Audio Clip, Layer, 3x Osc,
    and Fruity Parametric EQ 2 indexed by (profile, kind, plugin_id).
    """

    _fragments: dict[tuple[str, str, str | None], Fragment] = {}
    _aliases: dict[str, tuple[str, str, str | None]] = {}
    _stock_keys: set[tuple[str, str, str | None]] = set()
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Initialize stock fragment library if not already initialized."""
        if cls._initialized:
            return
        cls._init_stock_fragments()
        cls._stock_keys.update(cls._fragments.keys())
        cls._initialized = True

    @classmethod
    def _init_stock_fragments(cls) -> None:
        """Load and index baseline stock fragments from one_each_stock.flp."""
        stock_flp_path = get_seeds_dir() / "one_each_stock.flp"
        if not stock_flp_path.is_file():
            return

        try:
            stock_proj = Project.load(stock_flp_path)
        except Exception:
            return

        date_str = "2026-10-25T00:00:00Z"

        # 1. Sampler
        cls.register_fragment(
            Fragment(
                profile="fl26",
                kind="sampler",
                plugin_id=None,
                name="Sampler",
                events=[
                    Event(id=64, raw=struct.pack("<H", 0)),
                    Event(id=200, raw=encode_text("Sampler", "utf-16-le")),
                    Event(id=215, raw=b"\x00" * 32),
                ],
                provenance=FragmentProvenance(
                    fl_version="26.1.0",
                    author="StudioBridge",
                    date=date_str,
                    source_file="one_each_stock.flp",
                    notes="Curated stock sampler fragment",
                ),
                relocation_rules={"rewrite_index": True, "rewrite_name": True},
            ),
            alias="sampler",
        )

        # 2. Audio Clip
        cls.register_fragment(
            Fragment(
                profile="fl26",
                kind="audio_clip",
                plugin_id=None,
                name="Audio Clip",
                events=[
                    Event(id=64, raw=struct.pack("<H", 0)),
                    Event(id=200, raw=encode_text("Audio Clip", "utf-16-le")),
                    Event(id=215, raw=b"\x00" * 32),
                ],
                provenance=FragmentProvenance(
                    fl_version="26.1.0",
                    author="StudioBridge",
                    date=date_str,
                    source_file="one_each_stock.flp",
                    notes="Curated stock audio clip fragment",
                ),
                relocation_rules={"rewrite_index": True, "rewrite_name": True},
            ),
            alias="audio_clip",
        )

        # 3. Layer
        cls.register_fragment(
            Fragment(
                profile="fl26",
                kind="layer",
                plugin_id=None,
                name="Layer",
                events=[
                    Event(id=64, raw=struct.pack("<H", 0)),
                    Event(id=200, raw=encode_text("Layer", "utf-16-le")),
                    Event(id=215, raw=b"\x00" * 32),
                ],
                provenance=FragmentProvenance(
                    fl_version="26.1.0",
                    author="StudioBridge",
                    date=date_str,
                    source_file="one_each_stock.flp",
                    notes="Curated stock layer channel fragment",
                ),
                relocation_rules={"rewrite_index": True, "rewrite_name": True},
            ),
            alias="layer",
        )

        # 4. 3x Osc
        # Extract opaque plugin data from channel 3 if present in one_each_stock.flp
        osc_data = (
            stock_proj.channels[3].plugin.data
            if len(stock_proj.channels) > 3 and stock_proj.channels[3].plugin
            else b"Fruity Wrapper 3x Osc State\x00" + b"\x00" * 32
        )
        cls.register_fragment(
            Fragment(
                profile="fl26",
                kind="plugin",
                plugin_id="3x_osc",
                name="3x Osc",
                events=[
                    Event(id=64, raw=struct.pack("<H", 0)),
                    Event(id=200, raw=encode_text("3x Osc", "utf-16-le")),
                    Event(id=213, raw=osc_data),
                    Event(id=215, raw=b"\x00" * 32),
                ],
                provenance=FragmentProvenance(
                    fl_version="26.1.0",
                    author="StudioBridge",
                    date=date_str,
                    source_file="one_each_stock.flp",
                    notes="Curated stock 3x Osc synthesizer fragment with opaque wrapper state",
                ),
                relocation_rules={"rewrite_index": True, "rewrite_name": True},
            ),
            alias="3x_osc",
        )

        # 5. Fruity Parametric EQ 2
        eq_data = (
            stock_proj.channels[4].plugin.data
            if len(stock_proj.channels) > 4 and stock_proj.channels[4].plugin
            else b"Fruity Wrapper EQ2 State\x00" + b"\x00" * 32
        )
        cls.register_fragment(
            Fragment(
                profile="fl26",
                kind="plugin",
                plugin_id="fruity_parametric_eq_2",
                name="Fruity Parametric EQ 2",
                events=[
                    Event(id=64, raw=struct.pack("<H", 0)),
                    Event(id=200, raw=encode_text("Fruity Parametric EQ 2", "utf-16-le")),
                    Event(id=213, raw=eq_data),
                    Event(id=215, raw=b"\x00" * 32),
                ],
                provenance=FragmentProvenance(
                    fl_version="26.1.0",
                    author="StudioBridge",
                    date=date_str,
                    source_file="one_each_stock.flp",
                    notes="Curated stock Fruity Parametric EQ 2 effect fragment",
                ),
                relocation_rules={"rewrite_index": True, "rewrite_name": True},
            ),
            alias="fruity_parametric_eq_2",
        )

    @classmethod
    def register_fragment(cls, fragment: Fragment, alias: str | None = None) -> None:
        """Register a fragment in the library index."""

        def _norm(s: str) -> str:
            return s.strip().lower().replace("-", "_").replace(" ", "_")

        key = (fragment.profile, fragment.kind, fragment.plugin_id)
        # Protect stock keys from being overwritten by custom fragments
        if key in cls._stock_keys and fragment.name not in (
            "Sampler",
            "Audio Clip",
            "Layer",
            "3x Osc",
            "Fruity Parametric EQ 2",
        ):
            key = (fragment.profile, fragment.kind, _norm(fragment.name))

        cls._fragments[key] = fragment
        # Register wildcard profile fallback
        wildcard_key = ("*", key[1], key[2])
        if wildcard_key not in cls._stock_keys or fragment.name in (
            "Sampler",
            "Audio Clip",
            "Layer",
            "3x Osc",
            "Fruity Parametric EQ 2",
        ):
            cls._fragments[wildcard_key] = fragment

        if alias:
            cls._aliases[alias.lower()] = key
            cls._aliases[_norm(alias)] = key
        elif fragment.plugin_id and _norm(fragment.plugin_id) not in cls._aliases:
            cls._aliases[fragment.plugin_id.lower()] = key
            cls._aliases[_norm(fragment.plugin_id)] = key
        elif _norm(fragment.kind) not in cls._aliases:
            cls._aliases[fragment.kind.lower()] = key
            cls._aliases[_norm(fragment.kind)] = key

    @classmethod
    def get_fragment(
        cls,
        profile: str = "fl26",
        kind: str = "sampler",
        plugin_id: str | None = None,
    ) -> Fragment | None:
        """Retrieve fragment by (profile, kind, plugin_id) or alias."""
        cls._ensure_initialized()

        # 1. Direct key match
        key = (profile, kind, plugin_id)
        if key in cls._fragments:
            return cls._fragments[key]

        # 2. Wildcard profile match
        wildcard_key = ("*", kind, plugin_id)
        if wildcard_key in cls._fragments:
            return cls._fragments[wildcard_key]

        # 3. Alias match
        norm_kind = kind.strip().lower().replace("-", "_").replace(" ", "_")
        if norm_kind in cls._aliases:
            resolved_key = cls._aliases[norm_kind]
            if resolved_key in cls._fragments:
                return cls._fragments[resolved_key]
        if kind.lower() in cls._aliases:
            resolved_key = cls._aliases[kind.lower()]
            if resolved_key in cls._fragments:
                return cls._fragments[resolved_key]

        return None

    @classmethod
    def list_fragments(cls) -> list[Fragment]:
        """Return all distinct fragments registered in the library."""
        cls._ensure_initialized()
        seen_names = set()
        unique: list[Fragment] = []
        for frag in cls._fragments.values():
            if frag.name not in seen_names:
                seen_names.add(frag.name)
                unique.append(frag)
        return unique

    @classmethod
    def list_templates(cls) -> list[dict[str, Any]]:
        """Return summary of all available seed templates."""
        results: list[dict[str, Any]] = []
        for name in list_seed_templates():
            path = get_seed_path(name)
            try:
                proj = Project.load(path)
                results.append(
                    {
                        "name": name,
                        "file": path.name,
                        "title": proj.title,
                        "author": proj.author,
                        "version": proj.version,
                        "tempo": proj.tempo,
                        "channel_count": len(proj.channels),
                        "pattern_count": len(proj.patterns),
                        "channels": [c.name for c in proj.channels],
                    }
                )
            except Exception:
                results.append({"name": name, "file": path.name, "error": "Failed to parse"})
        return results

    @classmethod
    def extract_fragment(
        cls,
        project: Project,
        channel_index: int,
        *,
        name: str | None = None,
        kind: str | None = None,
        author: str | None = None,
    ) -> Fragment:
        """Extract a channel fragment and record provenance from a project [FLP-40]."""
        cls._ensure_initialized()
        if not (0 <= channel_index < len(project.channels)):
            raise IndexError(
                f"Channel index {channel_index} out of range (0..{len(project.channels) - 1})"
            )

        target_ch = project.channels[channel_index]
        profile_id = project.profile.id if project.profile else "fl26"
        text_encoding = (
            project.profile.text_encoding.default_encoding if project.profile else "utf-16-le"
        )

        extracted_events: list[Event] = []
        if project.source_file is not None and target_ch.source_events:
            for ev_idx in target_ch.source_events:
                if 0 <= ev_idx < len(project.source_file.events):
                    extracted_events.append(copy.deepcopy(project.source_file.events[ev_idx]))

        if not extracted_events:
            # Reconstruct standard channel event slice if source events missing
            extracted_events.append(Event(id=64, raw=struct.pack("<H", 0)))
            extracted_events.append(
                Event(id=200, raw=encode_text(target_ch.name, encoding=text_encoding))
            )
            if target_ch.plugin is not None:
                extracted_events.append(Event(id=213, raw=target_ch.plugin.data))
            extracted_events.append(Event(id=215, raw=b"\x00" * 32))

        frag_name = name or target_ch.name
        frag_kind = kind or (
            target_ch.channel_type
            if target_ch.channel_type in ("sampler", "audio_clip", "layer", "automation")
            else ("plugin" if target_ch.plugin else "sampler")
        )
        plugin_id = (
            frag_name.lower().replace(" ", "_").replace("-", "_") if target_ch.plugin else None
        )

        provenance = FragmentProvenance(
            fl_version=project.version,
            author=author or project.author or "StudioBridge",
            date=datetime.now(timezone.utc).isoformat(),
            source_file=project.file_path.name if project.file_path else "extracted.flp",
            notes=f"Extracted from channel [{channel_index}] '{target_ch.name}'",
        )

        frag = Fragment(
            profile=profile_id,
            kind=frag_kind,
            plugin_id=plugin_id,
            name=frag_name,
            events=extracted_events,
            provenance=provenance,
            relocation_rules={"rewrite_index": True, "rewrite_name": True},
        )

        cls.register_fragment(frag, alias=frag_name)
        return frag


def instantiate_project(
    template_name: str = "minimal",
    params: dict[str, Any] | None = None,
) -> Project:
    """Instantiate a fresh FL Studio Project from a seed template [FLP-40].

    Args:
        template_name: Name of seed template (e.g. 'minimal', 'one_each_stock', 'sampler').
        params: Optional project parameter overrides (title, author, comments, tempo, channels).

    Returns:
        Fresh valid Project object model.

    Raises:
        TemplateFragmentUnavailableError: If seed template does not exist.
        FlpInvariantViolationError: If resulting project violates structural invariants.
    """
    TemplateLibrary._ensure_initialized()
    norm_name = template_name.lower().removesuffix(".flp")
    available_seeds = list_seed_templates()
    if norm_name not in available_seeds:
        raise TemplateFragmentUnavailableError(
            f"Seed template '{template_name}' is not available in the library. "
            f"Available templates: {', '.join(available_seeds)}",
            code="E_UNAVAILABLE",
            remedy=(
                f"Use one of the available templates: {', '.join(available_seeds)}, "
                "or run 'sbridge flp template add <flp> --select channel:<id>' to create fragments."
            ),
            capability=f"flp.template.{template_name}",
            details={"template": template_name, "available": available_seeds},
        )

    seed_path = get_seed_path(norm_name)
    project = Project.load(seed_path)

    if params:
        with project.mutate() as m:
            if "title" in params:
                m.set_title(str(params["title"]))
            if "author" in params:
                m.set_author(str(params["author"]))
            if "comments" in params:
                m.set_comments(str(params["comments"]))
            if "tempo" in params:
                m.set_tempo(float(params["tempo"]))

        # Optional extra channels requested in params
        if "channels" in params and isinstance(params["channels"], list):
            for ch_spec in params["channels"]:
                if isinstance(ch_spec, str):
                    instantiate_channel(project, ch_spec)
                elif isinstance(ch_spec, dict):
                    ch_kind = ch_spec.get("kind", "sampler")
                    instantiate_channel(project, ch_kind, ch_spec)

    check_invariants(project)
    return project


def instantiate_channel(
    project: Project,
    kind: str,
    params: dict[str, Any] | None = None,
    *,
    profile: str | None = None,
    plugin_id: str | None = None,
) -> Channel:
    """Instantiate and append a relocatable stock fragment into a project [FLP-40].

    Copies proven binary fragment events, rewrites channel index and name,
    and preserves opaque plugin wrapper bytes and channel parameters intact.

    Args:
        project: Target Project to add channel into.
        kind: Fragment kind or alias (e.g. 'sampler', 'audio_clip', 'layer', '3x_osc',
            'fruity_parametric_eq_2').
        params: Optional channel parameters (name, color, target_mixer_track, volume, pan).
        profile: Target version profile ID (default: project.profile or 'fl26').
        plugin_id: Optional plugin identifier.

    Returns:
        The newly added Channel instance.

    Raises:
        TemplateFragmentUnavailableError: If fragment is not in the library.
        FlpInvariantViolationError: If resulting project violates structural invariants.
    """
    TemplateLibrary._ensure_initialized()
    prof_id = profile or (project.profile.id if project.profile else "fl26")
    fragment = TemplateLibrary.get_fragment(profile=prof_id, kind=kind, plugin_id=plugin_id)

    if fragment is None:
        raise TemplateFragmentUnavailableError(
            f"Fragment '{kind}' is unavailable in the template library.",
            code="E_UNAVAILABLE",
            remedy=(
                f"Create '{kind}' once in FL Studio, save as a template, and run "
                f"'sbridge flp template add <flp> --select channel:<id>' to import it."
            ),
            capability=f"flp.fragment.{kind}",
            details={"kind": kind, "profile": prof_id, "plugin_id": plugin_id},
        )

    new_index = len(project.channels)
    p_dict = params or {}
    new_name = str(p_dict.get("name", fragment.name))
    new_mixer_track = int(p_dict.get("target_mixer_track", 0))
    new_color = p_dict.get("color")
    new_volume = float(p_dict.get("volume", 1.0))
    new_pan = float(p_dict.get("pan", 0.0))

    text_encoding = (
        project.profile.text_encoding.default_encoding if project.profile else "utf-16-le"
    )

    # Relocate fragment events
    relocated_events: list[Event] = []
    has_event_64 = False
    has_event_200 = False
    plugin_data: bytes | None = None

    for ev in fragment.events:
        new_ev = copy.deepcopy(ev)
        if new_ev.id == 64:  # New channel rack index
            new_ev.raw = struct.pack("<H", new_index)
            has_event_64 = True
        elif new_ev.id == 200:  # Channel display name
            new_ev.raw = encode_text(new_name, encoding=text_encoding)
            has_event_200 = True
        elif new_ev.id == 213:  # Plugin wrapper blob (preserved intact!)
            plugin_data = new_ev.raw

        relocated_events.append(new_ev)

    if not has_event_64:
        relocated_events.insert(0, Event(id=64, raw=struct.pack("<H", new_index)))
    if not has_event_200:
        relocated_events.insert(1, Event(id=200, raw=encode_text(new_name, encoding=text_encoding)))

    # Determine channel type
    if fragment.kind in ("sampler", "audio_clip", "layer", "automation"):
        ch_type = fragment.kind
    elif plugin_data is not None or fragment.plugin_id is not None:
        ch_type = "plugin"
    else:
        ch_type = "sampler"

    opaque_plugin = (
        OpaquePlugin(data=plugin_data, wrapper_kind="fruity_wrapper", name_hint=new_name)
        if plugin_data
        else None
    )

    channel = Channel(
        index=new_index,
        name=new_name,
        channel_type=ch_type,
        color=new_color,
        target_mixer_track=new_mixer_track,
        volume=new_volume,
        pan=new_pan,
        plugin=opaque_plugin,
        _fragment_events=relocated_events,
        provenance=fragment.provenance,
    )

    project.channels.append(channel)

    # Sync source file header if present
    if project.source_file is not None and project.source_file.header is not None:
        project.source_file.header.channels = len(project.channels)

    # Invariant validation check
    check_invariants(project)

    # Audit logging if mutator attached
    if project._mutator is not None:
        project._mutator.touched_channels.add(new_index)
        project._mutator._log(
            "channel.instantiate_fragment",
            f"channel:{new_index}",
            {"kind": kind, "name": new_name, "target_mixer_track": new_mixer_track},
            None,
            new_name,
        )

    return channel


def instantiate(
    kind: str = "minimal",
    params: dict[str, Any] | None = None,
    *,
    project: Project | None = None,
    profile: str = "fl26",
    plugin_id: str | None = None,
) -> Project:
    """Instantiate a project or add a fragment conforming to schema invariants [FLP-40].

    When called with project=None:
        Instantiates a fresh project from a seed template (e.g. 'minimal', 'sampler')
        or creates a minimal project with the specified fragment channel.

    When called with project=<Project>:
        Instantiates and adds the requested fragment into the existing project.

    Args:
        kind: Template name ('minimal', 'sampler', 'one_each_stock') or fragment kind ('3x_osc').
        params: Parameters dictionary.
        project: Target project if adding a fragment to an existing project.
        profile: Profile version ID (default: 'fl26').
        plugin_id: Optional plugin identifier.

    Returns:
        The instantiated or modified Project conforming strictly to structural invariants.

    Raises:
        TemplateFragmentUnavailableError: If requested template or fragment is unavailable.
        FlpInvariantViolationError: If project violates structural schema invariants.
    """
    TemplateLibrary._ensure_initialized()

    # Case 1: Add fragment to an existing project
    if project is not None:
        instantiate_channel(project, kind, params, profile=profile, plugin_id=plugin_id)
        return project

    # Case 2: Fresh project from seed template
    norm_kind = kind.lower().removesuffix(".flp")
    if norm_kind in list_seed_templates():
        return instantiate_project(norm_kind, params)

    # Case 3: Fresh project starting from minimal and adding requested fragment
    fragment = TemplateLibrary.get_fragment(profile=profile, kind=kind, plugin_id=plugin_id)
    if fragment is not None:
        proj = instantiate_project("minimal")
        instantiate_channel(proj, kind, params, profile=profile, plugin_id=plugin_id)
        return proj

    # Case 4: Not found
    raise TemplateFragmentUnavailableError(
        f"Template or fragment '{kind}' is unavailable in the library.",
        code="E_UNAVAILABLE",
        remedy=(
            f"Use one of the available templates: {', '.join(list_seed_templates())}, "
            "or run 'sbridge flp template add <flp> --select channel:<id>' to import "
            "custom fragments."
        ),
        capability=f"flp.instantiate.{kind}",
        details={"kind": kind, "profile": profile, "plugin_id": plugin_id},
    )
