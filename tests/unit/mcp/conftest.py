"""Shared pytest fixtures for MCP unit and integration tests against DeviceEmulator."""

from __future__ import annotations

import pathlib
from collections.abc import Generator

import pytest

from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.client import Studio


@pytest.fixture(scope="session")
def mcp_secret() -> str:
    """Deterministic HMAC-SHA256 test secret."""
    return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="session")
def mcp_emulator_bundle(tmp_path_factory: pytest.TempPathFactory, mcp_secret: str) -> pathlib.Path:
    """Generate multi-file device script bundle once per test session."""
    tmp_path = tmp_path_factory.mktemp("mcp_emulator_bundle")
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="0.3.1-test",
        secret=mcp_secret,
        budget_ms=100,
        budget_calls=200,
    )
    gen.generate_multi_file(tmp_path)
    return tmp_path


@pytest.fixture
def running_emulator(
    mcp_emulator_bundle: pathlib.Path,
) -> Generator[tuple[FakeMidiPort, DeviceEmulator], None, None]:
    """Spin up DeviceEmulator wired to FakeMidiPort loopback pair."""
    emulator = DeviceEmulator(
        script_dir=mcp_emulator_bundle,
        device_name="TestDevice",
        enforce_sandbox=False,
    )
    emulator.start()

    port_sdk, port_device = FakeMidiPort.create_pair(
        name_a="TestDevice Loopback (A)",
        name_b="TestDevice Loopback (B)",
    )

    def on_device_sysex(data: bytes) -> None:
        emulator.send_sysex(data)
        for out_frame in emulator.get_sent_sysex():
            port_device.send_sysex(out_frame)
        emulator.clear_sent_sysex()

    port_device.on_sysex(on_device_sysex)

    try:
        yield port_sdk, emulator
    finally:
        emulator.stop()


@pytest.fixture
def studio(
    running_emulator: tuple[FakeMidiPort, DeviceEmulator],
    mcp_secret: str,
) -> Generator[Studio, None, None]:
    """Provide connected synchronous Studio client in write mode."""
    port_sdk, _ = running_emulator
    with Studio.connect(embedded=True, port=port_sdk, secret=mcp_secret, mode="write") as fl:
        yield fl
