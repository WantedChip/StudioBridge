"""Pytest fixtures for agent evaluation scenarios against DeviceEmulator."""

from __future__ import annotations

import pathlib
from collections.abc import Generator

import pytest

from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.sdk.client import Studio


@pytest.fixture(scope="session")
def eval_secret() -> str:
    """Deterministic HMAC test secret for evaluation harness."""
    return "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"


@pytest.fixture(scope="session")
def eval_emulator_bundle(
    tmp_path_factory: pytest.TempPathFactory, eval_secret: str
) -> pathlib.Path:
    """Generate controller script bundle once for evaluation tests."""
    tmp_path = tmp_path_factory.mktemp("eval_emulator_bundle")
    gen = DeviceScriptGenerator(
        device_name="EvalDevice",
        port_root="EvalDevice",
        build_id="0.3.5-eval",
        secret=eval_secret,
        budget_ms=100,
        budget_calls=200,
    )
    gen.generate_multi_file(tmp_path)
    return tmp_path


@pytest.fixture
def running_eval_emulator(
    eval_emulator_bundle: pathlib.Path,
) -> Generator[tuple[FakeMidiPort, DeviceEmulator], None, None]:
    """Spin up DeviceEmulator wired to FakeMidiPort loopback pair."""
    emulator = DeviceEmulator(
        script_dir=eval_emulator_bundle,
        device_name="EvalDevice",
        enforce_sandbox=False,
    )
    emulator.start()

    port_sdk, port_device = FakeMidiPort.create_pair(
        name_a="EvalDevice Loopback (A)",
        name_b="EvalDevice Loopback (B)",
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
def eval_studio_readonly(
    running_eval_emulator: tuple[FakeMidiPort, DeviceEmulator],
    eval_secret: str,
) -> Generator[Studio, None, None]:
    """Provide connected Studio client in default read_only mode."""
    port_sdk, _ = running_eval_emulator
    with Studio.connect(embedded=True, port=port_sdk, secret=eval_secret, mode="read_only") as fl:
        yield fl


@pytest.fixture
def eval_studio_write(
    running_eval_emulator: tuple[FakeMidiPort, DeviceEmulator],
    eval_secret: str,
) -> Generator[Studio, None, None]:
    """Provide connected Studio client in write mode."""
    port_sdk, _ = running_eval_emulator
    with Studio.connect(embedded=True, port=port_sdk, secret=eval_secret, mode="write") as fl:
        yield fl
