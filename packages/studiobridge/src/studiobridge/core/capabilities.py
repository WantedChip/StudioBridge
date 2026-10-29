"""StudioBridge capability status model, prerequisite resolution, and registry.

Implements the capability data model:
Capability { id, state, reason, requires[], alternatives[], evidence[] }
state in {available, degraded, unavailable, unknown}
and enforcement rule [CAP-02]: operations that would fail MUST fail early with E_UNAVAILABLE.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from studiobridge.core.errors import UnavailableError


class CapabilityState(str, Enum):
    """Lifecycle and operational state of a capability."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Capability:
    """Represents a feature capability with prerequisites and alternative paths."""

    id: str
    state: CapabilityState = CapabilityState.UNKNOWN
    name: str | None = None
    reason: str | None = None
    requires: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    is_experimental: bool = False

    @property
    def is_available(self) -> bool:
        """Whether capability is fully operational."""
        return self.state == CapabilityState.AVAILABLE

    @property
    def is_degraded(self) -> bool:
        """Whether capability is operating in a degraded mode."""
        return self.state == CapabilityState.DEGRADED

    @property
    def is_unavailable(self) -> bool:
        """Whether capability is offline or prerequisite unsatisfied."""
        return self.state == CapabilityState.UNAVAILABLE

    def to_dict(self) -> dict[str, Any]:
        """Serialize capability to a dictionary."""
        return {
            "id": self.id,
            "state": self.state.value
            if isinstance(self.state, CapabilityState)
            else str(self.state),
            "name": self.name,
            "reason": self.reason,
            "requires": list(self.requires),
            "alternatives": list(self.alternatives),
            "evidence": list(self.evidence),
            "is_experimental": self.is_experimental,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Capability:
        """Construct Capability from dictionary representation."""
        raw_state = data.get("state", "unknown")
        try:
            state = CapabilityState(raw_state)
        except ValueError:
            state = CapabilityState.UNKNOWN

        return cls(
            id=data["id"],
            state=state,
            name=data.get("name"),
            reason=data.get("reason"),
            requires=list(data.get("requires", [])),
            alternatives=list(data.get("alternatives", [])),
            evidence=list(data.get("evidence", [])),
            is_experimental=bool(data.get("is_experimental", False)),
        )


class CapabilityRegistry:
    """Registry maintaining capability states, prerequisite evaluation, and status reporting."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register a capability into the registry."""
        self._capabilities[capability.id] = capability

    def register_all(self, capabilities: Iterable[Capability]) -> None:
        """Register multiple capabilities."""
        for cap in capabilities:
            self.register(cap)

    def get(self, cap_id: str) -> Capability | None:
        """Retrieve capability by ID without prerequisite evaluation."""
        return self._capabilities.get(cap_id)

    def __getitem__(self, cap_id: str) -> Capability:
        """Evaluate and return effective capability by ID, supporting fl.caps[id]."""
        if cap_id not in self._capabilities:
            raise KeyError(f"Capability '{cap_id}' is not registered.")
        return self.evaluate(cap_id)

    def __contains__(self, cap_id: object) -> bool:
        """Check if capability ID is registered."""
        return cap_id in self._capabilities

    def __iter__(self):
        """Iterate over registered capability IDs."""
        return iter(self._capabilities)

    def __len__(self) -> int:
        """Return total count of registered capabilities."""
        return len(self._capabilities)

    def set_state(
        self,
        cap_id: str,
        state: CapabilityState | str,
        reason: str | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        """Update the state and metadata of a registered capability."""
        self.update(cap_id, state=state, reason=reason, evidence=evidence)

    def update(
        self,
        cap_id: str,
        state: CapabilityState | str,
        reason: str | None = None,
        alternatives: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        """Update or insert a capability with given state and metadata."""
        cap_state = CapabilityState(state) if isinstance(state, str) else state
        if cap_id in self._capabilities:
            cap = self._capabilities[cap_id]
            cap.state = cap_state
            if reason is not None:
                cap.reason = reason
            if alternatives is not None:
                cap.alternatives = list(alternatives)
            if evidence is not None:
                cap.evidence = list(evidence)
        else:
            self._capabilities[cap_id] = Capability(
                id=cap_id,
                state=cap_state,
                reason=reason,
                alternatives=list(alternatives) if alternatives else [],
                evidence=list(evidence) if evidence else [],
            )

    def evaluate(self, cap_id: str, visited: set[str] | None = None) -> Capability:
        """Evaluate effective capability state taking prerequisite dependencies into account.

        If any prerequisite in `requires` is UNAVAILABLE, this evaluates to UNAVAILABLE.
        If any prerequisite is DEGRADED (and none UNAVAILABLE), this evaluates to DEGRADED.
        """
        seen = visited or set()
        if cap_id in seen:
            # Prevent circular dependency recursion
            return Capability(
                id=cap_id,
                state=CapabilityState.UNAVAILABLE,
                reason=f"Circular prerequisite dependency detected involving '{cap_id}'.",
            )
        seen.add(cap_id)

        base_cap = self._capabilities.get(cap_id)
        if base_cap is None:
            return Capability(
                id=cap_id,
                state=CapabilityState.UNAVAILABLE,
                reason=f"Capability '{cap_id}' is not registered.",
            )

        # If base state is already explicitly unavailable, preserve it
        if base_cap.state == CapabilityState.UNAVAILABLE:
            return Capability(
                id=base_cap.id,
                state=CapabilityState.UNAVAILABLE,
                name=base_cap.name,
                reason=base_cap.reason or "Capability is marked unavailable.",
                requires=list(base_cap.requires),
                alternatives=list(base_cap.alternatives),
                evidence=list(base_cap.evidence),
                is_experimental=base_cap.is_experimental,
            )

        effective_state = base_cap.state
        effective_reason = base_cap.reason
        all_alternatives = list(base_cap.alternatives)

        # Evaluate each required prerequisite
        for req_id in base_cap.requires:
            req_eval = self.evaluate(req_id, visited=set(seen))

            if req_eval.state == CapabilityState.UNAVAILABLE:
                effective_state = CapabilityState.UNAVAILABLE
                sub_reason = req_eval.reason or "requirement not met"
                effective_reason = f"Prerequisite '{req_id}' is unavailable: {sub_reason}."
                # Inherit alternative options from failing prerequisites if available
                for alt in req_eval.alternatives:
                    if alt not in all_alternatives:
                        all_alternatives.append(alt)
                break
            elif req_eval.state == CapabilityState.DEGRADED:
                if (
                    effective_state == CapabilityState.AVAILABLE
                    or effective_state == CapabilityState.UNKNOWN
                ):
                    effective_state = CapabilityState.DEGRADED
                    sub_reason = req_eval.reason or "reduced capability"
                    effective_reason = f"Prerequisite '{req_id}' is degraded: {sub_reason}."

        return Capability(
            id=base_cap.id,
            state=effective_state,
            name=base_cap.name,
            reason=effective_reason,
            requires=list(base_cap.requires),
            alternatives=all_alternatives,
            evidence=list(base_cap.evidence),
            is_experimental=base_cap.is_experimental,
        )

    def check_capability(self, cap_id: str) -> Capability:
        """Verify capability availability per [CAP-02].

        Raises UnavailableError with remedy and alternatives if capability is UNAVAILABLE.
        """
        evaluated = self.evaluate(cap_id)
        if evaluated.state == CapabilityState.UNAVAILABLE:
            remedy_msg = (
                f"Try alternative capability: {', '.join(evaluated.alternatives)}"
                if evaluated.alternatives
                else "Satisfy required prerequisites or consult 'sbridge doctor'."
            )
            raise UnavailableError(
                message=f"Capability '{cap_id}' is unavailable: {evaluated.reason}",
                details={
                    "capability": cap_id,
                    "reason": evaluated.reason,
                    "alternatives": evaluated.alternatives,
                    "evidence": evaluated.evidence,
                },
                alternatives=evaluated.alternatives,
                remedy=remedy_msg,
            )
        return evaluated

    def get_alternatives(self, cap_id: str) -> list[str]:
        """Return alternative capabilities for a given capability ID."""
        evaluated = self.evaluate(cap_id)
        return list(evaluated.alternatives)

    def aggregate_status(self) -> dict[str, Any]:
        """Aggregate evaluated status across all registered capabilities for status reports."""
        evaluated_map: dict[str, dict[str, Any]] = {}
        counts = {
            CapabilityState.AVAILABLE.value: 0,
            CapabilityState.DEGRADED.value: 0,
            CapabilityState.UNAVAILABLE.value: 0,
            CapabilityState.UNKNOWN.value: 0,
        }

        for cap_id in sorted(self._capabilities):
            eff = self.evaluate(cap_id)
            state_val = eff.state.value
            counts[state_val] = counts.get(state_val, 0) + 1
            evaluated_map[cap_id] = {
                "state": state_val,
                "reason": eff.reason,
                "requires": eff.requires,
                "alternatives": eff.alternatives,
                "evidence": eff.evidence,
            }

        return {
            "capabilities": evaluated_map,
            "summary": {
                "total": len(self._capabilities),
                **counts,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize raw registered capabilities."""
        return {
            "capabilities": {cap_id: cap.to_dict() for cap_id, cap in self._capabilities.items()}
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityRegistry:
        """Construct CapabilityRegistry from dictionary representation."""
        reg = cls()
        caps_dict = data.get("capabilities", {})
        for _, cap_data in caps_dict.items():
            reg.register(Capability.from_dict(cap_data))
        return reg

    def to_json(self, indent: int = 2) -> str:
        """Serialize registry to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> CapabilityRegistry:
        """Construct registry from JSON string."""
        return cls.from_dict(json.loads(text))

    def save_to_file(self, path: Path) -> None:
        """Save registry to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> CapabilityRegistry:
        """Load registry from a JSON file."""
        if not path.is_file():
            return cls()
        return cls.from_json(path.read_text(encoding="utf-8"))


# Standard capability IDs
CAP_LIVE_TRANSPORT_CONTROL = "live.transport.control"
CAP_LIVE_MIXER_WRITE = "live.mixer.write"
CAP_LIVE_CHANNELS = "live.channels"
CAP_LIVE_PATTERNS = "live.patterns"
CAP_LIVE_PLUGIN_PARAM_WRITE = "live.plugin.param.write"
CAP_LIVE_PIANOROLL_APPLY = "live.pianoroll.apply"
CAP_LIVE_PROJECT_SAVE = "live.project.save"
CAP_LIVE_PLAYLIST_CLIP_PLACE = "live.playlist.clip.place"
CAP_OFFLINE_FLP_READ = "offline.flp.read"
CAP_OFFLINE_FLP_WRITE = "offline.flp.write"
CAP_RENDER_CLI = "render.cli"
CAP_ACTUATE_KEYSTROKE = "actuate.keystroke"
CAP_SANDBOX_FILE_IO = "sandbox.file_io"
CAP_PORT_WMS_LOOPBACK = "port.wms.loopback"
CAP_LIVE_PROJECT = "live.project"
CAP_LIVE_UI = "live.ui"
CAP_EXPERIMENTAL_PLAYLIST_PLACE = "experimental.playlist_place"


def create_default_registry() -> CapabilityRegistry:
    """Create a CapabilityRegistry pre-populated with standard StudioBridge capabilities."""
    reg = CapabilityRegistry()
    reg.register_all(
        [
            Capability(
                id=CAP_PORT_WMS_LOOPBACK,
                state=CapabilityState.UNKNOWN,
                reason="Port backend loopback status",
            ),
            Capability(
                id=CAP_LIVE_TRANSPORT_CONTROL,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_MIXER_WRITE,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_CHANNELS,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_PATTERNS,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_PLUGIN_PARAM_WRITE,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_PIANOROLL_APPLY,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
                alternatives=[CAP_OFFLINE_FLP_WRITE],
            ),
            Capability(
                id=CAP_LIVE_PROJECT_SAVE,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_PLAYLIST_CLIP_PLACE,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_PROJECT,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_LIVE_UI,
                state=CapabilityState.UNKNOWN,
                requires=[CAP_PORT_WMS_LOOPBACK],
            ),
            Capability(
                id=CAP_EXPERIMENTAL_PLAYLIST_PLACE,
                state=CapabilityState.DEGRADED,
                is_experimental=True,
                reason="Feature flag experimental.playlist_place is disabled.",
                alternatives=["Enable experimental capability 'experimental.playlist_place'"],
            ),
            Capability(
                id=CAP_OFFLINE_FLP_READ,
                state=CapabilityState.AVAILABLE,
                reason="Built-in offline FLP parser",
            ),
            Capability(
                id=CAP_OFFLINE_FLP_WRITE,
                state=CapabilityState.AVAILABLE,
                requires=[CAP_OFFLINE_FLP_READ],
                reason="Built-in offline FLP generator",
            ),
            Capability(
                id=CAP_RENDER_CLI,
                state=CapabilityState.UNKNOWN,
                reason="Requires FL64.exe installation",
            ),
            Capability(
                id=CAP_ACTUATE_KEYSTROKE,
                state=CapabilityState.UNKNOWN,
                reason="Requires Win32 UI focus and permissions",
            ),
            Capability(
                id=CAP_SANDBOX_FILE_IO,
                state=CapabilityState.UNKNOWN,
                reason="Device script filesystem access",
            ),
        ]
    )
    return reg
