"""Unit and integration tests for Studio and AsyncStudio SDK client.

Verifies [SDK-01], [SDK-02], [CAP-02]:
- with Studio.connect(embedded=True) as fl: executes cleanly and returns Status.
- async with AsyncStudio.connect(embedded=True) as fl: executes cleanly under anyio.
- fl.status() returns complete structured session status.
- fl.ping(), fl.stats(), fl.trace() observability hooks.
- Connection failure mappings (NoBrokerError, DisconnectedError, ReadOnlyError).
- End-to-end integration over FakeMidiPort and DeviceEmulator harness.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from studiobridge import (
    AsyncStudio,
    DisconnectedError,
    NoBrokerError,
    ReadOnlyError,
    Studio,
    connect,
)
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.ports.fake import FakeMidiPort


def test_sync_studio_connect_and_status() -> None:
    """Verify Studio.connect(embedded=True) initializes session and returns complete Status."""
    with Studio.connect(embedded=True) as fl:
        assert fl.is_connected is True
        assert fl.mode == "read_only"

        # 1. Status query
        st = fl.status()
        assert st.fl_version == "24.1.0"
        assert st.api == 44
        assert st.mode == "read_only"
        assert st.connected is True
        assert isinstance(st.caps_summary, dict)
        assert isinstance(st.rtt, float)

        st_dict = st.to_dict()
        assert st_dict["connected"] is True
        assert "caps_summary" in st_dict

        # 2. Ping round-trip
        rtt = fl.ping()
        assert isinstance(rtt, float)
        assert rtt >= 0.0

        # 3. Telemetry stats
        stats = fl.stats()
        assert "calls" in stats
        assert "batches" in stats
        assert "pings" in stats
        assert stats["pings"]["count"] >= 1


@pytest.mark.anyio
async def test_async_studio_connect_and_status() -> None:
    """Verify AsyncStudio.connect(embedded=True) works under anyio."""
    async with AsyncStudio.connect(embedded=True) as fl:
        assert fl.is_connected is True
        assert fl.mode == "read_only"

        st = fl.status()
        assert st.connected is True
        assert st.api == 44

        rtt = await fl.ping()
        assert isinstance(rtt, float)

        stats = fl.stats()
        assert stats["pings"]["count"] >= 1


def test_module_level_connect_convenience() -> None:
    """connect() module-level convenience function connects synchronously."""
    with connect(embedded=True) as fl:
        assert fl.is_connected is True
        assert fl.status().connected is True


def test_safety_mode_read_only_rejection() -> None:
    """Mutating operations in read-only mode raise ReadOnlyError per [SAF-01]."""
    with Studio.connect(embedded=True, mode="read_only") as fl:
        with pytest.raises(ReadOnlyError) as exc_info:
            fl.raw.call("mixer.setTrackVolume", track=0, value=0.5)

        err = exc_info.value
        assert err.code == "E_READONLY"
        assert "read-only mode" in err.message
        assert err.remedy is not None


def test_disconnected_error_after_close() -> None:
    """Calling operations on a closed session raises DisconnectedError."""
    fl = Studio.connect(embedded=True)
    fl.close()
    assert fl.is_connected is False

    with pytest.raises(DisconnectedError) as exc_info:
        fl.raw.call("ping")

    err = exc_info.value
    assert err.code == "E_DISCONNECTED"


def test_no_broker_error_on_unreachable_daemon() -> None:
    """Connecting to a non-existent TCP port raises NoBrokerError."""
    # Use invalid host port with 0.2s timeout so test doesn't wait
    with pytest.raises(NoBrokerError) as exc_info:
        Studio.connect(
            embedded=False,
            host="127.0.0.1",
            port_number=65530,
            token="invalid_tok",
            timeout=0.3,
        )

    err = exc_info.value
    assert err.code == "E_NOBROKER"
    assert err.remedy is not None


def test_sync_trace_context(tmp_path: pathlib.Path) -> None:
    """Verify fl.trace() captures frames and outputs JSONL log."""
    log_file = tmp_path / "trace_sync.jsonl"

    with Studio.connect(embedded=True) as fl:
        with fl.trace(output_path=log_file) as tr:
            fl.raw.call("ping")
            fl.ping()

        assert len(tr.records) >= 2
        assert log_file.is_file()
        content = log_file.read_text(encoding="utf-8")
        assert "ping" in content


@pytest.mark.anyio
async def test_async_trace_context(tmp_path: pathlib.Path) -> None:
    """Verify AsyncStudio fl.trace() captures records and redacts secrets."""
    log_file = tmp_path / "trace_async.jsonl"

    def mock_handler(op: str, args: dict[str, Any]) -> Any:
        return {"result": "ok"}

    async with AsyncStudio.connect(embedded=True, direct_handler=mock_handler) as fl:
        async with fl.trace(output_path=log_file) as tr:
            await fl.raw.call("ping", secret_key="super_secret_val")

        assert len(tr.records) >= 1
        content = log_file.read_text(encoding="utf-8")
        assert "[REDACTED]" in content
        assert "super_secret_val" not in content


def test_end_to_end_emulator_integration(tmp_path: pathlib.Path) -> None:
    """End-to-end integration test connecting Studio to DeviceEmulator via FakeMidiPort."""
    secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    # 1. Generate multi-file device script bundle
    bundle_dir = tmp_path / "device_bundle"
    generator = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="0.2.3-test",
        secret=secret,
        budget_ms=20,
        budget_calls=50,
    )
    generator.generate_multi_file(bundle_dir)

    # 2. Spin up DeviceEmulator
    emulator = DeviceEmulator(
        script_dir=bundle_dir,
        device_name="TestDevice",
        enforce_sandbox=False,  # sandbox disabled to permit thread coordination in tests
    )
    emulator.start()

    try:
        # 3. Create bidirectional fake MIDI port pair
        port_sdk, port_device = FakeMidiPort.create_pair(
            name_a="TestDevice Loopback (A)",
            name_b="TestDevice Loopback (B)",
        )

        # Wire port_device to emulator's OnSysEx handler
        def on_device_sysex(data: bytes) -> None:
            emulator.send_sysex(data)
            # Send any responses generated by device script back to SDK port
            for out_frame in emulator.get_sent_sysex():
                port_device.send_sysex(out_frame)
            emulator.clear_sent_sysex()

        port_device.on_sysex(on_device_sysex)

        # 4. Connect synchronous Studio client over port_sdk
        with Studio.connect(embedded=True, port=port_sdk, secret=secret) as fl:
            assert fl.is_connected is True

            # Handshake verification: SID and FP populated from device emulator
            st = fl.status()
            assert st.connected is True
            assert st.api == 44
            assert fl.sid is not None and fl.sid > 0
            assert fl.fp is not None

            # Execute read operation: mixer.getTrackVolume(0) -> default 0.8
            vol = fl.raw.call("mixer.getTrackVolume", 0)
            assert vol == 0.8

            # Execute read operation on transport: transport.isPlaying() -> False
            is_playing = fl.raw.call("transport.isPlaying")
            assert is_playing is False

    finally:
        emulator.stop()
