"""Project risk assessment calculator and static health scoring.

Calculates static health and risk scores for FL Studio project (.flp) files
based on unknown FL versions, modified opaque binary blobs, template mismatches,
size anomalies, and unconfirmed event formats per [FLP-40].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from studiobridge.flp.model.project import Project

if TYPE_CHECKING:
    pass

RiskCategory = Literal[
    "unknown_version",
    "modified_opaque_blob",
    "template_mismatch",
    "size_anomaly",
    "unconfirmed_event",
]
RiskSeverity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True, slots=True)
class RiskFactor:
    """Represents an identified structural or version risk factor in an FLP project.

    Attributes:
        category: Risk classification category.
        severity: Severity rating of the risk.
        score_penalty: Contribution of this factor to the total risk score (0..100).
        message: Human-readable explanation of the risk.
        details: Additional structured context or metadata.
    """

    category: RiskCategory
    severity: RiskSeverity
    score_penalty: int
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert factor to dictionary representation."""
        return {
            "category": self.category,
            "severity": self.severity,
            "score_penalty": self.score_penalty,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class ProjectRiskReport:
    """Project static health and risk scoring assessment report.

    Attributes:
        score: Total composite risk score from 0 (pristine / low risk) to 100 (critical).
        level: Overall risk level categorization ('low', 'medium', 'high', 'critical').
        factors: List of individual risk factors detected.
        is_safe_to_load: True if score < 50 and no critical risk factors are present.
        summary: Concise summary describing the project health status.
    """

    score: int
    level: RiskLevel
    factors: list[RiskFactor]
    is_safe_to_load: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert risk report to dictionary representation."""
        return {
            "score": self.score,
            "level": self.level,
            "factors": [f.to_dict() for f in self.factors],
            "is_safe_to_load": self.is_safe_to_load,
            "summary": self.summary,
        }


def calculate_project_risk(project: Project | Path | str | bytes) -> ProjectRiskReport:
    """Calculate static health risk score for an FL Studio project.

    Evaluates:
    1. Unknown FL version: project version not matching supported profiles or future version.
    2. Modified opaque blobs: synthesized or modified plugin wrapper/parameter bytes
       without provenance.
    3. Template mismatch: fragment provenance minor version differing from project minor version.
    4. Size anomalies: empty container, header count mismatch, truncated payloads, anomalous chunks.
    5. Unconfirmed event formats: event IDs unrecognized in version profile schemas.

    Args:
        project: Target Project instance, file path, or raw FLP bytes.

    Returns:
        ProjectRiskReport with numerical score (0..100), categorization level, and factor list.
    """
    if not isinstance(project, Project):
        project = Project.load(project)

    factors: list[RiskFactor] = []

    # -------------------------------------------------------------------------
    # 1. Unknown FL Studio Version Analysis
    # -------------------------------------------------------------------------
    profile = project.profile
    if profile is None:
        factors.append(
            RiskFactor(
                category="unknown_version",
                severity="critical",
                score_penalty=40,
                message="Project does not have a resolved version profile.",
            )
        )
    else:
        # Check profile risk declaration or fallback indicator
        profile_risk = getattr(profile, "risk", None)
        if profile_risk == "unknown_version" or profile.id == "fallback":
            factors.append(
                RiskFactor(
                    category="unknown_version",
                    severity="high",
                    score_penalty=35,
                    message=(
                        f"Project version '{project.version}' is not directly supported; "
                        f"using fallback profile '{profile.id}'."
                    ),
                    details={"profile_id": profile.id, "version": project.version},
                )
            )

        # Check version string sanity
        version_str = project.version or ""
        if version_str:
            parts = version_str.split(".")
            with_numeric = [p for p in parts if p.isdigit()]
            if with_numeric:
                major = int(with_numeric[0])
                if major >= 27:
                    factors.append(
                        RiskFactor(
                            category="unknown_version",
                            severity="high",
                            score_penalty=35,
                            message=(
                                f"Project FL Studio major version {major} exceeds tested "
                                "profiles (FL 21–26)."
                            ),
                            details={"major": major, "version": version_str},
                        )
                    )
        else:
            factors.append(
                RiskFactor(
                    category="unknown_version",
                    severity="medium",
                    score_penalty=25,
                    message="Project version string could not be extracted from FLhd/FLdt.",
                )
            )

    # -------------------------------------------------------------------------
    # 2. Modified Opaque Blobs Analysis ([FLP-40])
    # -------------------------------------------------------------------------
    modified_channels: list[int] = []
    synthesized_channels: list[int] = []

    for ch in project.channels:
        plugin = ch.plugin
        if plugin is not None:
            if getattr(plugin, "is_modified", False):
                modified_channels.append(ch.index)
            elif getattr(plugin, "is_synthesized", False):
                synthesized_channels.append(ch.index)
            elif not ch.source_events and not getattr(ch, "provenance", None) and plugin.data:
                # Plugin data present on newly created channel without template provenance
                synthesized_channels.append(ch.index)

    if modified_channels:
        factors.append(
            RiskFactor(
                category="modified_opaque_blob",
                severity="high",
                score_penalty=40,
                message=(
                    f"Channels {modified_channels} contain modified opaque plugin wrapper "
                    "blobs without host provenance."
                ),
                details={"channel_indices": modified_channels},
            )
        )
    if synthesized_channels:
        factors.append(
            RiskFactor(
                category="modified_opaque_blob",
                severity="high",
                score_penalty=40,
                message=(
                    f"Channels {synthesized_channels} contain procedurally synthesized "
                    "opaque plugin data [FLP-40]."
                ),
                details={"channel_indices": synthesized_channels},
            )
        )

    # Check mixer track slots
    modified_slots: list[str] = []
    for track in project.mixer:
        for slot in track.slots:
            if slot.plugin is not None and (
                getattr(slot.plugin, "is_modified", False)
                or getattr(slot.plugin, "is_synthesized", False)
            ):
                modified_slots.append(f"track:{track.index}/slot:{slot.index}")
    if modified_slots:
        factors.append(
            RiskFactor(
                category="modified_opaque_blob",
                severity="high",
                score_penalty=35,
                message=(
                    f"Mixer effect slots {modified_slots} contain modified or synthesized "
                    "opaque effect wrapper data."
                ),
                details={"slots": modified_slots},
            )
        )

    # -------------------------------------------------------------------------
    # 3. Template Mismatch Analysis (Fragment from different FL minor)
    # -------------------------------------------------------------------------
    proj_version = project.version or ""
    proj_major_minor = ".".join(proj_version.split(".")[:2]) if proj_version else ""

    mismatched_channels: list[dict[str, str]] = []
    for ch in project.channels:
        prov = getattr(ch, "provenance", None)
        if prov is not None and hasattr(prov, "fl_version") and prov.fl_version:
            frag_major_minor = ".".join(prov.fl_version.split(".")[:2])
            if proj_major_minor and frag_major_minor and frag_major_minor != proj_major_minor:
                mismatched_channels.append(
                    {
                        "channel_index": str(ch.index),
                        "channel_name": ch.name,
                        "fragment_version": prov.fl_version,
                        "project_version": proj_version,
                    }
                )

    if mismatched_channels:
        factors.append(
            RiskFactor(
                category="template_mismatch",
                severity="medium",
                score_penalty=30,
                message=(
                    f"Detected {len(mismatched_channels)} channel(s) instantiated from template "
                    f"fragments of a different FL Studio minor version."
                ),
                details={"mismatches": mismatched_channels},
            )
        )

    # -------------------------------------------------------------------------
    # 4. Size Anomalies Analysis
    # -------------------------------------------------------------------------
    source_file = project.source_file
    if source_file is not None:
        header = source_file.header
        if header is not None and header.channels != len(project.channels):
            # Header channel count mismatch
            factors.append(
                RiskFactor(
                    category="size_anomaly",
                    severity="high",
                    score_penalty=35,
                    message=(
                        f"Header channel declaration ({header.channels}) disagrees with actual "
                        f"channel count ({len(project.channels)}) [FLP-05]."
                    ),
                    details={"header": header.channels, "actual": len(project.channels)},
                )
            )

        # Container events count vs channel count
        total_events = len(source_file.events)
        if total_events == 0 and len(project.channels) > 0:
            factors.append(
                RiskFactor(
                    category="size_anomaly",
                    severity="critical",
                    score_penalty=45,
                    message=(
                        f"Project contains {len(project.channels)} channels "
                        "but 0 binary events in FLdt."
                    ),
                )
            )

        # High unmodeled event ratio (> 50% of events)
        if total_events > 10:
            unmodeled_count = len(project.unmodeled_events)
            if unmodeled_count > (total_events * 0.5):
                factors.append(
                    RiskFactor(
                        category="size_anomaly",
                        severity="medium",
                        score_penalty=20,
                        message=(
                            "Unusually high unmodeled event count: "
                            f"{unmodeled_count}/{total_events} (>50% unmodeled events)."
                        ),
                        details={"unmodeled": unmodeled_count, "total": total_events},
                    )
                )

        # Single event payload size anomaly (> 10MB)
        for ev in source_file.events:
            if len(ev.raw) > 10 * 1024 * 1024:
                factors.append(
                    RiskFactor(
                        category="size_anomaly",
                        severity="high",
                        score_penalty=30,
                        message=(
                            f"Event ID {ev.id} payload exceeds 10 MB ({len(ev.raw)} bytes); "
                            "potential memory or parsing anomaly."
                        ),
                        details={"event_id": ev.id, "size": len(ev.raw)},
                    )
                )
                break

    # -------------------------------------------------------------------------
    # 5. Unconfirmed Event Formats Analysis
    # -------------------------------------------------------------------------
    if source_file is not None and profile is not None:
        known_meanings = profile.event_meanings or {}
        unconfirmed_ids: set[int] = set()
        for ev in source_file.events:
            # Event IDs >= 240 or outside profile meanings (excluding standard EOF 0)
            if ev.id not in known_meanings and (ev.id >= 240 or ev.id == 255):
                unconfirmed_ids.add(ev.id)

        if unconfirmed_ids:
            factors.append(
                RiskFactor(
                    category="unconfirmed_event",
                    severity="medium",
                    score_penalty=25,
                    message=(
                        f"Project contains unconfirmed FLP event format IDs: "
                        f"{sorted(unconfirmed_ids)}."
                    ),
                    details={"unconfirmed_event_ids": sorted(unconfirmed_ids)},
                )
            )

    # -------------------------------------------------------------------------
    # Composite Score & Categorization
    # -------------------------------------------------------------------------
    total_penalty = sum(f.score_penalty for f in factors)
    score = min(100, max(0, total_penalty))

    if score < 25:
        level: RiskLevel = "low"
    elif score < 50:
        level = "medium"
    elif score < 75:
        level = "high"
    else:
        level = "critical"

    has_critical = any(f.severity == "critical" for f in factors)
    is_safe = score < 50 and not has_critical

    if score == 0:
        summary = "Project is healthy with zero elevated risk factors detected."
    elif is_safe:
        summary = (
            f"Project has low/moderate risk score ({score}/100, level: {level}); "
            "safe to load in FL Studio."
        )
    else:
        summary = (
            f"Project has elevated risk score ({score}/100, level: {level}) with "
            f"{len(factors)} warning factor(s); exercise caution before opening."
        )

    return ProjectRiskReport(
        score=score,
        level=level,
        factors=factors,
        is_safe_to_load=is_safe,
        summary=summary,
    )
