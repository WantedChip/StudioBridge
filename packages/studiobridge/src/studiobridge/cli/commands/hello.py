"""Implementation of 'sbridge hello' command."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from typing import Any

import anyio

from studiobridge._version import __version__
from studiobridge.broker.client import BrokerClient, is_process_alive
from studiobridge.core.paths import get_broker_json_path, get_broker_token_path
from studiobridge.device.emulator import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.wire.chunk import Reassembler
from studiobridge.wire.envelope import RequestEnvelope, ResponseEnvelope
from studiobridge.wire.frame import Frame, FrameKind, decode_frame, encode_frame


def _query_emulator_hello() -> dict[str, Any]:
    """Execute hello handshake using mock FL Studio device emulator."""
    generator = DeviceScriptGenerator(build_id=__version__, auth_alg="sha256")
    script_code = generator.get_inlined_code()
    emulator = DeviceEmulator(script_code=script_code, device_name="StudioBridge")

    with io.StringIO() as _sink, contextlib.redirect_stdout(_sink), emulator:
        req_env = RequestEnvelope(op="hello", idem="1")
        frame_bytes = encode_frame(
            Frame(
                kind=FrameKind.REQ,
                flags=0,
                sid=0,
                mid=1,
                cidx=0,
                ccnt=1,
                payload=req_env.to_json(),
            )
        )
        handled = emulator.send_sysex(frame_bytes)
        if not handled:
            raise RuntimeError("Emulator did not handle SysEx request")

        sent_frames = emulator.get_sent_sysex()
        if not sent_frames:
            raise RuntimeError("Emulator generated no response frames")

        reassembler = Reassembler()
        for raw in sent_frames:
            f = decode_frame(raw)
            payload_bytes = reassembler.feed(f)
            if payload_bytes is not None:
                resp = ResponseEnvelope.from_json(payload_bytes)
                result = dict(resp.r) if isinstance(resp.r, dict) else {}
                if "device" in result and isinstance(result["device"], dict):
                    result.setdefault("build_id", result["device"].get("build"))
                if "fl" in result and isinstance(result["fl"], dict):
                    result.setdefault("api", result["fl"].get("api_version"))
                    result.setdefault("fl_version", result["fl"].get("version", "24.1.0"))
                result["sid"] = f.sid
                return result

    return {"build_id": __version__, "api": 44, "fl_version": "24.1.0", "sid": 1}


def handle_hello(args: argparse.Namespace) -> int:
    """Execute 'sbridge hello' handshake with broker or emulator."""
    is_json = getattr(args, "json", False)
    use_emulator = getattr(args, "emulator", False)
    timeout = float(getattr(args, "timeout", 5.0))

    if use_emulator:
        try:
            res = _query_emulator_hello()
            if is_json:
                print(json.dumps({"status": "ok", "source": "emulator", **res}, indent=2))
            else:
                print(
                    f"StudioBridge (Emulator) v{res.get('build_id', __version__)} "
                    f"[API v{res.get('api', 44)}, FL Studio {res.get('fl_version', '24.1.0')}, "
                    f"SID: {res.get('sid', 1)}]"
                )
            return 0
        except Exception as exc:
            if is_json:
                print(
                    json.dumps(
                        {"status": "error", "code": "E_INTERNAL", "message": str(exc)},
                        indent=2,
                    )
                )
            else:
                print(f"Error executing emulator hello: {exc}", file=sys.stderr)
            return 1

    # Live broker communication
    meta_path = get_broker_json_path()
    token_path = get_broker_token_path()

    if not meta_path.exists():
        msg = "Broker is not running. Start it with 'sbridge broker start' or use '--emulator'."
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_NOBROKER",
                        "message": msg,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return 3  # ExitCode.UNAVAILABLE

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        pid = int(meta.get("pid", 0))
        port = int(meta.get("port", 0))
        if not is_process_alive(pid):
            msg = f"Stale broker metadata detected (PID {pid} is dead). Run 'sbridge broker start'."
            if is_json:
                print(
                    json.dumps({"status": "error", "code": "E_NOBROKER", "message": msg}, indent=2)
                )
            else:
                print(f"Error: {msg}", file=sys.stderr)
            return 3

        async def _run_hello() -> dict[str, Any]:
            client = BrokerClient(
                port=port,
                metadata_path=meta_path,
                token_path=token_path,
            )
            async with client:
                res = await client.device_call("hello", timeout=timeout)
                return res if isinstance(res, dict) else {"response": res}

        res = anyio.run(_run_hello)
        if is_json:
            print(json.dumps({"status": "ok", "source": "broker", **res}, indent=2))
        else:
            print(
                f"StudioBridge v{res.get('build_id', __version__)} "
                f"[API v{res.get('api', 'unknown')}, FL: {res.get('fl_version', 'unknown')}, "
                f"SID: {res.get('sid', 'none')}]"
            )
        return 0

    except Exception as exc:
        if is_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "code": "E_UNAVAILABLE",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error: Handshake failed ({exc})", file=sys.stderr)
        return 3
