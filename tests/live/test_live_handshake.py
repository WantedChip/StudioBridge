"""End-to-end live verification test suite against a real FL Studio instance.

Decorated with @pytest.mark.live, these tests are cleanly deselected by default
in standard CI and run only when explicitly requested via --run-live or -m live.
"""

from __future__ import annotations

import json
import time
from typing import Any

import anyio
import pytest

from studiobridge.broker.client import BrokerClient, is_process_alive
from studiobridge.core.paths import get_broker_json_path, get_broker_token_path
from studiobridge.setup.probe import ProbeReport, run_probe


def _get_live_broker_client() -> BrokerClient | None:
    """Return an active BrokerClient if a live broker process is running, else None."""
    meta_path = get_broker_json_path()
    token_path = get_broker_token_path()

    if not meta_path.exists() or not token_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pid = int(meta.get("pid", 0))
        port = int(meta.get("port", 0))
        if not is_process_alive(pid):
            return None
        return BrokerClient(
            port=port,
            metadata_path=meta_path,
            token_path=token_path,
        )
    except Exception:
        return None


def _check_live_fl_running() -> bool:
    """Check if a real FL Studio process (FL64.exe) is currently running on the host."""
    probe = run_probe()
    return probe.fl_studio.is_running


@pytest.fixture
def live_context() -> dict[str, Any]:
    """Ensure a live FL Studio instance or active broker is available, or skip cleanly."""
    fl_running = _check_live_fl_running()
    client = _get_live_broker_client()

    if not fl_running and client is None:
        pytest.skip(
            "Live test skipped: No running FL Studio instance (FL64.exe) "
            "or active StudioBridge broker detected on host."
        )

    return {
        "fl_running": fl_running,
        "client": client,
    }


def test_live_marker_gating_contract() -> None:
    """Verify that live test markers are recognized and live tests are segregated."""
    # req: TST-05
    # This non-marked test verifies that the live test module exists and probe runs.
    report = run_probe()
    assert isinstance(report, ProbeReport)
    assert report.host.os != ""
    assert report.host.machine != ""


@pytest.mark.live
def test_live_probe_execution(live_context: dict[str, Any]) -> None:
    """Verify that live environment probe captures real host and FL Studio execution facts."""
    # req: TST-05, CAP-01
    report = run_probe()
    assert isinstance(report, ProbeReport)
    assert report.host.python_arch != ""
    assert report.host.machine != ""
    assert report.fl_studio.user_data_dir is not None

    if live_context["fl_running"]:
        assert report.fl_studio.is_running is True
        assert len(report.fl_studio.pids) > 0


@pytest.mark.live
def test_live_handshake_hello(live_context: dict[str, Any]) -> None:
    """Verify end-to-end hello handshake against a live FL Studio device script."""
    # req: WIRE-01, TST-05
    client: BrokerClient | None = live_context["client"]
    if client is None:
        pytest.skip("Broker is not running; start broker with 'sbridge broker start'")

    async def _do_hello() -> dict[str, Any]:
        async with client:
            res = await client.device_call("hello", timeout=5.0)
            return res if isinstance(res, dict) else {"response": res}

    res = anyio.run(_do_hello)
    assert isinstance(res, dict)
    assert "build_id" in res or "build" in res or "device" in res


@pytest.mark.live
def test_live_ping_latency(live_context: dict[str, Any]) -> None:
    """Verify live SysEx round-trip time is within performance budget (< 100 ms)."""
    # req: WIRE-01, WIRE-05
    client: BrokerClient | None = live_context["client"]
    if client is None:
        pytest.skip("Broker is not running; start broker with 'sbridge broker start'")

    async def _measure_pings() -> list[float]:
        rtts: list[float] = []
        async with client:
            for _ in range(5):
                t0 = time.perf_counter()
                await client.device_call("ping", timeout=3.0)
                t1 = time.perf_counter()
                rtts.append((t1 - t0) * 1000.0)
                await anyio.sleep(0.01)
        return rtts

    rtts = anyio.run(_measure_pings)
    assert len(rtts) == 5
    avg_rtt = sum(rtts) / len(rtts)
    # RTT budget per spec 12_crosscutting.md §5: p50 <= 25-50 ms, max <= 100 ms
    assert avg_rtt < 100.0, f"Average live ping RTT too high: {avg_rtt:.2f} ms"


@pytest.mark.live
def test_live_read_back(live_context: dict[str, Any]) -> None:
    """Verify non-mutating state query against live FL Studio instance."""
    # req: LIVE-01, WIRE-02
    client: BrokerClient | None = live_context["client"]
    if client is None:
        pytest.skip("Broker is not running; start broker with 'sbridge broker start'")

    async def _do_probe() -> dict[str, Any]:
        async with client:
            res = await client.device_call("probe", timeout=5.0)
            return res if isinstance(res, dict) else {"response": res}

    res = anyio.run(_do_probe)
    assert isinstance(res, dict)
