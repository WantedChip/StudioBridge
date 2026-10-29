"""Unit tests for offline FLP MCP tools suite.

Verifies:
1. Tool definitions and schemas for flp_inspect, flp_edit, flp_diff, flp_validate,
   flp_save_as, flp_new_from_template (# req: T-MCP-06).
2. Schema snapshot validation against frozen JSON schemas (# req: MCP-01).
3. flp_inspect returns full structural project metadata with untrusted tags (# req: FLP-20, SEC-05).
4. flp_diff semantic comparison between projects (# req: FLP-20).
5. flp_validate structural invariant checks and static risk scoring (# req: FLP-50).
6. flp_save_as atomic save to new destination without corrupting input (# req: FLP-31).
7. flp_new_from_template instantiation producing openable projects (# req: FLP-40).
8. flp_edit applying validated mutations atomically (# req: FLP-30, FLP-31).
9. MCP path validation rejecting '..' traversal and unauthorized UNC paths (# req: MCP-SEC).
10. Tool dispatch via StudioMcpServer with toolset filtering (# req: MCP-11).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from studiobridge.core.errors import ArgumentError, SecurityError
from studiobridge.flp.model.project import Project
from studiobridge.flp.templates import get_seed_path
from studiobridge.mcp.schemas import get_schema, validate_schema
from studiobridge.mcp.server import StudioMcpServer
from studiobridge.mcp.tools.flp import FlpTools, get_flp_tools


@pytest.fixture
def minimal_flp(tmp_path: Path) -> Path:
    """Fixture providing an isolated copy of the minimal seed template."""
    src = get_seed_path("minimal")
    dest = tmp_path / "test_minimal.flp"
    shutil.copy2(src, dest)
    return dest


@pytest.fixture
def sampler_flp(tmp_path: Path) -> Path:
    """Fixture providing an isolated copy of the sampler seed template."""
    src = get_seed_path("sampler")
    dest = tmp_path / "test_sampler.flp"
    shutil.copy2(src, dest)
    return dest


class TestFlpToolsDefinitionsAndSchemas:
    """Verifies tool definitions, safety hints, and frozen JSON schemas for the FLP suite."""

    def test_tool_catalog(self) -> None:
        """All 6 tools are registered in the FLP toolset with correct annotations."""
        tools = get_flp_tools()
        names = {t.name for t in tools}
        expected = {
            "flp_inspect",
            "flp_edit",
            "flp_diff",
            "flp_validate",
            "flp_save_as",
            "flp_new_from_template",
        }
        assert names == expected

        tool_map = {t.name: t for t in tools}
        for name in expected:
            t = tool_map[name]
            assert t.toolset == "flp"
            schema = get_schema(name)
            assert schema["name"] == name
            assert "inputSchema" in schema
            assert "outputSchema" in schema
            assert t.input_schema == schema["inputSchema"]

        # Read-only hint assertions
        assert tool_map["flp_inspect"].read_only is True
        assert tool_map["flp_diff"].read_only is True
        assert tool_map["flp_validate"].read_only is True
        assert tool_map["flp_edit"].read_only is False
        assert tool_map["flp_save_as"].read_only is False
        assert tool_map["flp_new_from_template"].read_only is False

        # Destructive hint assertions (all False per safety design)
        for name in expected:
            assert tool_map[name].destructive is False


class TestFlpInspectTool:
    """Tests for flp_inspect tool."""

    def test_inspect_minimal_project(self, minimal_flp: Path) -> None:
        """Inspect returns complete structural metadata conforming to schema."""
        provider = FlpTools()
        res = provider.flp_inspect(file=str(minimal_flp))

        assert res.is_error is False
        data = res.structured_content
        assert isinstance(data, dict)

        schema = get_schema("flp_inspect")
        validate_schema(data, schema["outputSchema"])

        assert data["channel_count"] >= 0
        assert data["pattern_count"] >= 0
        assert data["tempo"] > 0
        assert data["ppq"] > 0
        assert "metadata" in data
        assert data["metadata"].get("untrusted") is True

    def test_inspect_project_with_channels(self, sampler_flp: Path) -> None:
        """Inspect on project with channels verifies channel metadata and untrusted tagging."""
        provider = FlpTools()
        res = provider.flp_inspect(file=str(sampler_flp))

        assert res.is_error is False
        data = res.structured_content
        assert data["channel_count"] == 1
        assert len(data["channels"]) == 1

        ch = data["channels"][0]
        assert ch["index"] == 0
        assert ch["name"] == "Sampler"
        assert ch.get("untrusted") is True

    def test_inspect_field_filtering(self, sampler_flp: Path) -> None:
        """Inspect respects fields parameter to selectively include sections."""
        provider = FlpTools()
        res = provider.flp_inspect(file=str(sampler_flp), fields=["metadata", "channels"])

        assert res.is_error is False
        data = res.structured_content
        assert len(data["channels"]) >= 1
        assert data["patterns"] == []

    def test_inspect_clamping(self, sampler_flp: Path) -> None:
        """Inspect clamps channel and pattern counts according to max_ channels/patterns."""
        provider = FlpTools()
        res = provider.flp_inspect(file=str(sampler_flp), max_channels=1, max_patterns=1)

        assert res.is_error is False
        data = res.structured_content
        assert len(data["channels"]) <= 1
        assert len(data["patterns"]) <= 1

    def test_inspect_missing_file(self, tmp_path: Path) -> None:
        """Inspect raises ArgumentError when file does not exist."""
        provider = FlpTools()
        missing = tmp_path / "nonexistent.flp"
        with pytest.raises(ArgumentError) as exc_info:
            provider.flp_inspect(file=str(missing))
        assert exc_info.value.code == "E_NOT_FOUND"


class TestFlpDiffTool:
    """Tests for flp_diff tool."""

    def test_diff_identical_projects(self, sampler_flp: Path) -> None:
        """Comparing identical project files returns has_differences=False."""
        provider = FlpTools()
        res = provider.flp_diff(file_a=str(sampler_flp), file_b=str(sampler_flp))

        assert res.is_error is False
        data = res.structured_content
        assert data["has_differences"] is False
        schema = get_schema("flp_diff")
        validate_schema(data, schema["outputSchema"])

    def test_diff_modified_project(self, sampler_flp: Path, tmp_path: Path) -> None:
        """Comparing modified project returns differences in tempo and metadata."""
        mod_flp = tmp_path / "modified.flp"
        proj = Project.load(sampler_flp)
        proj.mutate().set_tempo(140.0).set_title("Diff Test Project")
        proj.save_as(mod_flp)

        provider = FlpTools()
        res = provider.flp_diff(file_a=str(sampler_flp), file_b=str(mod_flp))

        assert res.is_error is False
        data = res.structured_content
        assert data["has_differences"] is True
        assert "tempo" in data["diff"]["metadata"]
        schema = get_schema("flp_diff")
        validate_schema(data, schema["outputSchema"])


class TestFlpValidateTool:
    """Tests for flp_validate tool."""

    def test_validate_valid_project(self, sampler_flp: Path) -> None:
        """Valid project passes invariant checks with static risk assessment."""
        provider = FlpTools()
        res = provider.flp_validate(file=str(sampler_flp))

        assert res.is_error is False
        data = res.structured_content
        assert data["is_valid"] is True
        assert data["is_safe_to_load"] is True
        assert data["invariants"] == []
        assert "risk" in data
        assert "score" in data["risk"]

        schema = get_schema("flp_validate")
        validate_schema(data, schema["outputSchema"])


class TestFlpSaveAsTool:
    """Tests for flp_save_as tool."""

    def test_save_as_creates_new_file(self, sampler_flp: Path, tmp_path: Path) -> None:
        """Save as writes project atomically to a new destination without modifying source."""
        provider = FlpTools()
        dest = tmp_path / "saved_copy.flp"

        orig_mtime = sampler_flp.stat().st_mtime
        res = provider.flp_save_as(source=str(sampler_flp), destination=str(dest))

        assert res.is_error is False
        data = res.structured_content
        assert dest.is_file()
        assert data["size_bytes"] > 0
        assert data["is_valid"] is True
        assert sampler_flp.stat().st_mtime == orig_mtime

        # Verify saved project is openable
        loaded = Project.load(dest)
        assert len(loaded.channels) == len(Project.load(sampler_flp).channels)

        schema = get_schema("flp_save_as")
        validate_schema(data, schema["outputSchema"])

    def test_save_as_rejects_identical_paths(self, sampler_flp: Path) -> None:
        """Save as rejects destination identical to source."""
        provider = FlpTools()
        with pytest.raises(ArgumentError):
            provider.flp_save_as(source=str(sampler_flp), destination=str(sampler_flp))


class TestFlpNewFromTemplateTool:
    """Tests for flp_new_from_template tool."""

    def test_new_minimal_template(self, tmp_path: Path) -> None:
        """Generates clean project file from minimal seed template."""
        provider = FlpTools()
        dest = tmp_path / "new_project.flp"

        res = provider.flp_new_from_template(
            destination=str(dest),
            template="minimal",
            title="My New Project",
            author="StudioBridge Agent",
            tempo=128.0,
            ppq=96,
        )

        assert res.is_error is False
        data = res.structured_content
        assert dest.is_file()
        assert data["template"] == "minimal"
        assert data["tempo"] == 128.0

        schema = get_schema("flp_new_from_template")
        validate_schema(data, schema["outputSchema"])

        # Verify created project loads cleanly with given parameters
        proj = Project.load(dest)
        assert proj.title == "My New Project"
        assert proj.author == "StudioBridge Agent"
        assert proj.tempo == 128.0
        assert proj.ppq == 96


class TestFlpEditTool:
    """Tests for flp_edit tool."""

    def test_edit_to_new_destination(self, sampler_flp: Path, tmp_path: Path) -> None:
        """Applies validated mutations and writes atomically to a new destination."""
        provider = FlpTools()
        dest = tmp_path / "edited_project.flp"

        mutations = [
            {"op": "set_tempo", "bpm": 135.0},
            {"op": "set_title", "title": "Edited Title"},
            {"op": "rename_channel", "channel": 0, "name": "Kick Drum"},
            {"op": "set_channel_volume", "channel": 0, "volume": 0.95},
            {"op": "add_marker", "name": "Verse 1", "pos": 384},
        ]

        res = provider.flp_edit(
            file=str(sampler_flp),
            destination=str(dest),
            mutations=mutations,
        )

        assert res.is_error is False
        data = res.structured_content
        assert data["mutations_applied"] == len(mutations)
        assert data["is_valid"] is True
        assert dest.is_file()

        schema = get_schema("flp_edit")
        validate_schema(data, schema["outputSchema"])

        # Verify mutations took effect in the saved file and were logged in records
        edited_proj = Project.load(dest)
        assert edited_proj.tempo == 135.0
        assert edited_proj.title == "Edited Title"
        assert edited_proj.channels[0].name == "Kick Drum"
        assert any(
            r["op"] == "channel.set_channel_volume" and r["after"] == 0.95 for r in data["records"]
        )
        assert any(
            r["op"] == "playlist.add_marker" and r["params"]["name"] == "Verse 1"
            for r in data["records"]
        )

    def test_edit_in_place_with_backup(self, sampler_flp: Path) -> None:
        """In-place edit creates timestamped backup copy and updates original."""
        provider = FlpTools()
        mutations = [{"op": "set_tempo", "bpm": 142.0}]

        res = provider.flp_edit(
            file=str(sampler_flp),
            in_place=True,
            mutations=mutations,
        )

        assert res.is_error is False
        assert Project.load(sampler_flp).tempo == 142.0

        # Verify a .bak backup file was created in the same directory
        parent = sampler_flp.parent
        backups = list(parent.glob(f"{sampler_flp.name}.bak-*"))
        assert len(backups) >= 1

    def test_edit_notes_mutation(self, sampler_flp: Path, tmp_path: Path) -> None:
        """Applies structured note array mutation to pattern."""
        provider = FlpTools()
        dest = tmp_path / "notes_edited.flp"

        notes = [
            {"pos": 0, "length": 96, "key": 60, "velocity": 0.8},
            {"pos": 96, "length": 96, "key": 64, "velocity": 0.8},
            {"pos": 192, "length": 96, "key": 67, "velocity": 0.8},
        ]

        res = provider.flp_edit(
            file=str(sampler_flp),
            destination=str(dest),
            mutations=[
                {
                    "op": "set_notes",
                    "pattern": 1,
                    "channel": 0,
                    "notes": notes,
                    "mode": "replace",
                }
            ],
        )

        assert res.is_error is False
        edited = Project.load(dest)
        pat = edited.pattern(1)
        pat_notes = pat.get_notes(0)
        assert len(pat_notes) == 3
        assert pat_notes[0].key == 60
        assert pat_notes[1].key == 64
        assert pat_notes[2].key == 67

    def test_edit_requires_destination_or_in_place(self, sampler_flp: Path) -> None:
        """Edit rejects mutation without destination when in_place=False."""
        provider = FlpTools()
        with pytest.raises(ArgumentError):
            provider.flp_edit(
                file=str(sampler_flp),
                mutations=[{"op": "set_tempo", "bpm": 130.0}],
                in_place=False,
            )

    def test_edit_unknown_mutation_operation(self, sampler_flp: Path, tmp_path: Path) -> None:
        """Edit raises ArgumentError on unrecognized mutation operation."""
        provider = FlpTools()
        dest = tmp_path / "bad.flp"
        with pytest.raises(ArgumentError) as exc_info:
            provider.flp_edit(
                file=str(sampler_flp),
                destination=str(dest),
                mutations=[{"op": "unsupported_unknown_op", "foo": "bar"}],
            )
        assert exc_info.value.code == "E_INVALID_MUTATION"


class TestFlpSecurityAndPathContainment:
    """Verifies path containment, traversal rejection, and UNC restrictions [MCP-SEC]."""

    def test_reject_directory_traversal(self) -> None:
        """Path traversal sequence '..' is forbidden."""
        provider = FlpTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file="../../windows/system32/cmd.exe")
        assert exc_info.value.code == "E_SECURITY"

    def test_reject_unauthorized_unc_path(self) -> None:
        """Unauthorized UNC network prefix is forbidden."""
        provider = FlpTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file=r"\\remote-server\share\exploit.flp")
        assert exc_info.value.code == "E_SECURITY"

    def test_reject_slash_unc_path(self) -> None:
        """Forward-slash UNC network prefix is forbidden."""
        provider = FlpTools()
        with pytest.raises(SecurityError) as exc_info:
            provider.flp_inspect(file="//remote-server/share/exploit.flp")
        assert exc_info.value.code == "E_SECURITY"


class TestFlpServerDispatch:
    """Verifies MCP server integration and toolset gating for the FLP suite."""

    def test_dispatch_when_flp_toolset_enabled(self, sampler_flp: Path) -> None:
        """Calling flp_inspect through StudioMcpServer succeeds when flp toolset is active."""
        server = StudioMcpServer(toolsets="core,flp")
        res = server.call_tool("flp_inspect", {"file": str(sampler_flp)})

        assert res.get("isError") is False
        assert "structuredContent" in res
        assert res["structuredContent"]["channel_count"] == 1

    def test_dispatch_when_flp_toolset_disabled(self, sampler_flp: Path) -> None:
        """Calling flp_inspect returns disabled toolset error when flp toolset is omitted."""
        server = StudioMcpServer(toolsets="core")
        res = server.call_tool("flp_inspect", {"file": str(sampler_flp)})

        assert res.get("isError") is True
        assert "disabled toolset" in res["content"][0]["text"]
