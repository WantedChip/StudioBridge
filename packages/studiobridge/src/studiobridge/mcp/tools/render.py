"""Headless render orchestration and audio analysis MCP tools for StudioBridge.

Implements render tools [RND-01..05]:
- render_start: Asynchronous headless render launch with path containment and MCP task handles.
- render_status: Poll active job progress, output audio artifacts, and sidecar metrics.
- render_cancel: Clean subprocess termination and job cancellation.
- render_analyze: Pure-Python audio metric validation and quality analysis.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from studiobridge.core.config import StudioBridgeConfig, load_config
from studiobridge.core.errors import ArgumentError, BadRefError
from studiobridge.core.paths import get_jobs_dir, validate_safe_path
from studiobridge.mcp.schemas import get_schema
from studiobridge.mcp.server import ToolDefinition, ToolResult
from studiobridge.render.job import JobState, RenderJob
from studiobridge.render.runner import RenderRunner, WindowsJobObject
from studiobridge.render.sidecar import read_sidecar
from studiobridge.render.validate import AudioValidator, ValidationSpec

# Active job tracking registry across MCP tool invocations
_ACTIVE_JOBS: dict[str, RenderJob] = {}
_ACTIVE_RUNNERS: dict[str, RenderRunner] = {}
_ACTIVE_THREADS: dict[str, threading.Thread] = {}
_REGISTRY_LOCK: threading.Lock = threading.Lock()


def _get_negotiated_version(server: Any = None) -> str | None:
    """Retrieve client protocol version if available."""
    if server is not None and hasattr(server, "host"):
        return getattr(server.host, "negotiated_version", None)
    return None


def _persist_job(job: RenderJob) -> None:
    """Write job metadata dictionary to jobs/<id>/job.json."""
    try:
        job_dir = get_jobs_dir() / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        job_file = job_dir / "job.json"
        job_file.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
    except Exception:
        pass


def _lookup_job(job_id: str) -> dict[str, Any] | None:
    """Retrieve job metadata from active memory or disk persistence."""
    with _REGISTRY_LOCK:
        active = _ACTIVE_JOBS.get(job_id)
        if active is not None:
            return active.to_dict()

    job_file = get_jobs_dir() / job_id / "job.json"
    if job_file.is_file():
        try:
            data = json.loads(job_file.read_text(encoding="utf-8"))
            # Enrich with sidecar if present and missing from data
            sidecar_path = data.get("sidecar_path")
            if not sidecar_path:
                out_dir = data.get("out_dir")
                if out_dir:
                    p_out = Path(out_dir)
                    if p_out.exists():
                        for item in p_out.glob("*.render.json"):
                            data["sidecar_path"] = str(item)
                            try:
                                sc = read_sidecar(item)
                                if "metrics" in sc:
                                    data.setdefault("metrics", {}).update(sc["metrics"])
                            except Exception:
                                pass
                            break
            return data
        except Exception:
            pass

    return None


class RenderTools:
    """Provider for headless render orchestration and audio metric analysis MCP tools."""

    def __init__(
        self,
        client: Any = None,
        server: Any = None,
        config: StudioBridgeConfig | None = None,
        runner: RenderRunner | None = None,
        validator: AudioValidator | None = None,
    ) -> None:
        self.client = client
        self.server = server
        self.config = config or load_config()
        self.runner = runner or RenderRunner(config=self.config)
        self.validator = validator or AudioValidator()

    def render_start(
        self,
        source: str | Path,
        formats: Sequence[str] | str | None = None,
        out_dir: str | Path | None = None,
        instance_policy: str = "require_closed",
        timeout_s: float = 900.0,
        idle_timeout_s: float = 120.0,
        min_duration_s: float = 0.5,
        max_silence_ratio: float = 0.98,
        wait: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Initiate background headless render job with path security containment.

        # req: RND-01, RND-02, MCP-20, MCP-SEC
        """
        # 1. Enforce path containment on project source and output directory
        safe_source = validate_safe_path(source)
        safe_out_dir: Path | None = None
        if out_dir is not None:
            safe_out_dir = validate_safe_path(out_dir)

        if not safe_source.exists() or not safe_source.is_file():
            raise ArgumentError(
                f"Source FL Studio project file not found: '{safe_source}'", code="E_ARGS"
            )

        # 2. Normalize export format list
        norm_formats: list[str] = []
        if formats is None:
            norm_formats = ["wav"]
        elif isinstance(formats, str):
            norm_formats = [f.strip().lower() for f in formats.split(",") if f.strip()]
        else:
            norm_formats = [str(f).strip().lower() for f in formats if str(f).strip()]

        if not norm_formats:
            norm_formats = ["wav"]

        # 3. Create RenderJob specification
        val_spec = ValidationSpec(
            min_duration_s=min_duration_s,
            max_silence_ratio=max_silence_ratio,
        )

        job = RenderJob(
            source=safe_source,
            formats=norm_formats,
            out_dir=safe_out_dir,
            instance_policy=instance_policy or "require_closed",
            timeout_s=float(timeout_s),
            idle_timeout_s=float(idle_timeout_s),
            validate=val_spec,
        )

        with _REGISTRY_LOCK:
            _ACTIVE_JOBS[job.job_id] = job
            _ACTIVE_RUNNERS[job.job_id] = self.runner

        _persist_job(job)

        # 4. Spawn background supervisor thread
        runner_instance = self.runner

        def _worker() -> None:
            try:
                runner_instance.run(job)
            except Exception as exc:
                job.state = JobState.FAILED
                if not job.error:
                    job.error = str(exc)
            finally:
                _persist_job(job)

        thread = threading.Thread(target=_worker, name=f"sbridge-render-{job.job_id}", daemon=True)
        with _REGISTRY_LOCK:
            _ACTIVE_THREADS[job.job_id] = thread
        thread.start()

        if wait:
            thread.join(timeout=timeout_s)

        # 5. Build structured receipt and task handle if client negotiated Tasks extension
        task_handle = {
            "id": job.job_id,
            "status": "running"
            if job.state not in (JobState.DONE, JobState.FAILED, JobState.CANCELLED)
            else job.state.value,
            "poll_interval": 1.0,
        }

        receipt: dict[str, Any] = {
            "job_id": job.job_id,
            "state": job.state.value,
            "source": str(job.source),
            "formats": job.formats,
            "out_dir": str(job.out_dir) if job.out_dir else None,
            "created_at": job.created_at,
            "task_handle": task_handle,
        }

        human_text = (
            f"Render job '{job.job_id}' initiated for '{job.source.name}' "
            f"formats=[{', '.join(job.formats)}] (state: {job.state.value})."
        )

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=False,
        )

    def render_status(
        self,
        job_id: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Poll active render job progress, output file paths, and metrics.

        # req: RND-01, MCP-20
        """
        data = _lookup_job(job_id)
        if data is None:
            raise BadRefError(
                f"Render job '{job_id}' not found.",
                code="E_BADREF",
                remedy="Check job ID or start a new render job via 'render_start'.",
            )

        receipt: dict[str, Any] = {
            "job_id": data["job_id"],
            "state": data.get("state", "unknown"),
            "source": data.get("source", ""),
            "formats": data.get("formats", ["wav"]),
            "output_files": data.get("output_files", []),
            "sidecar_path": data.get("sidecar_path"),
            "error": data.get("error"),
            "error_code": data.get("error_code"),
            "exit_code": data.get("exit_code"),
            "metrics": data.get("metrics", {}),
            "created_at": data.get("created_at", 0.0),
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
        }

        state_str = receipt["state"]
        out_count = len(receipt["output_files"])
        human_text = f"Render job '{job_id}' status: {state_str} ({out_count} artifact(s))."
        if receipt.get("error"):
            human_text += f" Error: {receipt['error']}"

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=(state_str == "failed"),
        )

    def render_cancel(
        self,
        job_id: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Terminate active render subprocess and supervisor cleanly.

        # req: RND-03, MCP-20
        """
        with _REGISTRY_LOCK:
            job = _ACTIVE_JOBS.get(job_id)
            runner = _ACTIVE_RUNNERS.get(job_id)

        if job is None:
            # Check persisted disk data
            persisted = _lookup_job(job_id)
            if persisted is None:
                raise BadRefError(
                    f"Render job '{job_id}' not found.",
                    code="E_BADREF",
                    remedy="Provide an active render job ID.",
                )
            if persisted.get("state") in ("done", "failed", "cancelled"):
                return ToolResult(
                    content=[
                        {
                            "type": "text",
                            "text": f"Render job '{job_id}' is already {persisted.get('state')}.",
                        }
                    ],
                    structured_content={
                        "job_id": job_id,
                        "status": persisted.get("state"),
                        "message": f"Render job '{job_id}' already terminated.",
                    },
                    is_error=False,
                )

        if job is not None:
            # Terminate active process if alive
            if job.pid and runner:
                job_obj = getattr(runner, "_job_obj", None)
                if isinstance(job_obj, WindowsJobObject):
                    with contextlib.suppress(Exception):
                        runner._terminate_process_tree(job, job_obj)

            job.state = JobState.CANCELLED
            job.completed_at = time.time()
            _persist_job(job)

        receipt: dict[str, Any] = {
            "job_id": job_id,
            "status": "cancelled",
            "message": f"Render job '{job_id}' cancelled cleanly.",
        }

        return ToolResult(
            content=[{"type": "text", "text": receipt["message"]}],
            structured_content=receipt,
            is_error=False,
        )

    def render_analyze(
        self,
        path: str | Path,
        min_duration_s: float = 0.5,
        max_silence_ratio: float = 0.98,
        allow_clipping: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Run acoustic signal validation metrics and quality checks on an audio file.

        # req: RND-05
        """
        safe_path = validate_safe_path(path)
        if not safe_path.exists() or not safe_path.is_file():
            raise ArgumentError(f"Audio file not found: '{safe_path}'", code="E_ARGS")

        spec = ValidationSpec(
            min_duration_s=min_duration_s,
            max_silence_ratio=max_silence_ratio,
            allow_clipping=allow_clipping,
        )

        res = self.validator.validate_file(safe_path, spec=spec)

        receipt: dict[str, Any] = {
            "path": str(safe_path),
            "is_valid": res.is_valid,
            "validation_status": "passed" if res.is_valid else "failed",
            "error_message": res.error_message,
            "metrics": res.metrics.to_dict(),
        }

        status_str = "PASSED" if res.is_valid else "FAILED"
        human_text = (
            f"Audio analysis for '{safe_path.name}': {status_str} "
            f"({res.metrics.duration_s:.2f}s, {res.metrics.channels}ch, "
            f"peak: {res.metrics.peak_dbfs:.1f} dBFS, RMS: {res.metrics.rms_dbfs:.1f} dBFS)."
        )
        if res.error_message:
            human_text += f" Issue: {res.error_message}"

        return ToolResult(
            content=[{"type": "text", "text": human_text}],
            structured_content=receipt,
            is_error=(not res.is_valid),
        )


def get_render_tools(client: Any = None, server: Any = None) -> list[ToolDefinition]:
    """Return ToolDefinition list for render orchestration MCP tool suite."""
    provider = RenderTools(client=client, server=server)

    s_start = get_schema("render_start")
    s_status = get_schema("render_status")
    s_cancel = get_schema("render_cancel")
    s_analyze = get_schema("render_analyze")

    return [
        ToolDefinition(
            name="render_start",
            title=s_start.get("title", "Render Start"),
            description=s_start.get(
                "description",
                "Initiate a background headless FL Studio project render job.",
            ),
            input_schema=s_start.get("inputSchema", {}),
            toolset="render",
            read_only=False,
            destructive=False,
            idempotent=False,
            open_world=False,
            handler=provider.render_start,
        ),
        ToolDefinition(
            name="render_status",
            title=s_status.get("title", "Render Status"),
            description=s_status.get(
                "description",
                "Poll progress, completion state, output file paths, and metrics for a render job.",
            ),
            input_schema=s_status.get("inputSchema", {}),
            toolset="render",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.render_status,
        ),
        ToolDefinition(
            name="render_cancel",
            title=s_cancel.get("title", "Render Cancel"),
            description=s_cancel.get(
                "description",
                "Terminate an active headless render subprocess and supervisor cleanly.",
            ),
            input_schema=s_cancel.get("inputSchema", {}),
            toolset="render",
            read_only=False,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.render_cancel,
        ),
        ToolDefinition(
            name="render_analyze",
            title=s_analyze.get("title", "Render Analyze"),
            description=s_analyze.get(
                "description",
                (
                    "Run acoustic signal validation metrics and quality checks on a "
                    "rendered audio file."
                ),
            ),
            input_schema=s_analyze.get("inputSchema", {}),
            toolset="render",
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
            handler=provider.render_analyze,
        ),
    ]


__all__ = [
    "RenderTools",
    "get_render_tools",
    "_lookup_job",
]
