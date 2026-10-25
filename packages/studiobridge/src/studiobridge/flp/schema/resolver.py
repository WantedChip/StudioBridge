"""FLP version profile resolver and compatibility detection [FLP-10, FLP-32].

Detects FL Studio project versions from event streams (event ID 199) and selects
the matching VersionProfile. For unknown or newer versions, provides read-only
best-effort fallback, flags risk="unknown_version", and raises FlpVersionUnsupportedError
(E_FLP_VERSION) on unsupported write operations per 12_crosscutting.md §7.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from studiobridge.core.errors import FlpVersionUnsupportedError
from studiobridge.flp.codec.events import Event
from studiobridge.flp.codec.reader import iter_events_from_file
from studiobridge.flp.schema.profile import (
    VersionProfile,
    _compare_version,
    load_builtin_profiles,
    parse_version_tuple,
)
from studiobridge.flp.schema.text import decode_version_string


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Outcome of resolving an FLP project version to a profile [FLP-10]."""

    profile: VersionProfile
    version: str
    version_tuple: tuple[int, ...]
    is_exact_match: bool
    is_fallback: bool
    risk: str | None = None
    read_only: bool = False
    notes: str = ""

    def assert_can_write(self, *, force: bool = False) -> None:
        """Validate write safety for the resolved version profile [FLP-32].

        Raises:
            FlpVersionUnsupportedError (E_FLP_VERSION): If version is unknown or unsupported
                and force is not explicitly enabled.
        """
        if force:
            return

        if self.risk == "unknown_version" or self.read_only or not self.is_exact_match:
            msg = (
                f"FLP version '{self.version}' is unknown or newer than verified profiles "
                f"(risk='{self.risk or 'unknown_version'}'). Writes are blocked to prevent "
                f"corrupting project structure. Use read-only mode or force with force=True."
            )
            raise FlpVersionUnsupportedError(
                message=msg,
                details={
                    "version": self.version,
                    "risk": self.risk or "unknown_version",
                    "profile_id": self.profile.id,
                    "read_only": self.read_only,
                },
            )


class ProfileResolver:
    """Registry and resolver for FL Studio version profiles [FLP-10]."""

    def __init__(self, profiles: dict[str, VersionProfile] | None = None) -> None:
        if profiles is not None:
            self._profiles = dict(profiles)
        else:
            self._profiles = dict(load_builtin_profiles())

    @property
    def profiles(self) -> dict[str, VersionProfile]:
        """Return registered profiles dictionary."""
        return self._profiles

    def register(self, profile: VersionProfile) -> None:
        """Register a new or custom VersionProfile."""
        self._profiles[profile.id] = profile

    def resolve(self, version_str: str) -> ResolutionResult:
        """Resolve a version string (e.g. '26.1.0', '21.0.3') to a VersionProfile.

        Matches against supported ranges. For unknown or newer versions, selects
        the nearest older profile in read-only best-effort mode with risk='unknown_version'.
        """
        cleaned_version = version_str.strip() if version_str else "unknown"
        v_tuple = parse_version_tuple(cleaned_version)

        # 1. Exact match check
        for p in self._profiles.values():
            if p.matches_version(v_tuple):
                return ResolutionResult(
                    profile=p,
                    version=cleaned_version,
                    version_tuple=v_tuple,
                    is_exact_match=True,
                    is_fallback=False,
                    risk=None,
                    read_only=False,
                    notes=f"Exact match on profile '{p.id}'.",
                )

        # 2. No exact match: find nearest older profile
        # Sort profiles by their max_version_tuple descending
        sorted_profiles = sorted(
            self._profiles.values(),
            key=lambda pr: pr.max_version_tuple,
            reverse=True,
        )

        if not sorted_profiles:
            raise FlpVersionUnsupportedError(
                f"No version profiles are registered to handle version '{cleaned_version}'."
            )

        newest_profile = sorted_profiles[0]
        oldest_profile = sorted_profiles[-1]

        # Case A: Version is newer than our highest known profile (e.g. FL 27+)
        if _compare_version(v_tuple, newest_profile.max_version_tuple) > 0:
            return ResolutionResult(
                profile=newest_profile,
                version=cleaned_version,
                version_tuple=v_tuple,
                is_exact_match=False,
                is_fallback=True,
                risk="unknown_version",
                read_only=True,
                notes=(
                    f"Version '{cleaned_version}' is newer than verified profile "
                    f"'{newest_profile.id}'; falling back to nearest older profile "
                    "in read-only mode."
                ),
            )

        # Case B: Version is between profiles or older than oldest
        # Find the highest profile whose min_version is <= v_tuple
        for p in sorted_profiles:
            if _compare_version(v_tuple, p.min_version_tuple) >= 0:
                return ResolutionResult(
                    profile=p,
                    version=cleaned_version,
                    version_tuple=v_tuple,
                    is_exact_match=False,
                    is_fallback=True,
                    risk="unknown_version",
                    read_only=True,
                    notes=(
                        f"Version '{cleaned_version}' fell back to nearest older profile '{p.id}'."
                    ),
                )

        # Case C: Version is older than our lowest known profile (e.g. FL 11)
        return ResolutionResult(
            profile=oldest_profile,
            version=cleaned_version,
            version_tuple=v_tuple,
            is_exact_match=False,
            is_fallback=True,
            risk="unknown_version",
            read_only=True,
            notes=(
                f"Version '{cleaned_version}' is older than lowest supported profile; "
                f"falling back to '{oldest_profile.id}' in read-only mode."
            ),
        )

    def resolve_from_events(self, events: Iterable[Event]) -> ResolutionResult:
        """Resolve version profile by scanning event stream for version string event 199.

        Tagged with [FLP-10].
        """
        for event in events:
            if event.id == 199:
                v_str = decode_version_string(event.raw)
                if v_str:
                    return self.resolve(v_str)

        # If no event 199 is found, use newest profile in read-only fallback mode
        sorted_profiles = sorted(
            self._profiles.values(),
            key=lambda pr: pr.max_version_tuple,
            reverse=True,
        )
        fallback = sorted_profiles[0] if sorted_profiles else None
        if fallback is None:
            raise FlpVersionUnsupportedError("No profiles registered.")

        return ResolutionResult(
            profile=fallback,
            version="unknown",
            version_tuple=(0,),
            is_exact_match=False,
            is_fallback=True,
            risk="unknown_version",
            read_only=True,
            notes="No version string event (ID 199) found in event stream.",
        )

    def resolve_from_file(self, flp_path: Path | str) -> ResolutionResult:
        """Stream events from an FLP file to detect version event 199 and resolve profile."""
        path = Path(flp_path)
        if not path.is_file():
            raise FileNotFoundError(f"FLP file not found: {path}")

        events = iter_events_from_file(path)
        return self.resolve_from_events(events)


# Default module-level singleton resolver
_DEFAULT_RESOLVER = ProfileResolver()


def get_default_resolver() -> ProfileResolver:
    """Get the default singleton ProfileResolver."""
    return _DEFAULT_RESOLVER


def resolve_profile(
    target: str | Path | Iterable[Event],
) -> ResolutionResult:
    """Resolve an FLP profile from a version string, file path, or event stream [FLP-10]."""
    if isinstance(target, (str, Path)):
        p = Path(target)
        if p.is_file():
            return _DEFAULT_RESOLVER.resolve_from_file(p)
        return _DEFAULT_RESOLVER.resolve(str(target))

    return _DEFAULT_RESOLVER.resolve_from_events(target)


def resolve_profile_from_events(events: Iterable[Event]) -> ResolutionResult:
    """Resolve version profile from an iterable of Event objects [FLP-10]."""
    return _DEFAULT_RESOLVER.resolve_from_events(events)


def resolve_profile_from_file(flp_path: Path | str) -> ResolutionResult:
    """Resolve version profile from an FLP project file path [FLP-10]."""
    return _DEFAULT_RESOLVER.resolve_from_file(flp_path)


def get_profile(profile_id: str) -> VersionProfile:
    """Retrieve a registered VersionProfile by ID [FLP-10]."""
    profiles = _DEFAULT_RESOLVER.profiles
    if profile_id not in profiles:
        raise KeyError(
            f"Profile '{profile_id}' not found. Available profiles: {list(profiles.keys())}"
        )
    return profiles[profile_id]


def list_profiles() -> list[VersionProfile]:
    """Return all registered VersionProfile instances [FLP-10]."""
    return list(_DEFAULT_RESOLVER.profiles.values())
