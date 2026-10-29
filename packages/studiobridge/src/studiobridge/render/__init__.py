"""Headless render job supervisor, execution, and audio output validators.

Provides FL Studio headless render orchestration, process supervision under Windows
Job Objects, blocking dialog detection, job isolation staging, and collision policies [RND-01..05].
"""

from __future__ import annotations

from studiobridge.render.discover import FlDiscovery, FlInstall
from studiobridge.render.job import JobState, RenderJob, RenderJobLock
from studiobridge.render.policy import InstancePolicy, InstancePolicyEnforcer
from studiobridge.render.runner import RenderRunner, WindowsJobObject
from studiobridge.render.sidecar import (
    SidecarMetadata,
    build_sidecar_dict,
    read_sidecar,
    write_sidecar,
)
from studiobridge.render.validate import (
    AudioMetrics,
    AudioValidationResult,
    AudioValidator,
    ValidationSpec,
)

__all__ = [
    "AudioMetrics",
    "AudioValidationResult",
    "AudioValidator",
    "FlDiscovery",
    "FlInstall",
    "InstancePolicy",
    "InstancePolicyEnforcer",
    "JobState",
    "RenderJob",
    "RenderJobLock",
    "RenderRunner",
    "SidecarMetadata",
    "ValidationSpec",
    "WindowsJobObject",
    "build_sidecar_dict",
    "read_sidecar",
    "write_sidecar",
]
