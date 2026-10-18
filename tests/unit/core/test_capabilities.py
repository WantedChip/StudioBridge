"""Unit tests for StudioBridge capability model and registry.

# req: CAP-01, CAP-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

from studiobridge.core.capabilities import (
    CAP_LIVE_MIXER_WRITE,
    CAP_LIVE_PIANOROLL_APPLY,
    CAP_OFFLINE_FLP_WRITE,
    CAP_PORT_WMS_LOOPBACK,
    Capability,
    CapabilityRegistry,
    CapabilityState,
    create_default_registry,
)
from studiobridge.core.errors import UnavailableError


def test_capability_serialization():
    """Verify Capability dataclass serialization and deserialization.

    # req: CAP-01
    """
    cap = Capability(
        id="test.feature",
        state=CapabilityState.AVAILABLE,
        reason="Enabled by default",
        requires=["dep.one"],
        alternatives=["alt.feature"],
        evidence=["probe_ok"],
    )

    d = cap.to_dict()
    assert d["id"] == "test.feature"
    assert d["state"] == "available"
    assert d["reason"] == "Enabled by default"
    assert d["requires"] == ["dep.one"]
    assert d["alternatives"] == ["alt.feature"]
    assert d["evidence"] == ["probe_ok"]

    restored = Capability.from_dict(d)
    assert restored.id == cap.id
    assert restored.state == CapabilityState.AVAILABLE
    assert restored.requires == cap.requires


def test_registry_prerequisite_evaluation_available():
    """Verify capability evaluates to available when all prerequisites are available.

    # req: CAP-01
    """
    reg = CapabilityRegistry()
    reg.register(Capability(id="port.loopback", state=CapabilityState.AVAILABLE))
    reg.register(
        Capability(
            id="live.transport",
            state=CapabilityState.AVAILABLE,
            requires=["port.loopback"],
        )
    )

    evaluated = reg.evaluate("live.transport")
    assert evaluated.state == CapabilityState.AVAILABLE


def test_registry_prerequisite_evaluation_degraded():
    """Verify capability evaluates to degraded when a prerequisite is degraded.

    # req: CAP-01
    """
    reg = CapabilityRegistry()
    reg.register(
        Capability(
            id="port.loopback",
            state=CapabilityState.DEGRADED,
            reason="High latency measured",
        )
    )
    reg.register(
        Capability(
            id="live.transport",
            state=CapabilityState.AVAILABLE,
            requires=["port.loopback"],
        )
    )

    evaluated = reg.evaluate("live.transport")
    assert evaluated.state == CapabilityState.DEGRADED
    assert "High latency" in (evaluated.reason or "")


def test_registry_prerequisite_evaluation_unavailable():
    """Verify capability evaluates to unavailable when a prerequisite is unavailable.

    # req: CAP-01, CAP-02
    """
    reg = CapabilityRegistry()
    reg.register(
        Capability(
            id="port.loopback",
            state=CapabilityState.UNAVAILABLE,
            reason="WMS service stopped",
            alternatives=["port.loopmidi"],
        )
    )
    reg.register(
        Capability(
            id="live.mixer.write",
            state=CapabilityState.AVAILABLE,
            requires=["port.loopback"],
            alternatives=["offline.flp.write"],
        )
    )

    evaluated = reg.evaluate("live.mixer.write")
    assert evaluated.state == CapabilityState.UNAVAILABLE
    assert "port.loopback" in (evaluated.reason or "")
    assert "port.loopmidi" in evaluated.alternatives
    assert "offline.flp.write" in evaluated.alternatives


def test_check_capability_surfaces_e_unavailable():
    """Verify check_capability raises UnavailableError with E_UNAVAILABLE and alternatives.

    # req: CAP-02
    """
    reg = CapabilityRegistry()
    reg.register(
        Capability(
            id="live.pianoroll.apply",
            state=CapabilityState.UNAVAILABLE,
            reason="pyscript not installed in FL Studio settings",
            alternatives=["offline.flp.write"],
        )
    )

    with pytest.raises(UnavailableError) as exc_info:
        reg.check_capability("live.pianoroll.apply")

    err = exc_info.value
    assert err.code == "E_UNAVAILABLE"
    assert "live.pianoroll.apply" in err.message
    assert err.alternatives == ["offline.flp.write"]
    assert "offline.flp.write" in err.remedy
    assert len(err.remedy) > 0


def test_check_capability_succeeds_when_available():
    """Verify check_capability succeeds and returns Capability when available.

    # req: CAP-01
    """
    reg = CapabilityRegistry()
    reg.register(Capability(id="offline.flp.read", state=CapabilityState.AVAILABLE))

    cap = reg.check_capability("offline.flp.read")
    assert cap.id == "offline.flp.read"
    assert cap.state == CapabilityState.AVAILABLE


def test_unregistered_capability_evaluates_to_unavailable():
    """Verify requesting an unregistered capability returns unavailable.

    # req: CAP-01, CAP-02
    """
    reg = CapabilityRegistry()
    evaluated = reg.evaluate("unknown.feature")
    assert evaluated.state == CapabilityState.UNAVAILABLE
    assert "not registered" in (evaluated.reason or "")

    with pytest.raises(UnavailableError) as exc_info:
        reg.check_capability("unknown.feature")
    assert exc_info.value.code == "E_UNAVAILABLE"


def test_aggregate_status_report():
    """Verify aggregate_status generates formatted capability report and summary counters.

    # req: CAP-01
    """
    reg = CapabilityRegistry()
    reg.register(Capability(id="cap.avail", state=CapabilityState.AVAILABLE))
    reg.register(Capability(id="cap.degr", state=CapabilityState.DEGRADED))
    reg.register(Capability(id="cap.unavail", state=CapabilityState.UNAVAILABLE))
    reg.register(Capability(id="cap.unk", state=CapabilityState.UNKNOWN))

    report = reg.aggregate_status()
    summary = report["summary"]

    assert summary["total"] == 4
    assert summary["available"] == 1
    assert summary["degraded"] == 1
    assert summary["unavailable"] == 1
    assert summary["unknown"] == 1

    caps = report["capabilities"]
    assert caps["cap.avail"]["state"] == "available"
    assert caps["cap.degr"]["state"] == "degraded"
    assert caps["cap.unavail"]["state"] == "unavailable"
    assert caps["cap.unk"]["state"] == "unknown"


def test_registry_file_roundtrip(tmp_path: Path):
    """Verify registry serialization and loading to/from JSON file.

    # req: CAP-01
    """
    json_path = tmp_path / "capabilities.json"
    reg = CapabilityRegistry()
    reg.register(
        Capability(
            id="test.cap",
            state=CapabilityState.AVAILABLE,
            reason="Verified in test",
            requires=["dep.a"],
            alternatives=["alt.b"],
        )
    )

    reg.save_to_file(json_path)
    assert json_path.exists()

    loaded = CapabilityRegistry.load_from_file(json_path)
    cap = loaded.get("test.cap")
    assert cap is not None
    assert cap.state == CapabilityState.AVAILABLE
    assert cap.reason == "Verified in test"
    assert cap.requires == ["dep.a"]
    assert cap.alternatives == ["alt.b"]


def test_default_registry_initialization():
    """Verify create_default_registry populates canonical capabilities.

    # req: CAP-01
    """
    reg = create_default_registry()
    assert reg.get(CAP_PORT_WMS_LOOPBACK) is not None
    assert reg.get(CAP_LIVE_MIXER_WRITE) is not None
    assert reg.get(CAP_LIVE_PIANOROLL_APPLY) is not None
    assert reg.get(CAP_OFFLINE_FLP_WRITE) is not None

    # Verify offline FLP read is available by default
    flp_read = reg.evaluate("offline.flp.read")
    assert flp_read.state == CapabilityState.AVAILABLE


def test_circular_dependency_handling():
    """Verify circular dependency is detected and evaluates to unavailable.

    # req: CAP-01, CAP-02
    """
    reg = CapabilityRegistry()
    reg.register(Capability(id="cycle.a", state=CapabilityState.AVAILABLE, requires=["cycle.b"]))
    reg.register(Capability(id="cycle.b", state=CapabilityState.AVAILABLE, requires=["cycle.a"]))

    eval_a = reg.evaluate("cycle.a")
    assert eval_a.state == CapabilityState.UNAVAILABLE
    assert "Circular prerequisite" in (eval_a.reason or "")


def test_set_state_and_alternatives():
    """Verify set_state updates existing or adds new capabilities, and get_alternatives works.

    # req: CAP-01
    """
    reg = CapabilityRegistry()
    reg.set_state("cap.new", "available", reason="New feature added", evidence=["ok"])
    cap_new = reg.get("cap.new")
    assert cap_new is not None
    assert cap_new.state == CapabilityState.AVAILABLE

    # Update existing
    reg.set_state("cap.new", CapabilityState.DEGRADED, reason="Degraded")
    updated = reg.get("cap.new")
    assert updated is not None
    assert updated.state == CapabilityState.DEGRADED

    # Test get_alternatives
    reg.register(
        Capability(
            id="cap.with_alt",
            state=CapabilityState.AVAILABLE,
            alternatives=["alt.1", "alt.2"],
        )
    )
    alts = reg.get_alternatives("cap.with_alt")
    assert alts == ["alt.1", "alt.2"]


def test_capability_from_dict_invalid_state():
    """Verify from_dict gracefully handles unknown state string.

    # req: CAP-01
    """
    cap = Capability.from_dict({"id": "foo", "state": "invalid_value"})
    assert cap.state == CapabilityState.UNKNOWN


def test_load_from_file_missing(tmp_path: Path):
    """Verify load_from_file returns empty registry when file does not exist.

    # req: CAP-01
    """
    non_existent = tmp_path / "does_not_exist.json"
    reg = CapabilityRegistry.load_from_file(non_existent)
    assert len(reg._capabilities) == 0
