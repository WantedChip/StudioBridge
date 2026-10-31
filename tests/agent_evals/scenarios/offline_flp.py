"""Offline FLP project evaluation scenarios exercising template instantiation, diffing, and editing.

Covers:
- Scenario 10: Offline project creation from template (# req: EVAL-10)
- Scenario 11: Offline FLP track inspection & diffing (# req: EVAL-11)
- Scenario 12: Offline FLP channel creation & mutation (# req: EVAL-12)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.agent_evals.harness import ScriptedAgentHarness, ToolCall
from tests.agent_evals.scenarios.registry import register_scenario


@register_scenario(
    id="eval-10-offline-project-creation",
    name="Offline project creation from template",
    description=(
        "Instantiate clean offline FLP project from seed template, "
        "inspect properties, and validate invariants."
    ),
    requirement_id="EVAL-10",
)
def run_scenario_offline_project_creation(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 10: Offline project creation from template (# req: EVAL-10)."""
    out_project = work_dir / "created_beat.flp"

    # Turn 1: Create fresh project from template 'minimal'
    res_new = harness.step(
        "Create fresh FL Studio project from 'minimal' template",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(out_project),
                    "title": "Agent Minimal Beat",
                    "author": "Antigravity",
                    "tempo": 126.0,
                },
            )
        ],
    )
    assert not res_new[0].is_error
    sc_new = res_new[0].structured_content
    assert out_project.exists()
    assert sc_new["template"] == "minimal"
    assert sc_new["tempo"] == 126.0

    # Turn 2: Validate structural invariants of created project
    res_val = harness.step(
        "Validate project invariants",
        [ToolCall(tool="flp_validate", arguments={"file": str(out_project)})],
    )
    sc_val = res_val[0].structured_content
    assert not res_val[0].is_error
    assert sc_val.get("is_valid") is True

    # Turn 3: Inspect project channels and tempo
    res_inspect = harness.step(
        "Inspect project channels and metadata",
        [ToolCall(tool="flp_inspect", arguments={"file": str(out_project)})],
    )
    sc_insp = res_inspect[0].structured_content
    assert not res_inspect[0].is_error
    assert sc_insp.get("metadata", {}).get("title") == "Agent Minimal Beat"
    assert sc_insp["tempo"] == pytest.approx(126.0, abs=0.1)
    assert "channels" in sc_insp


@register_scenario(
    id="eval-11-offline-flp-diff",
    name="Offline FLP track inspection & diffing",
    description="Inspect project structure across revisions and compute structured semantic delta.",
    requirement_id="EVAL-11",
)
def run_scenario_offline_flp_diff(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 11: Offline FLP track inspection & diffing (# req: EVAL-11)."""
    proj_a = work_dir / "revision_a.flp"
    proj_b = work_dir / "revision_b.flp"

    # Turn 1: Create base revision A
    res_a = harness.step(
        "Create revision A at 120 BPM",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(proj_a),
                    "title": "Track Rev A",
                    "tempo": 120.0,
                },
            )
        ],
    )
    assert not res_a[0].is_error

    # Turn 2: Create modified revision B
    res_b = harness.step(
        "Create revision B at 132 BPM",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(proj_b),
                    "title": "Track Rev B",
                    "tempo": 132.0,
                },
            )
        ],
    )
    assert not res_b[0].is_error

    # Turn 3: Perform semantic diff between revisions
    res_diff = harness.step(
        "Compute semantic diff between Revision A and Revision B",
        [
            ToolCall(
                tool="flp_diff",
                arguments={
                    "file_a": str(proj_a),
                    "file_b": str(proj_b),
                },
            )
        ],
    )
    sc_diff = res_diff[0].structured_content
    assert not res_diff[0].is_error
    assert "differences" in sc_diff or "changes" in sc_diff or "has_differences" in sc_diff


@register_scenario(
    id="eval-12-offline-flp-mutation",
    name="Offline FLP channel creation & mutation",
    description=(
        "Inspect channels, apply channel creation and parameter edits, "
        "and verify structural validity."
    ),
    requirement_id="EVAL-12",
)
def run_scenario_offline_flp_mutation(harness: ScriptedAgentHarness, work_dir: Path) -> None:
    """Scenario 12: Offline FLP channel creation & mutation (# req: EVAL-12)."""
    base_proj = work_dir / "mutate_base.flp"
    mutated_proj = work_dir / "mutate_output.flp"

    # Turn 1: Create base project
    harness.step(
        "Create base project for mutation testing",
        [
            ToolCall(
                tool="flp_new_from_template",
                arguments={
                    "template": "minimal",
                    "destination": str(base_proj),
                    "title": "Base For Mutations",
                    "tempo": 124.0,
                },
            )
        ],
    )

    # Turn 2: Inspect initial channel count
    res_initial = harness.step(
        "Inspect initial channels",
        [ToolCall(tool="flp_inspect", arguments={"file": str(base_proj)})],
    )
    initial_channels = len(res_initial[0].structured_content.get("channels", []))

    # Turn 3: Apply offline channel creation and parameter edits
    mutations = [
        {
            "op": "add_channel_from_template",
            "kind": "sampler",
            "name": "Sub Bass",
        },
        {
            "op": "set_title",
            "title": "Mutated Project With Sub Bass",
        },
    ]

    res_edit = harness.step(
        "Apply add_channel and set_title mutations to project",
        [
            ToolCall(
                tool="flp_edit",
                arguments={
                    "file": str(base_proj),
                    "destination": str(mutated_proj),
                    "mutations": mutations,
                },
            )
        ],
    )
    assert not res_edit[0].is_error
    assert mutated_proj.exists()

    # Turn 4: Validate mutated project passes all invariants
    res_val = harness.step(
        "Validate mutated project invariants",
        [ToolCall(tool="flp_validate", arguments={"file": str(mutated_proj)})],
    )
    assert not res_val[0].is_error
    assert res_val[0].structured_content.get("is_valid") is True

    # Turn 5: Inspect mutated project channels and title
    res_post = harness.step(
        "Inspect mutated project to verify new channel and title",
        [ToolCall(tool="flp_inspect", arguments={"file": str(mutated_proj)})],
    )
    sc_post = res_post[0].structured_content
    assert not res_post[0].is_error
    assert len(sc_post.get("channels", [])) == initial_channels + 1
    assert sc_post.get("metadata", {}).get("title") == "Mutated Project With Sub Bass"
