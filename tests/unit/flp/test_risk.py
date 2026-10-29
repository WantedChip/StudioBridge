"""Unit test suite for FLP static project health and risk scoring.

Tests risk assessment criteria [FLP-40]:
- Clean stock projects have low/zero risk
- Unknown FL versions elevate risk
- Modified opaque blobs elevate risk
- Template version mismatches elevate risk
- Size and event format anomalies elevate risk
# req: FLP-40, FLP-50
"""

from __future__ import annotations

from studiobridge.flp.codec.events import Event
from studiobridge.flp.model.elements import Channel, OpaquePlugin
from studiobridge.flp.model.project import Project
from studiobridge.flp.templates.instantiator import (
    FragmentProvenance,
    instantiate_project,
)
from studiobridge.flp.validate.risk import (
    ProjectRiskReport,
    calculate_project_risk,
)


def _build_minimal_project() -> Project:
    """Helper to instantiate a clean baseline minimal project."""
    return instantiate_project("minimal")


def test_clean_seed_project_has_zero_risk() -> None:
    """Clean seed projects should have score 0, low risk level, and be safe to load.

    # req: FLP-50
    """
    project = _build_minimal_project()
    report = calculate_project_risk(project)

    assert isinstance(report, ProjectRiskReport)
    assert report.score == 0
    assert report.level == "low"
    assert report.is_safe_to_load is True
    assert len(report.factors) == 0
    assert "healthy" in report.summary.lower()


def test_unknown_fl_version_elevates_risk() -> None:
    """Projects declaring unknown or unprofiled future FL versions must be flagged.

    # req: FLP-50
    """
    project = _build_minimal_project()
    # Simulate future unsupported FL Studio version
    project.version = "28.5.1.9999"

    report = calculate_project_risk(project)
    assert report.score >= 25
    assert any(f.category == "unknown_version" for f in report.factors)
    factor = next(f for f in report.factors if f.category == "unknown_version")
    assert "exceeds" in factor.message or "28" in factor.message


def test_missing_version_profile_elevates_risk() -> None:
    """Projects with no resolved profile must trigger a critical risk factor.

    # req: FLP-50
    """
    project = _build_minimal_project()
    project.profile = None  # type: ignore

    report = calculate_project_risk(project)
    assert report.score >= 40
    assert any(f.category == "unknown_version" for f in report.factors)
    assert report.is_safe_to_load is False


def test_modified_opaque_blob_elevates_risk() -> None:
    """Modified or synthesized opaque plugin wrapper blobs must trigger elevated risk.

    # req: FLP-40, FLP-50
    """
    project = _build_minimal_project()
    # Add a channel with a modified opaque plugin
    opaque = OpaquePlugin(data=b"\x01\x02\x03\x04", is_modified=True, name_hint="ModifiedPlugin")
    ch = Channel(
        index=len(project.channels),
        name="CustomSynth",
        channel_type="plugin",
        plugin=opaque,
    )
    project.channels.append(ch)

    report = calculate_project_risk(project)
    assert report.score >= 40
    assert any(f.category == "modified_opaque_blob" for f in report.factors)
    factor = next(f for f in report.factors if f.category == "modified_opaque_blob")
    assert "modified opaque plugin" in factor.message.lower()


def test_synthesized_opaque_blob_elevates_risk() -> None:
    """Procedurally synthesized opaque plugin data without host provenance must be flagged.

    # req: FLP-40, FLP-50
    """
    project = _build_minimal_project()
    opaque = OpaquePlugin(data=b"fake_synthesized_blob", is_synthesized=True)
    ch = Channel(
        index=len(project.channels),
        name="Synthesized",
        channel_type="plugin",
        plugin=opaque,
    )
    project.channels.append(ch)

    report = calculate_project_risk(project)
    assert report.score >= 40
    assert any(f.category == "modified_opaque_blob" for f in report.factors)


def test_template_version_mismatch_elevates_risk() -> None:
    """Fragments originating from a different FL minor version must be flagged.

    # req: FLP-40, FLP-50
    """
    project = _build_minimal_project()
    project.version = "26.1.3.5570"

    # Channel from FL 21 fragment
    prov = FragmentProvenance(
        fl_version="21.0.3",
        author="TestAuthor",
        date="2024-01-01T00:00:00Z",
    )
    ch = Channel(
        index=len(project.channels),
        name="LegacyChannel",
        channel_type="sampler",
        provenance=prov,
    )
    project.channels.append(ch)

    report = calculate_project_risk(project)
    assert report.score >= 25
    assert any(f.category == "template_mismatch" for f in report.factors)
    factor = next(f for f in report.factors if f.category == "template_mismatch")
    assert "different fl studio minor version" in factor.message.lower()


def test_header_channel_count_discrepancy_elevates_risk() -> None:
    """Header channel count disagreement with actual channel count is flagged as size anomaly.

    # req: FLP-05, FLP-50
    """
    project = _build_minimal_project()
    assert project.source_file is not None and project.source_file.header is not None
    # Intentionally corrupt header channel declaration
    project.source_file.header.channels = 99

    report = calculate_project_risk(project)
    assert report.score >= 35
    assert any(f.category == "size_anomaly" for f in report.factors)
    factor = next(f for f in report.factors if f.category == "size_anomaly")
    assert "disagrees with actual channel count" in factor.message.lower()


def test_unconfirmed_event_ids_elevate_risk() -> None:
    """Unconfirmed or unknown event format IDs must be flagged with elevated risk.

    # req: FLP-50
    """
    project = _build_minimal_project()
    assert project.source_file is not None
    # Inject unknown/unconfirmed event ID 250
    project.source_file.events.append(Event(id=250, raw=b"\x00\x01\x02"))

    report = calculate_project_risk(project)
    assert report.score >= 25
    assert any(f.category == "unconfirmed_event" for f in report.factors)
    factor = next(f for f in report.factors if f.category == "unconfirmed_event")
    assert "250" in factor.message


def test_project_validate_returns_comprehensive_report() -> None:
    """Project.validate() returns a typed ValidationReport supporting inspection and iteration.

    # req: FLP-50
    """
    project = _build_minimal_project()
    report = project.validate()

    assert report.is_valid is True
    assert report.is_safe_to_load is True
    assert len(report.invariants) == 0
    assert report.risk.score == 0

    # Iteration behaves like list of invariant violations
    violations_list = list(report)
    assert violations_list == []
    assert bool(report) is True

    # Dictionary conversion
    report_dict = report.to_dict()
    assert report_dict["is_valid"] is True
    assert report_dict["risk"]["level"] == "low"
