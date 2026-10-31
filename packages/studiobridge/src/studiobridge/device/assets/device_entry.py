# name={DEVICE}
# url=https://example.invalid/{DIST}
# supportedDevices={PORT_ROOT} (A)

"""FL Studio controller script entry point for StudioBridge.

Generated code strictly conforming to Python 3.9 embedded environment.
"""

import contextlib
import sys
from typing import Any

# Injected parameters (configured by DeviceScriptGenerator)
BUILD_ID = "1.0.0"
SECRET = ""
AUTH_ALG = "sha256"
PORT_ROOT = "StudioBridge"
MAX_FRAME = 512
BUDGET_MS = 15
BUDGET_CALLS = 150
UNSAFE = 0

# Sibling import resolution for multi-file mode
_dir = None
try:
    _file = globals().get("__file__")
    if _file and ("/" in _file or "\\" in _file):
        _sep = "\\" if "\\" in _file else "/"
        _dir = _file.rsplit(_sep, 1)[0]
        if _dir and _dir not in sys.path:
            sys.path.insert(0, _dir)
except Exception:
    pass

try:
    from studiobridge.device.assets import (
        _sb_core as core,
    )
    from studiobridge.device.assets import (
        _sb_json as json_codec,
    )
    from studiobridge.device.assets import (
        _sb_wire as wire,
    )
except ImportError:
    import _sb_core as core  # type: ignore
    import _sb_json as json_codec  # type: ignore
    import _sb_wire as wire  # type: ignore

# Global runtime state
dispatcher: Any = None
reassembler: Any = None


def _send_sysex(data):
    """Send raw SysEx byte sequence via FL Studio device API."""
    try:
        import device  # type: ignore

        device.midiOutSysex(data)
    except Exception as exc:
        if dispatcher:
            dispatcher.log_ring.append("ERROR", f"device.midiOutSysex failed: {exc}")


def _send_response(sid, mid, resp_dict):
    """Serialize, chunk, and send a ResponseEnvelope to FL Studio output port."""
    try:
        payload = json_codec.dumps(resp_dict).encode("ascii")
        max_chunk = MAX_FRAME - wire.FRAME_OVERHEAD
        chunks = wire.chunk_payload(payload, max_chunk_size=max_chunk)
        ccnt = len(chunks)
        for cidx, chunk in enumerate(chunks):
            frame_bytes = wire.encode_frame(
                wire.KIND_RES,
                wire.FLAG_ENC_JSON,
                sid,
                mid,
                cidx,
                ccnt,
                chunk,
                max_frame_size=MAX_FRAME,
            )
            _send_sysex(frame_bytes)
    except Exception as exc:
        if dispatcher:
            dispatcher.log_ring.append("ERROR", f"Failed to send response: {exc}")


def OnInit():
    """FL Studio controller script initialization."""
    global dispatcher, reassembler
    try:
        dispatcher = core.Dispatcher(
            build_id=BUILD_ID,
            secret=SECRET,
            auth_alg=AUTH_ALG,
            port_root=PORT_ROOT,
            max_frame=MAX_FRAME,
            budget_ms=BUDGET_MS,
            budget_calls=BUDGET_CALLS,
            unsafe=UNSAFE,
        )
        reassembler = wire.WireReassembler(max_messages=16)
        dispatcher.log_ring.console_print(
            f"StudioBridge initialized (build={BUILD_ID}, "
            f"sid={dispatcher.session.sid}, fp={dispatcher.session.fp})",
            force=True,
        )
    except Exception as exc:
        with contextlib.suppress(Exception):
            print(f"StudioBridge OnInit fatal exception: {exc}")


def OnDeInit():
    """FL Studio controller script teardown."""
    global dispatcher
    try:
        if dispatcher:
            dispatcher.idle_queue.clear()
            dispatcher.log_ring.console_print("StudioBridge script unloaded", force=True)
    except Exception:
        pass


def OnSysEx(event):
    """SysEx message handler."""
    global dispatcher, reassembler
    try:
        raw = getattr(event, "sysex", None)
        if raw is None:
            return

        if not isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw)

        # Check magic prefix to identify StudioBridge frames
        is_sb = (
            len(raw) >= 5
            and raw[0] == 0xF0
            and raw[1] == 0x7D
            and raw[2] == 0x53
            and raw[3] == 0x42
            and raw[4] == 0x01
        )
        if not is_sb:
            return

        # Mark handled so FL does not process internal StudioBridge frames
        event.handled = True

        frame = wire.decode_frame(raw)
        if frame is None:
            if dispatcher:
                dispatcher.log_ring.append("WARN", f"Dropped corrupted frame ({len(raw)} bytes)")
            return

        assembled_payload = reassembler.add_chunk(frame)
        if assembled_payload is None:
            return  # Waiting for more chunks

        sid = frame["sid"]
        mid = frame["mid"]
        kind = frame["kind"]

        # Control frames
        if kind == wire.KIND_CTL:
            try:
                ctl_obj = json_codec.loads(assembled_payload)
            except Exception:
                return
            if isinstance(ctl_obj, dict) and ctl_obj.get("c") == "ping":
                pong_payload = json_codec.dumps({"c": "pong", "mid": mid}).encode("ascii")
                pong_frame = wire.encode_frame(
                    wire.KIND_CTL,
                    0,
                    sid,
                    mid,
                    0,
                    1,
                    pong_payload,
                    max_frame_size=MAX_FRAME,
                )
                _send_sysex(pong_frame)
            return

        # Request frames
        if kind == wire.KIND_REQ:
            resp = dispatcher.dispatch(frame, assembled_payload)
            if resp is not None:
                _send_response(sid, mid, resp)

    except Exception as exc:
        if dispatcher:
            dispatcher.log_ring.append("ERROR", f"OnSysEx exception: {exc}")


def OnIdle():
    """FL Studio idle event loop callback."""
    global dispatcher
    try:
        if dispatcher:
            dispatcher.on_idle(_send_response)
    except Exception as exc:
        if dispatcher:
            dispatcher.log_ring.append("ERROR", f"OnIdle exception: {exc}")


def OnRefresh(flags):
    """FL Studio refresh callback."""
    pass


def OnProjectLoad(status):
    """FL Studio project load callback."""
    global dispatcher
    try:
        if dispatcher:
            dispatcher.on_project_load(status)
    except Exception:
        pass
