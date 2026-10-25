"""Headless render job supervisor, execution, and audio output validators.

Provides FL Studio headless render orchestration, process supervision under Windows
Job Objects, blocking dialog detection, job isolation staging, and collision policies
per spec 06_l0d_pianoroll_actuation_render.md §9-§13 and [RND-01] through [RND-04].
"""

from __future__ import annotations

from studiobridge.render.discover import FlDiscovery, FlInstall
from studiobridge.render.job import JobState, RenderJob, RenderJobLock
from studiobridge.render.policy import InstancePolicy, InstancePolicyEnforcer
from studiobridge.render.runner import RenderRunner, WindowsJobObject

__all__ = [
    "FlDiscovery",
    "FlInstall",
    "InstancePolicy",
    "InstancePolicyEnforcer",
    "JobState",
    "RenderJob",
    "RenderJobLock",
    "RenderRunner",
    "WindowsJobObject",
]
