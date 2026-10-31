"""Unit tests for DeviceScriptGenerator per [DEV-01]..[DEV-03]."""

from __future__ import annotations

import pathlib
from typing import Any

from studiobridge.device.generator import DeviceScriptGenerator


def test_generator_default_parameters() -> None:
    """Verify default generator parameter initialization."""
    gen = DeviceScriptGenerator()
    assert gen.device_name == "StudioBridge"
    assert gen.port_root == "StudioBridge"
    assert gen.build_id == "1.0.0"
    assert len(gen.secret) == 64  # 32 bytes hex = 64 chars
    assert gen.auth_alg == "sha256"
    assert gen.max_frame == 512
    assert gen.budget_ms == 15
    assert gen.budget_calls == 150
    assert gen.unsafe == 0


def test_generator_custom_parameters() -> None:
    """Verify custom parameter injection."""
    custom_secret = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    gen = DeviceScriptGenerator(
        device_name="CustomDevice",
        port_root="CustomPort",
        build_id="1.2.3",
        secret=custom_secret,
        auth_alg="siphash24",
        max_frame=1022,
        budget_ms=25,
        budget_calls=200,
        unsafe=1,
    )
    assert gen.device_name == "CustomDevice"
    assert gen.port_root == "CustomPort"
    assert gen.build_id == "1.2.3"
    assert gen.secret == custom_secret
    assert gen.auth_alg == "siphash24"
    assert gen.max_frame == 1022
    assert gen.budget_ms == 25
    assert gen.budget_calls == 200
    assert gen.unsafe == 1


def test_generator_multi_file_bundle(tmp_path: pathlib.Path) -> None:
    """Verify multi-file bundle directory layout and compilation."""
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestPort",
        build_id="0.2.0",
        secret="cafebabe" * 8,
    )
    out_dir = tmp_path / "TestDevice"
    created = gen.generate_multi_file(out_dir)

    expected_files = {
        "device_TestDevice.py",
        "_sb_wire.py",
        "_sb_json.py",
        "_sb_auth.py",
        "_sb_core.py",
        "_sb_api.py",
    }
    assert set(created.keys()) == expected_files

    for _name, path in created.items():
        assert path.exists()
        code = path.read_text(encoding="utf-8")
        # Ensure each generated file compiles cleanly without syntax error
        compiled = compile(code, str(path), "exec")
        assert compiled is not None

    entry_code = created["device_TestDevice.py"].read_text(encoding="utf-8")
    assert "# name=TestDevice" in entry_code
    assert "# supportedDevices=TestPort (A)" in entry_code
    assert 'BUILD_ID = "0.2.0"' in entry_code
    assert f'SECRET = "{"cafebabe" * 8}"' in entry_code


def test_generator_single_file_inlining(tmp_path: pathlib.Path) -> None:
    """Verify single-file inlined bundle generation and self-contained syntax."""
    gen = DeviceScriptGenerator(
        device_name="InlinedDevice",
        port_root="InlinedPort",
        build_id="0.3.0",
        secret="deadbeef" * 8,
        budget_ms=20,
    )
    target_file = tmp_path / "device_InlinedDevice.py"
    out_path = gen.generate_single_file(target_file)

    assert out_path.exists()
    assert out_path == target_file

    inlined_code = out_path.read_text(encoding="utf-8")
    assert "# name=InlinedDevice" in inlined_code
    assert "# supportedDevices=InlinedPort (A)" in inlined_code
    assert 'BUILD_ID = "0.3.0"' in inlined_code
    assert f'SECRET = "{"deadbeef" * 8}"' in inlined_code
    assert "BUDGET_MS = 20" in inlined_code

    # Verify that inlined markers and component sections exist
    assert "BEGIN _sb_wire.py" in inlined_code
    assert "BEGIN _sb_json.py" in inlined_code
    assert "BEGIN _sb_auth.py" in inlined_code
    assert "BEGIN _sb_api.py" in inlined_code
    assert "BEGIN _sb_core.py" in inlined_code
    assert "BEGIN device_entry.py handlers" in inlined_code

    # Verify that the entire inlined script compiles cleanly
    compiled = compile(inlined_code, str(target_file), "exec")
    assert compiled is not None

    # Verify that executing the inlined code in an isolated namespace produces all expected symbols
    scope: dict[str, Any] = {"__name__": "device_InlinedDevice"}
    exec(compiled, scope)
    assert "OnInit" in scope
    assert "OnSysEx" in scope
    assert "OnIdle" in scope
    assert "OnDeInit" in scope
    assert "encode_frame" in scope
    assert "decode_frame" in scope
    assert "dumps" in scope
    assert "loads" in scope
    assert "compute_auth" in scope
    assert "verify_auth" in scope
    assert "Dispatcher" in scope
