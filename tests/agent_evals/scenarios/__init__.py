"""Modular scripted agent evaluation scenarios library.

Registers all realistic multi-turn agent evaluation scenarios covering mixer control,
transport lifecycles, piano roll sequencing, offline project creation and manipulation,
headless rendering, safety interlocks, and security defenses.
"""

from __future__ import annotations

# Import scenario modules in sequential requirement order
from tests.agent_evals.scenarios import (
    mixer,
    offline_flp,
    render,
    safety,
    sequencing,
    system,
    transport,
)
from tests.agent_evals.scenarios.registry import (
    ScenarioDefinition,
    ScenarioRegistry,
    register_scenario,
)

__all__ = [
    "ScenarioDefinition",
    "ScenarioRegistry",
    "mixer",
    "offline_flp",
    "register_scenario",
    "render",
    "safety",
    "sequencing",
    "system",
    "transport",
]
