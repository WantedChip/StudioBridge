"""Comprehensive unit tests for DeviceEmulator and device script wire protocol conformance.

Verifies end-to-end SysEx message exchange, authentication, budgets, error wrapping,
and sandbox enforcement per [DEV-10]..[DEV-30].
"""

from __future__ import annotations

import json
import pathlib

import pytest

from studiobridge.device.emulator.mock_fl import FORBIDDEN_MODULES
from studiobridge.device.emulator.runner import DeviceEmulator
from studiobridge.device.generator import DeviceScriptGenerator
from studiobridge.wire.auth import sign_request
from studiobridge.wire.chunk import Reassembler
from studiobridge.wire.envelope import ControlEnvelope, RequestEnvelope, ResponseEnvelope
from studiobridge.wire.frame import Frame, FrameKind, decode_frame, encode_frame


@pytest.fixture
def secret() -> str:
    return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def multi_file_bundle(tmp_path: pathlib.Path, secret: str) -> pathlib.Path:
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="1.0.0",
        secret=secret,
        budget_ms=10,
        budget_calls=10,
    )
    bundle_dir = tmp_path / "bundle"
    gen.generate_multi_file(bundle_dir)
    return bundle_dir


@pytest.fixture
def single_file_script(tmp_path: pathlib.Path, secret: str) -> pathlib.Path:
    gen = DeviceScriptGenerator(
        device_name="TestDevice",
        port_root="TestDevice",
        build_id="1.0.0",
        secret=secret,
        budget_ms=10,
        budget_calls=10,
    )
    script_path = tmp_path / "device_TestDevice.py"
    gen.generate_single_file(script_path)
    return script_path


def _send_and_get_response(
    emulator: DeviceEmulator,
    req_env: RequestEnvelope,
    sid: int,
    mid: int,
) -> ResponseEnvelope:
    """Helper to serialize a RequestEnvelope, send via SysEx, and decode ResponseEnvelope."""
    payload = req_env.to_json()
    frame_bytes = encode_frame(
        Frame(
            kind=FrameKind.REQ,
            flags=0,
            sid=sid,
            mid=mid,
            cidx=0,
            ccnt=1,
            payload=payload,
        )
    )
    handled = emulator.send_sysex(frame_bytes)
    assert handled is True

    sent_frames = emulator.get_sent_sysex()
    assert len(sent_frames) >= 1
    emulator.clear_sent_sysex()

    resp_payload = None
    reassembler = Reassembler()
    for frame_bytes in sent_frames:
        frame = decode_frame(frame_bytes)
        assert frame.kind == FrameKind.RES
        res = reassembler.feed(frame)
        if res is not None:
            resp_payload = res
    assert resp_payload is not None
    return ResponseEnvelope.from_json(resp_payload)


def test_vector_1_conformance(multi_file_bundle: pathlib.Path) -> None:
    """Verify Vector 1 exact byte sequence conformance inside the emulator."""
    # Official Vector 1 byte sequence (REQ, session 0, MID 1, payload {"op":"ping"}, CRC 0x2017)
    vector_1_hex = (
        "F0 7D 53 42 01 01 00 00 00 00 00 01 00 00 00 01 00 0D "
        "7B 22 6F 70 22 3A 22 70 69 6E 67 22 7D 00 40 17 F7"
    )
    raw_bytes = bytes.fromhex(vector_1_hex)

    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        handled = em.send_sysex(raw_bytes)
        assert handled is True

        sent = em.get_sent_sysex()
        assert len(sent) == 1
        resp_frame = decode_frame(sent[0])
        assert resp_frame.kind == FrameKind.RES
        assert resp_frame.sid == 0
        assert resp_frame.mid == 1

        raw_p = resp_frame.payload
        payload_bytes = raw_p.encode("ascii") if isinstance(raw_p, str) else bytes(raw_p)
        payload_obj = json.loads(payload_bytes)
        assert payload_obj["ok"] is True
        assert payload_obj["r"]["pong"] is True


def test_ctl_ping_pong(multi_file_bundle: pathlib.Path) -> None:
    """Verify CTL ping generates CTL pong control frame."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        ctl_ping = ControlEnvelope.ping(mid=42)
        frame_bytes = encode_frame(
            Frame(
                kind=FrameKind.CTL,
                sid=100,
                mid=42,
                cidx=0,
                ccnt=1,
                payload=ctl_ping.to_json(),
            )
        )
        handled = em.send_sysex(frame_bytes)
        assert handled is True

        sent = em.get_sent_sysex()
        assert len(sent) == 1
        resp_frame = decode_frame(sent[0])
        assert resp_frame.kind == FrameKind.CTL
        assert resp_frame.mid == 42
        raw_ctl = resp_frame.payload
        ctl_bytes = raw_ctl.encode("ascii") if isinstance(raw_ctl, str) else bytes(raw_ctl)
        ctl_res = json.loads(ctl_bytes)
        assert ctl_res["c"] == "pong"
        assert ctl_res["mid"] == 42


def test_hello_and_probe_operations(multi_file_bundle: pathlib.Path) -> None:
    """Verify hello and probe query operations."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        # 1. Hello handshake
        hello_req = RequestEnvelope(op="hello")
        res_hello = _send_and_get_response(em, hello_req, sid=0, mid=2)
        assert res_hello.ok is True
        assert res_hello.r["device"]["build"] == "1.0.0"
        assert res_hello.r["device"]["port_root"] == "TestDevice"
        assert res_hello.r["fl"]["api_version"] == 44

        # 2. Probe operation
        probe_req = RequestEnvelope(op="probe")
        res_probe = _send_and_get_response(em, probe_req, sid=0, mid=3)
        assert res_probe.ok is True
        assert res_probe.r["ctx"] == "controller"
        assert "imports" in res_probe.r
        assert res_probe.r["fl"]["api"] == 44


def test_authenticated_calls_and_verified_writes(
    multi_file_bundle: pathlib.Path, secret: str
) -> None:
    """Verify authenticated API calls, read-backs, and state mutation."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore

        # 1. Read call: mixer.getTrackVolume(0) -> default 0.8
        req_read = RequestEnvelope(op="call", args={"fn": "mixer.getTrackVolume", "a": [0]})
        sign_request(secret, req_read)
        res_read = _send_and_get_response(em, req_read, sid=sid, mid=10)
        assert res_read.ok is True
        assert res_read.r == 0.8

        # 2. Mutating call with verified read-back: mixer.setTrackVolume(1, 0.65)
        req_write = RequestEnvelope(
            op="call",
            args={"fn": "mixer.setTrackVolume", "a": [1, 0.65]},
            opts=RequestEnvelope.from_dict({"op": "call", "opts": {"verify": "readback"}}).opts,
        )
        sign_request(secret, req_write)
        res_write = _send_and_get_response(em, req_write, sid=sid, mid=11)
        assert res_write.ok is True
        assert res_write.rb == 0.65
        # Verify actual mock mixer track was mutated
        assert em.fl.mixer_tracks[1]["volume"] == 0.65

        # 3. Read call on transport: transport.isPlaying() -> False
        req_trans = RequestEnvelope(op="call", args={"fn": "transport.isPlaying", "a": []})
        sign_request(secret, req_trans)
        res_trans = _send_and_get_response(em, req_trans, sid=sid, mid=12)
        assert res_trans.ok is True
        assert res_trans.r is False


def test_preconditions_and_fingerprint_guard(multi_file_bundle: pathlib.Path, secret: str) -> None:
    """Verify opts.expect precondition and session fingerprint checks."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore
        current_fp = em.script_mod.dispatcher.session.fp  # type: ignore

        # 1. Matching fingerprint succeeds
        req_ok = RequestEnvelope(
            op="call",
            args={"fn": "mixer.getTrackVolume", "a": [0]},
            opts=RequestEnvelope.from_dict({"op": "call", "opts": {"fp": current_fp}}).opts,
        )
        sign_request(secret, req_ok)
        res_ok = _send_and_get_response(em, req_ok, sid=sid, mid=20)
        assert res_ok.ok is True

        # 2. Stale fingerprint fails with E_STALE
        req_stale = RequestEnvelope(
            op="call",
            args={"fn": "mixer.getTrackVolume", "a": [0]},
            opts=RequestEnvelope.from_dict({"op": "call", "opts": {"fp": "stale_fp_123"}}).opts,
        )
        sign_request(secret, req_stale)
        res_stale = _send_and_get_response(em, req_stale, sid=sid, mid=21)
        assert res_stale.ok is False
        assert res_stale.code == "E_STALE"

        # 3. Matching precondition succeeds
        req_prec_ok = RequestEnvelope(
            op="call",
            args={"fn": "mixer.getTrackVolume", "a": [0]},
            opts=RequestEnvelope.from_dict(
                {
                    "op": "call",
                    "opts": {
                        "expect": {"getter": "mixer.getTrackVolume", "args": [0], "value": 0.8}
                    },
                }
            ).opts,
        )
        sign_request(secret, req_prec_ok)
        res_prec_ok = _send_and_get_response(em, req_prec_ok, sid=sid, mid=22)
        assert res_prec_ok.ok is True

        # 4. Mismatched precondition fails with E_PRECONDITION
        req_prec_fail = RequestEnvelope(
            op="call",
            args={"fn": "mixer.getTrackVolume", "a": [0]},
            opts=RequestEnvelope.from_dict(
                {
                    "op": "call",
                    "opts": {
                        "expect": {"getter": "mixer.getTrackVolume", "args": [0], "value": 0.2}
                    },
                }
            ).opts,
        )
        sign_request(secret, req_prec_fail)
        res_prec_fail = _send_and_get_response(em, req_prec_fail, sid=sid, mid=23)
        assert res_prec_fail.ok is False
        assert res_prec_fail.code == "E_PRECONDITION"


def test_auth_and_allowlist_errors(multi_file_bundle: pathlib.Path, secret: str) -> None:
    """Verify E_AUTH on bad signature, E_UNAVAILABLE on unknown, and E_ARGS on bad args."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore

        # 1. Bad authentication signature -> E_AUTH
        req_bad_auth = RequestEnvelope(
            op="call",
            auth="bad_signature_hex",
            args={"fn": "mixer.getTrackVolume", "a": [0]},
        )
        res_bad_auth = _send_and_get_response(em, req_bad_auth, sid=sid, mid=30)
        assert res_bad_auth.ok is False
        assert res_bad_auth.code == "E_AUTH"

        # 2. Unknown function -> E_UNAVAILABLE
        req_unknown = RequestEnvelope(op="call", args={"fn": "nonexistent.function", "a": []})
        sign_request(secret, req_unknown)
        res_unknown = _send_and_get_response(em, req_unknown, sid=sid, mid=31)
        assert res_unknown.ok is False
        assert res_unknown.code == "E_UNAVAILABLE"

        # 3. Argument validation error (track index 150 > 126 max) -> E_ARGS
        req_args = RequestEnvelope(op="call", args={"fn": "mixer.getTrackVolume", "a": [150]})
        sign_request(secret, req_args)
        res_args = _send_and_get_response(em, req_args, sid=sid, mid=32)
        assert res_args.ok is False
        assert res_args.code == "E_ARGS"


def test_error_wrapping_fl_exceptions(multi_file_bundle: pathlib.Path, secret: str) -> None:
    """Verify that FL API exceptions are converted to structured E_FL errors per [DEV-10]."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore

        # Inject an exception into mock mixer
        def _failing_getTrackVolume(index: int) -> float:
            raise RuntimeError("Simulated FL hardware fault")

        em.fl.mixer_tracks[0]["failing"] = True
        import mixer  # type: ignore

        mixer.getTrackVolume = _failing_getTrackVolume  # type: ignore

        req = RequestEnvelope(op="call", args={"fn": "mixer.getTrackVolume", "a": [0]})
        sign_request(secret, req)
        res = _send_and_get_response(em, req, sid=sid, mid=40)

        # Must return ok=False with code E_FL and not crash FL
        assert res.ok is False
        assert res.code == "E_FL"
        assert "RuntimeError" in (res.err or "")


def test_batch_execution_and_budgeting(multi_file_bundle: pathlib.Path, secret: str) -> None:
    """Verify inline batch execution, idle scheduling, and budget interruption per [DEV-11]."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore

        # 1. Small inline batch (4 calls <= max_inline_calls 8)
        small_calls = [{"fn": "mixer.getTrackVolume", "a": [i]} for i in range(4)]
        req_small = RequestEnvelope(op="batch", args={"calls": small_calls})
        sign_request(secret, req_small)
        res_small = _send_and_get_response(em, req_small, sid=sid, mid=50)
        assert res_small.ok is True
        assert res_small.r["count"] == 4

        # 2. Large batch (25 calls > max_inline_calls 8) with budget_calls = 10 per tick
        large_calls = [{"fn": "mixer.getTrackVolume", "a": [i]} for i in range(25)]
        req_large = RequestEnvelope(op="batch", args={"calls": large_calls})
        sign_request(secret, req_large)

        frame_bytes = encode_frame(
            Frame(
                kind=FrameKind.REQ,
                sid=sid,
                mid=51,
                cidx=0,
                ccnt=1,
                payload=req_large.to_json(),
            )
        )
        handled = em.send_sysex(frame_bytes)
        assert handled is True

        # Initially queued for OnIdle ticks: no response sent yet
        assert len(em.get_sent_sysex()) == 0
        assert len(em.script_mod.dispatcher.idle_queue) == 1  # type: ignore

        # Tick 1: processes 10 calls (idx: 0 -> 10)
        em.idle(1)
        assert len(em.get_sent_sysex()) == 0
        assert em.script_mod.dispatcher.idle_queue[0]["idx"] == 10  # type: ignore

        # Tick 2: processes 10 calls (idx: 10 -> 20)
        em.idle(1)
        assert len(em.get_sent_sysex()) == 0
        assert em.script_mod.dispatcher.idle_queue[0]["idx"] == 20  # type: ignore

        # Tick 3: processes remaining 5 calls (idx: 20 -> 25) -> job finishes!
        em.idle(1)
        sent = em.get_sent_sysex()
        assert len(sent) >= 1
        reassembler = Reassembler()
        full_payload = None
        for frame_bytes in sent:
            res = reassembler.feed(decode_frame(frame_bytes))
            if res is not None:
                full_payload = res
        assert full_payload is not None
        res_large = ResponseEnvelope.from_json(full_payload)
        assert res_large.ok is True
        assert res_large.r["count"] == 25
        assert len(res_large.r["results"]) == 25


def test_panic_clears_queue(multi_file_bundle: pathlib.Path, secret: str) -> None:
    """Verify panic operation clears running batch work."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        sid = em.script_mod.dispatcher.session.sid  # type: ignore

        # Queue a large batch
        large_calls = [{"fn": "mixer.getTrackVolume", "a": [i]} for i in range(50)]
        req_batch = RequestEnvelope(op="batch", args={"calls": large_calls})
        sign_request(secret, req_batch)
        em.send_sysex(
            encode_frame(
                Frame(
                    kind=FrameKind.REQ,
                    sid=sid,
                    mid=60,
                    cidx=0,
                    ccnt=1,
                    payload=req_batch.to_json(),
                )
            )
        )
        assert len(em.script_mod.dispatcher.idle_queue) == 1  # type: ignore

        # Send panic
        req_panic = RequestEnvelope(op="panic")
        sign_request(secret, req_panic)
        res_panic = _send_and_get_response(em, req_panic, sid=sid, mid=61)
        assert res_panic.ok is True
        assert res_panic.r["cleared"] == 1
        assert len(em.script_mod.dispatcher.idle_queue) == 0  # type: ignore


def test_sandbox_import_blocker(multi_file_bundle: pathlib.Path) -> None:
    """Verify importing forbidden modules raises ImportError inside emulator [DEV-30]."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as _em:
        for mod_name in FORBIDDEN_MODULES:
            with pytest.raises(ImportError) as exc_info:
                __import__(mod_name)
            assert "blocked by FL Studio" in str(exc_info.value)


def test_corrupted_frame_handling(multi_file_bundle: pathlib.Path) -> None:
    """Verify that malformed or corrupted frames are silently dropped without crashing."""
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em:
        # Corrupt CRC
        bad_crc_bytes = bytes.fromhex(
            "F0 7D 53 42 01 01 00 00 00 00 00 01 00 00 00 01 00 0D "
            "7B 22 6F 70 22 3A 22 70 69 6E 67 22 7D 00 7F 7F F7"
        )
        handled = em.send_sysex(bad_crc_bytes)
        assert handled is True  # handled for SB frames so FL ignores it
        assert len(em.get_sent_sysex()) == 0  # but no response generated

        # Non-SB message
        non_sb_bytes = bytes.fromhex("F0 00 20 29 00 01 F7")
        handled_non_sb = em.send_sysex(non_sb_bytes)
        assert handled_non_sb is False  # not handled, left for FL


def test_single_file_and_multi_file_equivalence(
    multi_file_bundle: pathlib.Path, single_file_script: pathlib.Path, secret: str
) -> None:
    """Verify single-file inlined bundle produces identical behavior to multi-file layout."""
    # Run multi-file bundle
    with DeviceEmulator(script_dir=multi_file_bundle, device_name="TestDevice") as em_multi:
        # 1. Ping test
        req_ping = RequestEnvelope(op="ping")
        res_m_ping = _send_and_get_response(em_multi, req_ping, sid=0, mid=1)

        # 2. Call test: mixer.getTrackVolume(0)
        req_call = RequestEnvelope(op="call", args={"fn": "mixer.getTrackVolume", "a": [0]})
        sign_request(secret, req_call)
        assert em_multi.script_mod is not None
        res_m_call = _send_and_get_response(
            em_multi,
            req_call,
            sid=em_multi.script_mod.dispatcher.session.sid,
            mid=2,  # type: ignore
        )

    # Run single-file inlined script
    with DeviceEmulator(script_file=single_file_script, device_name="TestDevice") as em_single:
        # 1. Ping test
        req_ping = RequestEnvelope(op="ping")
        res_s_ping = _send_and_get_response(em_single, req_ping, sid=0, mid=1)

        # 2. Call test: mixer.getTrackVolume(0)
        req_call = RequestEnvelope(op="call", args={"fn": "mixer.getTrackVolume", "a": [0]})
        sign_request(secret, req_call)
        assert em_single.script_mod is not None
        res_s_call = _send_and_get_response(
            em_single,
            req_call,
            sid=em_single.script_mod.dispatcher.session.sid,
            mid=2,  # type: ignore
        )

    assert res_m_ping.ok is True and res_s_ping.ok is True
    assert res_m_ping.r["pong"] == res_s_ping.r["pong"]
    assert res_m_call.ok is True and res_s_call.ok is True
    assert res_m_call.r == res_s_call.r == 0.8
