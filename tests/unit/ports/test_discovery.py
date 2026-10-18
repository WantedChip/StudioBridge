"""Unit tests for MIDI port discovery, matching order, and ambiguity handling [PORT-16, PORT-17]."""

import pytest

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPortInfo
from studiobridge.ports.discovery import PortResolver
from studiobridge.ports.fake import FakeMidiPort


@pytest.fixture
def test_ports() -> list[MidiPortInfo]:
    """Sample list of input and output ports for discovery testing."""
    return [
        MidiPortInfo(direction="in", index=0, name="StudioBridge Loopback (A)", api="winmm"),
        MidiPortInfo(direction="out", index=0, name="StudioBridge Loopback (A)", api="winmm"),
        MidiPortInfo(direction="in", index=1, name="StudioBridge Loopback (B)", api="winmm"),
        MidiPortInfo(direction="out", index=1, name="StudioBridge Loopback (B)", api="winmm"),
        MidiPortInfo(direction="in", index=2, name="Default App Loopback (A)", api="winmm"),
        MidiPortInfo(direction="out", index=2, name="Default App Loopback (A)", api="winmm"),
        MidiPortInfo(direction="in", index=3, name="Default App Loopback (B)", api="winmm"),
        MidiPortInfo(direction="out", index=3, name="Default App Loopback (B)", api="winmm"),
        MidiPortInfo(direction="in", index=4, name="Hardware Controller", api="winmm"),
        MidiPortInfo(direction="out", index=4, name="Hardware Synth Out", api="winmm"),
    ]


def test_exact_name_match(test_ports: list[MidiPortInfo]) -> None:
    """Verify exact match has top priority [PORT-16]."""
    resolver = PortResolver(FakeMidiPort())
    info = resolver.resolve("StudioBridge Loopback (A)", direction="in", available_ports=test_ports)
    assert info.name == "StudioBridge Loopback (A)"
    assert info.index == 0
    assert info.direction == "in"


def test_case_insensitive_match(test_ports: list[MidiPortInfo]) -> None:
    """Verify case-insensitive matching when exact match is absent [PORT-16]."""
    resolver = PortResolver(FakeMidiPort())
    info = resolver.resolve("studiobridge loopback (b)", direction="in", available_ports=test_ports)
    assert info.name == "StudioBridge Loopback (B)"
    assert info.index == 1


def test_prefix_match(test_ports: list[MidiPortInfo]) -> None:
    """Verify prefix matching when unique [PORT-16]."""
    resolver = PortResolver(FakeMidiPort())
    info = resolver.resolve("Hardware Cont", direction="in", available_ports=test_ports)
    assert info.name == "Hardware Controller"
    assert info.index == 4


def test_ambiguous_prefix_match_raises_porterror(test_ports: list[MidiPortInfo]) -> None:
    """Verify ambiguous match raises PortError with full candidate listing [PORT-16]."""
    resolver = PortResolver(FakeMidiPort())

    # "StudioBridge" prefix matches both (A) and (B)
    with pytest.raises(PortError) as exc_info:
        resolver.resolve("StudioBridge", direction="in", available_ports=test_ports)

    err = exc_info.value
    assert err.code == "E_ENV_PORT"
    assert "Ambiguous MIDI in port match" in err.message
    assert "candidates" in err.details
    assert len(err.details["candidates"]) == 2
    assert "StudioBridge Loopback (A)" in err.details["candidates"]
    assert "StudioBridge Loopback (B)" in err.details["candidates"]
    assert err.remedy is not None
    assert "Specify the exact full name" in err.remedy


def test_port_not_found_raises_porterror(test_ports: list[MidiPortInfo]) -> None:
    """Verify non-existent port raises PortError with list of available ports."""
    resolver = PortResolver(FakeMidiPort())

    with pytest.raises(PortError) as exc_info:
        resolver.resolve("NonExistentPort 9000", direction="in", available_ports=test_ports)

    err = exc_info.value
    assert err.code == "E_ENV_PORT"
    assert "not found" in err.message
    assert "available_ports" in err.details
    assert "Available in ports" in err.remedy


def test_resolve_in_and_out_helpers(test_ports: list[MidiPortInfo]) -> None:
    """Verify resolve_in and resolve_out apply correct directional filters."""
    resolver = PortResolver(FakeMidiPort())

    in_info = resolver.resolve_in("Hardware Controller", available_ports=test_ports)
    assert in_info.direction == "in"

    out_info = resolver.resolve_out("Hardware Synth Out", available_ports=test_ports)
    assert out_info.direction == "out"

    # Searching for out port with resolve_in should fail
    with pytest.raises(PortError):
        resolver.resolve_in("Hardware Synth Out", available_ports=test_ports)


def test_resolve_pair_wms(test_ports: list[MidiPortInfo]) -> None:
    """Verify resolve_pair discovers Side A and Side B endpoints."""
    resolver = PortResolver(FakeMidiPort())
    in_port, out_port = resolver.resolve_pair("StudioBridge Loopback", available_ports=test_ports)

    assert in_port.name == "StudioBridge Loopback (A)"
    assert out_port.name == "StudioBridge Loopback (B)"
    assert in_port.direction == "in"
    assert out_port.direction == "out"


def test_resolve_pair_default_app_loopback(test_ports: list[MidiPortInfo]) -> None:
    """Verify resolve_pair with 'auto' selects in-box Default App Loopback pair."""
    resolver = PortResolver(FakeMidiPort())
    in_port, out_port = resolver.resolve_pair("auto", available_ports=test_ports)

    assert in_port.name == "Default App Loopback (A)"
    assert out_port.name == "Default App Loopback (B)"


def test_resolve_pair_unresolvable_raises_porterror() -> None:
    """Verify resolve_pair raises PortError when no matching pair can be found."""
    ports = [
        MidiPortInfo(direction="in", index=0, name="Random Port 1", api="winmm"),
        MidiPortInfo(direction="out", index=0, name="Random Port 2", api="winmm"),
    ]
    resolver = PortResolver(FakeMidiPort())

    with pytest.raises(PortError) as exc_info:
        resolver.resolve_pair("StudioBridge", available_ports=ports)

    assert exc_info.value.code == "E_ENV_PORT"
    assert "Could not resolve a matching MIDI loopback port pair" in exc_info.value.message
    assert exc_info.value.remedy is not None
