"""Unit tests for headless render MCP tools and resource streaming.

Verifies:
1. Tool definitions and schemas for render_start, render_status, render_cancel, render_analyze.
2. Render start, asynchronous launch, and polling status (# req: RND-01, RND-02, MCP-20).
3. Path containment verification rejecting '..' traversal and UNC paths (# req: MCP-SEC).
4. Subprocess lifecycle cancellation (# req: RND-03).
5. Audio validation analysis via render_analyze (# req: RND-05).
6. Resource streaming via studio://render/{job_id} (# req: RND-05, MCP-RES).
7. MCP Tasks extension handling (tasks/get, tasks/cancel, tasks/list).
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from studiobridge.core.errors import SecurityError
from studiobridge.core.paths import get_jobs_dir
from studiobridge.mcp.host import McpHost
from studiobridge.mcp.resources import ResourceProvider
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.tools.render import RenderTools, get_render_tools
from studiobridge.render.job import JobState, RenderJob
from studiobridge.render.runner import RenderRunner


def _create_synthetic_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 44100) -> Path:
    """Generate a clean synthetic sine wave PCM 16-bit WAV file for testing."""
    n_samples = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(16384 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return path


class MockRenderRunner(RenderRunner):
    """Mock runner simulating headless export for test environments."""

    def __init__(self, output_wav: Path | None = None) -> None:
        self.output_wav = output_wav

    def run(self, job: RenderJob) -> RenderJob:
        job.state = JobState.RENDERING
        out_dir = job.out_dir or (get_jobs_dir() / job.job_id / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        job.out_dir = out_dir

        if self.output_wav and self.output_wav.exists():
            dest = out_dir / f"{job.source.stem}.wav"
            dest.write_bytes(self.output_wav.read_bytes())
            job.output_files = [dest]

        job.state = JobState.DONE
        job.metrics = {
            "duration_s": 1.0,
            "peak_dbfs": -6.0,
            "rms_dbfs": -9.0,
            "silence_ratio": 0.0,
        }
        return job


def test_render_tool_definitions() -> None:
    """Verify tool definitions and schemas for render tool suite (# req: RND-01)."""
    tools = get_render_tools()
    names = {t.name for t in tools}
    assert names == {"render_start", "render_status", "render_cancel", "render_analyze"}

    for t in tools:
        assert t.toolset == "render"
        schema = get_schema(t.name)
        assert schema is not None
        assert "inputSchema" in schema
        assert "outputSchema" in schema


def test_render_start_and_status(tmp_path: Path) -> None:
    """Verify render_start launches job and render_status polls state (# req: RND-01, MCP-20)."""
    flp_file = tmp_path / "song.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    synth_wav = _create_synthetic_wav(tmp_path / "reference.wav")
    mock_runner = MockRenderRunner(output_wav=synth_wav)
    tools = RenderTools(runner=mock_runner)

    start_res = tools.render_start(
        source=flp_file,
        formats=["wav"],
        wait=True,
    )

    assert start_res.is_error is False
    start_data = start_res.structured_content
    job_id = start_data["job_id"]
    assert job_id.startswith("rnd-")
    assert "task_handle" in start_data

    # Poll status
    status_res = tools.render_status(job_id=job_id)
    assert status_res.is_error is False
    status_data = status_res.structured_content
    assert status_data["job_id"] == job_id
    assert status_data["state"] == "done"
    assert len(status_data["output_files"]) == 1
    assert "metrics" in status_data
    assert status_data["metrics"]["duration_s"] == 1.0


def test_render_path_traversal_rejection(tmp_path: Path) -> None:
    """Verify render tools reject path traversal and unauthorized UNC paths (# req: MCP-SEC)."""
    tools = RenderTools()
    flp_file = tmp_path / "song.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    # Traversal '..'
    with pytest.raises(SecurityError):
        tools.render_start(source="../secret.flp")

    with pytest.raises(SecurityError):
        tools.render_start(source=flp_file, out_dir="out/../../forbidden")

    with pytest.raises(SecurityError):
        tools.render_analyze(path="..\\system.wav")

    # Unauthorized UNC paths
    with pytest.raises(SecurityError):
        tools.render_start(source="\\\\network-share\\projects\\song.flp")

    with pytest.raises(SecurityError):
        tools.render_analyze(path="//remote-host/share/audio.wav")


def test_render_cancel(tmp_path: Path) -> None:
    """Verify render_cancel cleanly terminates an active render job (# req: RND-03)."""
    flp_file = tmp_path / "heavy_project.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    class BlockingRunner(RenderRunner):
        def run(self, job: RenderJob) -> RenderJob:
            job.state = JobState.RENDERING
            job.pid = 99999
            return job

    tools = RenderTools(runner=BlockingRunner())
    start_res = tools.render_start(source=flp_file, wait=False)
    job_id = start_res.structured_content["job_id"]

    cancel_res = tools.render_cancel(job_id=job_id)
    assert cancel_res.is_error is False
    assert cancel_res.structured_content["status"] == "cancelled"

    status_res = tools.render_status(job_id=job_id)
    assert status_res.structured_content["state"] == "cancelled"


def test_render_analyze(tmp_path: Path) -> None:
    """Verify render_analyze runs audio validation metrics on audio files (# req: RND-05)."""
    wav_file = _create_synthetic_wav(tmp_path / "valid.wav", duration_s=1.5)
    tools = RenderTools()

    res = tools.render_analyze(path=wav_file, min_duration_s=0.5, max_silence_ratio=0.98)
    assert res.is_error is False
    data = res.structured_content
    assert data["is_valid"] is True
    assert data["validation_status"] == "passed"
    assert data["metrics"]["duration_s"] >= 1.4
    assert data["metrics"]["channels"] == 1


def test_render_resource_streaming(tmp_path: Path) -> None:
    """Verify MCP resource studio://render/{job_id} streams metrics (# req: RND-05, MCP-RES)."""
    flp_file = tmp_path / "stream_project.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    synth_wav = _create_synthetic_wav(tmp_path / "stream_out.wav")
    mock_runner = MockRenderRunner(output_wav=synth_wav)
    tools = RenderTools(runner=mock_runner)

    start_res = tools.render_start(source=flp_file, wait=True)
    job_id = start_res.structured_content["job_id"]

    # Read resource via ResourceProvider
    provider = ResourceProvider()
    content = provider.read_resource(f"studio://render/{job_id}")

    assert content.uri == f"studio://render/{job_id}"
    assert content.mime_type == "application/json"
    assert content.text is not None

    data = json.loads(content.text)
    assert data["job_id"] == job_id
    assert data["state"] == "done"
    assert len(data["output_files"]) == 1
    assert data["metrics"]["duration_s"] == 1.0


def test_render_resource_unknown_job_raises() -> None:
    """Verify studio://render/{job_id} raises ValueError for non-existent job ID."""
    provider = ResourceProvider()
    with pytest.raises(ValueError, match="not found"):
        provider.read_resource("studio://render/rnd-nonexistent-123456")


def test_render_tasks_extension(tmp_path: Path) -> None:
    """Verify MCP host routes tasks/get, tasks/cancel, and tasks/list (# req: MCP-20)."""
    flp_file = tmp_path / "task_project.flp"
    flp_file.write_bytes(b"FLhd\x06\x00\x00\x00")

    synth_wav = _create_synthetic_wav(tmp_path / "task_out.wav")
    tools = RenderTools(runner=MockRenderRunner(output_wav=synth_wav))

    start_res = tools.render_start(source=flp_file, wait=True)
    job_id = start_res.structured_content["job_id"]

    host = McpHost()
    host.negotiated_version = "2026-07-28"
    host.is_initialized = True

    # 1. tasks/get
    get_req = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tasks/get",
        "params": {"taskId": job_id},
    }
    get_res = host.handle_request(get_req)
    assert get_res is not None
    assert "result" in get_res
    task_info = get_res["result"]["task"]
    assert task_info["id"] == job_id
    assert task_info["status"] == "completed"
    assert task_info["state"] == "done"

    # 2. tasks/list
    list_req = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tasks/list",
        "params": {},
    }
    list_res = host.handle_request(list_req)
    assert list_res is not None
    assert "result" in list_res
    assert isinstance(list_res["result"]["tasks"], list)

    # 3. tasks/cancel
    cancel_req = {
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tasks/cancel",
        "params": {"taskId": job_id},
    }
    cancel_res = host.handle_request(cancel_req)
    assert cancel_res is not None
    assert "result" in cancel_res
    assert cancel_res["result"]["task"]["status"] == "cancelled"
