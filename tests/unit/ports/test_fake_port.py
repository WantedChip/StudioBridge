"""Unit tests for FakeMidiPort in-memory loopback and duplex communication."""

import threading
import time

import pytest

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPort, MidiPortInfo
from studiobridge.ports.fake import FakeMidiPort


def test_fake_port_protocol_conformance() -> None:
    """Verify FakeMidiPort conforms to MidiPort protocol."""
    port = FakeMidiPort()
    assert isinstance(port, MidiPort)
    assert not port.is_open
    assert port.in_name is None
    assert port.out_name is None


def test_fake_port_listing() -> None:
    """Verify FakeMidiPort lists virtual endpoints with MidiPortInfo records."""
    port = FakeMidiPort()
    ports = port.list_ports()
    assert len(ports) >= 4
    for p in ports:
        assert isinstance(p, MidiPortInfo)
        assert p.api == "fake"
        assert p.direction in ("in", "out")
        assert "Loopback" in p.name


def test_standalone_loopback_roundtrip() -> None:
    """Verify that a standalone FakeMidiPort loopbacks sent messages to its own callbacks."""
    port = FakeMidiPort()
    port.open("Fake Loopback (A)", "Fake Loopback (A)")
    assert port.is_open

    received: list[bytes] = []
    rx_event = threading.Event()

    def _on_rx(data: bytes) -> None:
        received.append(data)
        rx_event.set()

    port.on_sysex(_on_rx)

    test_msg = b"\xf0\x7d\x53\x42\x01\x00\x01\x02\xf7"
    port.send_sysex(test_msg)

    assert rx_event.wait(timeout=1.0)
    assert len(received) == 1
    assert received[0] == test_msg

    assert port.stats.bytes_sent == len(test_msg)
    assert port.stats.frames_sent == 1
    assert port.stats.bytes_recv == len(test_msg)
    assert port.stats.frames_recv == 1
    assert port.stats.dropped == 0

    port.close()
    assert not port.is_open


def test_paired_duplex_communication() -> None:
    """Verify duplex communication between cross-wired FakeMidiPort pair."""
    port_a, port_b = FakeMidiPort.create_pair(
        name_a="StudioBridge Loopback (A)",
        name_b="StudioBridge Loopback (B)",
    )
    assert port_a.is_open
    assert port_b.is_open

    received_a: list[bytes] = []
    received_b: list[bytes] = []
    rx_event_a = threading.Event()
    rx_event_b = threading.Event()

    def _on_rx_a(data: bytes) -> None:
        received_a.append(data)
        rx_event_a.set()

    def _on_rx_b(data: bytes) -> None:
        received_b.append(data)
        rx_event_b.set()

    port_a.on_sysex(_on_rx_a)
    port_b.on_sysex(_on_rx_b)

    # A sends to B
    msg_a_to_b = b"\xf0\x7d\x53\x42\x01\xaa\xbb\xf7"
    port_a.send_sysex(msg_a_to_b)
    assert rx_event_b.wait(timeout=1.0)
    assert received_b == [msg_a_to_b]
    assert received_a == []

    # B sends to A
    msg_b_to_a = b"\xf0\x7d\x53\x42\x01\xcc\xdd\xf7"
    port_b.send_sysex(msg_b_to_a)
    assert rx_event_a.wait(timeout=1.0)
    assert received_a == [msg_b_to_a]

    # Verify telemetry stats
    assert port_a.stats.frames_sent == 1
    assert port_a.stats.frames_recv == 1
    assert port_a.stats.bytes_received == len(msg_b_to_a)
    assert port_b.stats.frames_sent == 1
    assert port_b.stats.frames_recv == 1
    assert port_b.stats.bytes_received == len(msg_a_to_b)

    port_a.close()
    port_b.close()
    assert not port_a.is_open
    assert not port_b.is_open


def test_latency_simulation() -> None:
    """Verify latency simulation delays packet delivery."""
    port = FakeMidiPort(latency_ms=60.0)
    port.open("Fake Loopback (A)", "Fake Loopback (A)")

    rx_event = threading.Event()
    port.on_sysex(lambda _: rx_event.set())

    t0 = time.perf_counter()
    port.send_sysex(b"\xf0\x7d\x53\x42\x01\x00\xf7")
    assert rx_event.wait(timeout=1.0)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Should take at least 50 ms
    assert elapsed_ms >= 45.0
    port.close()


def test_packet_drop_simulation() -> None:
    """Verify packet drop simulation drops packets and updates stats."""
    port = FakeMidiPort(drop_rate=1.0)
    port.open("Fake Loopback (A)", "Fake Loopback (A)")

    received: list[bytes] = []
    port.on_sysex(lambda d: received.append(d))

    for _ in range(5):
        port.send_sysex(b"\xf0\x7d\x53\x42\x01\x00\xf7")

    time.sleep(0.05)
    assert received == []
    assert port.stats.frames_sent == 5
    assert port.stats.dropped == 5
    assert port.stats.dropped_frames == 5
    assert port.stats.frames_recv == 0

    port.close()


def test_invalid_sysex_and_closed_port_errors() -> None:
    """Verify PortError is raised when sending on closed port or invalid SysEx."""
    port = FakeMidiPort()

    # Sending on closed port
    with pytest.raises(PortError) as exc_info:
        port.send_sysex(b"\xf0\x00\xf7")
    assert exc_info.value.code == "E_ENV_PORT"

    port.open("Fake Loopback (A)", "Fake Loopback (A)")

    # Missing F0
    with pytest.raises(PortError) as exc_info:
        port.send_sysex(b"\x00\x01\xf7")
    assert exc_info.value.code == "E_PROTO"

    # Missing F7
    with pytest.raises(PortError) as exc_info:
        port.send_sysex(b"\xf0\x00\x01")
    assert exc_info.value.code == "E_PROTO"

    port.close()


def test_fail_next_send_and_simulated_errors() -> None:
    """Verify error injection and asynchronous notification callbacks."""
    port = FakeMidiPort()
    port.open("Fake Loopback (A)", "Fake Loopback (A)")

    # One-shot simulated send failure
    custom_err = PortError("Hardware glitch", code="E_FL", remedy="Retry action.")
    port.fail_next_send_error = custom_err

    with pytest.raises(PortError) as exc_info:
        port.send_sysex(b"\xf0\x00\xf7")
    assert exc_info.value is custom_err

    # Next send should succeed
    port.send_sysex(b"\xf0\x00\xf7")

    # Error callback notification
    received_errors: list[PortError] = []
    port.on_error(lambda err: received_errors.append(err))

    async_err = PortError("Async disconnect", code="E_DISCONNECTED")
    port.simulate_error(async_err)
    assert len(received_errors) == 1
    assert received_errors[0] is async_err

    # Disconnect simulation
    port.simulate_disconnect()
    assert not port.is_open
    assert len(received_errors) == 2
    assert received_errors[1].code == "E_DISCONNECTED"


def test_callback_exception_does_not_crash_worker() -> None:
    """Verify unhandled exception inside SysEx callback is forwarded to on_error."""
    port = FakeMidiPort()
    port.open("Fake Loopback (A)", "Fake Loopback (A)")

    errors: list[PortError] = []
    port.on_error(lambda err: errors.append(err))

    def _broken_callback(_: bytes) -> None:
        raise ValueError("Intentional callback failure")

    port.on_sysex(_broken_callback)
    port.send_sysex(b"\xf0\x00\xf7")

    time.sleep(0.05)
    assert len(errors) == 1
    assert "Intentional callback failure" in errors[0].message
    assert errors[0].code == "E_FL"

    port.close()
