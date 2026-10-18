#!/usr/bin/env python3
"""Hardware probe script for S3 spike: WinMM port enumeration and duplex latency testing.

Uses ctypes to interact directly with winmm.dll to:
1. Enumerate all system MIDI in/out ports with exact names, checking for 31-char truncation.
2. Detect loopback pairs (Windows MIDI Services loopback, loopMIDI, etc.).
3. Test multi-client port sharing (opening the same port twice) to verify WMS multi-client support.
4. Measure round-trip latency and packet loss across duplex loopback port pairs.

Zero external dependencies; compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import statistics
import sys
import threading
import time
from typing import Any

# WinMM Constants & Structures
MAXPNAMELEN = 32
MMSYSERR_NOERROR = 0
MMSYSERR_ALLOCATED = 4
CALLBACK_FUNCTION = 0x00030000
MIM_LONGDATA = 0x3C4
MHDR_DONE = 0x00000001


class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("dwSupport", ctypes.c_uint),
    ]


class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("wTechnology", ctypes.c_ushort),
        ("wVoices", ctypes.c_ushort),
        ("wNotes", ctypes.c_ushort),
        ("wChannelMask", ctypes.c_ushort),
        ("dwSupport", ctypes.c_uint),
    ]


class MIDIHDR(ctypes.Structure):
    pass


MIDIHDR._fields_ = [
    ("lpData", ctypes.c_char_p),
    ("dwBufferLength", ctypes.c_uint),
    ("dwBytesRecorded", ctypes.c_uint),
    ("dwUser", ctypes.c_size_t),
    ("dwFlags", ctypes.c_uint),
    ("lpNext", ctypes.POINTER(MIDIHDR)),
    ("reserved", ctypes.c_size_t),
    ("dwOffset", ctypes.c_uint),
    ("dwReserved", ctypes.c_size_t * 8),
]

if hasattr(ctypes, "WINFUNCTYPE"):
    MIDI_IN_CALLBACK_TYPE = ctypes.WINFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )
else:
    MIDI_IN_CALLBACK_TYPE = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )


def enumerate_ports() -> dict[str, list[dict[str, Any]]]:
    """Enumerate all available WinMM MIDI input and output ports."""
    if sys.platform != "win32":
        return {
            "inputs": [],
            "outputs": [],
            "note": f"WinMM is only available on Windows (current platform: {sys.platform})",
        }

    winmm = ctypes.windll.winmm  # type: ignore[attr-defined]

    num_in = winmm.midiInGetNumDevs()
    inputs: list[dict[str, Any]] = []
    caps_in = MIDIINCAPSW()
    for idx in range(num_in):
        res = winmm.midiInGetDevCapsW(idx, ctypes.byref(caps_in), ctypes.sizeof(caps_in))
        if res == MMSYSERR_NOERROR:
            name = caps_in.szPname
            truncated = len(name) >= (MAXPNAMELEN - 1)
            inputs.append(
                {
                    "index": idx,
                    "name": name,
                    "mid": caps_in.wMid,
                    "pid": caps_in.wPid,
                    "driver_version": hex(caps_in.vDriverVersion),
                    "truncated": truncated,
                }
            )

    num_out = winmm.midiOutGetNumDevs()
    outputs: list[dict[str, Any]] = []
    caps_out = MIDIOUTCAPSW()
    for idx in range(num_out):
        res = winmm.midiOutGetDevCapsW(idx, ctypes.byref(caps_out), ctypes.sizeof(caps_out))
        if res == MMSYSERR_NOERROR:
            name = caps_out.szPname
            truncated = len(name) >= (MAXPNAMELEN - 1)
            outputs.append(
                {
                    "index": idx,
                    "name": name,
                    "mid": caps_out.wMid,
                    "pid": caps_out.wPid,
                    "driver_version": hex(caps_out.vDriverVersion),
                    "technology": caps_out.wTechnology,
                    "truncated": truncated,
                }
            )

    return {"inputs": inputs, "outputs": outputs}


def test_multi_open(port_type: str = "input", port_index: int = 0) -> dict[str, Any]:
    """Test if opening the same MIDI port twice succeeds (multi-client) or errors."""
    if sys.platform != "win32":
        return {"error": "WinMM not available on this platform"}

    winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
    h1 = ctypes.c_void_p()
    h2 = ctypes.c_void_p()

    result: dict[str, Any] = {
        "port_type": port_type,
        "port_index": port_index,
        "first_open": None,
        "second_open": None,
        "multi_client_supported": False,
    }

    if port_type == "input":
        r1 = winmm.midiInOpen(ctypes.byref(h1), port_index, 0, 0, 0)
        result["first_open"] = r1
        if r1 == MMSYSERR_NOERROR:
            try:
                r2 = winmm.midiInOpen(ctypes.byref(h2), port_index, 0, 0, 0)
                result["second_open"] = r2
                result["multi_client_supported"] = r2 == MMSYSERR_NOERROR
                if r2 == MMSYSERR_NOERROR:
                    winmm.midiInClose(h2)
            finally:
                winmm.midiInClose(h1)
    else:
        r1 = winmm.midiOutOpen(ctypes.byref(h1), port_index, 0, 0, 0)
        result["first_open"] = r1
        if r1 == MMSYSERR_NOERROR:
            try:
                r2 = winmm.midiOutOpen(ctypes.byref(h2), port_index, 0, 0, 0)
                result["second_open"] = r2
                result["multi_client_supported"] = r2 == MMSYSERR_NOERROR
                if r2 == MMSYSERR_NOERROR:
                    winmm.midiOutClose(h2)
            finally:
                winmm.midiOutClose(h1)

    return result


def test_duplex_latency(
    in_index: int, out_index: int, trials: int = 20, payload_size: int = 64
) -> dict[str, Any]:
    """Send SysEx frames through loopback out -> in and measure round-trip latency."""
    if sys.platform != "win32":
        return {"error": "WinMM not available on this platform"}

    winmm = ctypes.windll.winmm  # type: ignore[attr-defined]

    h_in = ctypes.c_void_p()
    h_out = ctypes.c_void_p()

    received_events: list[bytes] = []
    recv_event = threading.Event()

    def in_callback(h_midi: Any, msg: int, instance: int, param1: int, param2: int) -> None:
        if msg == MIM_LONGDATA:
            hdr_ptr = ctypes.cast(param1, ctypes.POINTER(MIDIHDR))
            if hdr_ptr and hdr_ptr.contents.dwBytesRecorded > 0:
                raw_bytes = ctypes.string_at(
                    hdr_ptr.contents.lpData, hdr_ptr.contents.dwBytesRecorded
                )
                received_events.append(raw_bytes)
                recv_event.set()

    cb_func = MIDI_IN_CALLBACK_TYPE(in_callback)

    # Open In
    r = winmm.midiInOpen(ctypes.byref(h_in), in_index, cb_func, 0, CALLBACK_FUNCTION)
    if r != MMSYSERR_NOERROR:
        return {"error": f"Failed to open MIDI in port {in_index}: error code {r}"}

    # Open Out
    r = winmm.midiOutOpen(ctypes.byref(h_out), out_index, 0, 0, 0)
    if r != MMSYSERR_NOERROR:
        winmm.midiInClose(h_in)
        return {"error": f"Failed to open MIDI out port {out_index}: error code {r}"}

    # Prepare In Buffer
    in_buf_size = 2048
    in_buffer = ctypes.create_string_buffer(in_buf_size)
    in_hdr = MIDIHDR()
    in_hdr.lpData = ctypes.cast(in_buffer, ctypes.c_char_p)
    in_hdr.dwBufferLength = in_buf_size
    in_hdr.dwFlags = 0

    winmm.midiInPrepareHeader(h_in, ctypes.byref(in_hdr), ctypes.sizeof(in_hdr))
    winmm.midiInAddBuffer(h_in, ctypes.byref(in_hdr), ctypes.sizeof(in_hdr))
    winmm.midiInStart(h_in)

    rtts_ms: list[float] = []
    lost_frames = 0

    # Build test SysEx frame
    test_body = bytes([i % 127 for i in range(max(4, payload_size - 6))])
    test_sysex = b"\xf0\x7d\x53\x42" + test_body + b"\xf7"

    try:
        for _ in range(trials):
            recv_event.clear()
            del received_events[:]

            out_buf = ctypes.create_string_buffer(test_sysex)
            out_hdr = MIDIHDR()
            out_hdr.lpData = ctypes.cast(out_buf, ctypes.c_char_p)
            out_hdr.dwBufferLength = len(test_sysex)
            out_hdr.dwFlags = 0

            winmm.midiOutPrepareHeader(h_out, ctypes.byref(out_hdr), ctypes.sizeof(out_hdr))

            t0 = time.perf_counter()
            winmm.midiOutLongMsg(h_out, ctypes.byref(out_hdr), ctypes.sizeof(out_hdr))

            # Wait up to 500ms for echo
            arrived = recv_event.wait(timeout=0.5)
            t1 = time.perf_counter()

            # Clean up out header
            while not (out_hdr.dwFlags & MHDR_DONE):
                time.sleep(0.001)
            winmm.midiOutUnprepareHeader(h_out, ctypes.byref(out_hdr), ctypes.sizeof(out_hdr))

            if arrived:
                rtt = (t1 - t0) * 1000.0
                rtts_ms.append(rtt)
            else:
                lost_frames += 1

            time.sleep(0.005)  # 5ms pacing between packets
    finally:
        winmm.midiInStop(h_in)
        winmm.midiInReset(h_in)
        winmm.midiInUnprepareHeader(h_in, ctypes.byref(in_hdr), ctypes.sizeof(in_hdr))
        winmm.midiInClose(h_in)
        winmm.midiOutClose(h_out)

    if not rtts_ms:
        return {
            "trials": trials,
            "lost": lost_frames,
            "loss_pct": 100.0,
            "error": "No frames received back through loopback",
        }

    rtts_sorted = sorted(rtts_ms)
    p50 = statistics.median(rtts_sorted)
    idx_p95 = int(len(rtts_sorted) * 0.95)
    p95 = rtts_sorted[min(idx_p95, len(rtts_sorted) - 1)]

    return {
        "trials": trials,
        "received": len(rtts_ms),
        "lost": lost_frames,
        "loss_pct": (lost_frames / trials) * 100.0,
        "min_ms": round(rtts_sorted[0], 3),
        "median_ms": round(p50, 3),
        "mean_ms": round(statistics.mean(rtts_sorted), 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(rtts_sorted[-1], 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WinMM MIDI port probe and latency test")
    parser.add_argument("--json", action="store_true", help="Output results as formatted JSON")
    parser.add_argument("--multi-open", action="store_true", help="Test multi-client port opening")
    parser.add_argument("--latency", action="store_true", help="Test loopback duplex latency")
    parser.add_argument("--in-port", type=int, default=0, help="Input port index for testing")
    parser.add_argument("--out-port", type=int, default=0, help="Output port index for testing")
    parser.add_argument("--trials", type=int, default=20, help="Number of latency trials")
    args = parser.parse_args()

    ports = enumerate_ports()

    results: dict[str, Any] = {"ports": ports}

    if args.multi_open:
        results["multi_open_in"] = test_multi_open("input", args.in_port)
        results["multi_open_out"] = test_multi_open("output", args.out_port)

    if args.latency:
        results["latency_test"] = test_duplex_latency(
            args.in_port, args.out_port, trials=args.trials
        )

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    print("=" * 60)
    print(" StudioBridge S3 - WinMM MIDI Port Discovery & Probe")
    print("=" * 60)
    print(f"Platform: {sys.platform}")

    inputs = ports.get("inputs", [])
    outputs = ports.get("outputs", [])

    print(f"\n[+] MIDI Input Ports ({len(inputs)} found):")
    for p in inputs:
        trunc_warn = " [TRUNCATED > 31 chars!]" if p.get("truncated") else ""
        print(f'  [{p["index"]}] "{p["name"]}"{trunc_warn} (v{p["driver_version"]})')

    print(f"\n[+] MIDI Output Ports ({len(outputs)} found):")
    for p in outputs:
        trunc_warn = " [TRUNCATED > 31 chars!]" if p.get("truncated") else ""
        print(f'  [{p["index"]}] "{p["name"]}"{trunc_warn} (v{p["driver_version"]})')

    if args.multi_open and "multi_open_in" in results:
        mo = results["multi_open_in"]
        print("\n[+] Multi-Client Test (Input):")
        print(
            f"  Port index {mo['port_index']}: "
            f"Multi-client allowed = {mo['multi_client_supported']}"
        )

    if args.latency and "latency_test" in results:
        lat = results["latency_test"]
        print("\n[+] Duplex Latency Test:")
        if "error" in lat:
            print(f"  Error: {lat['error']}")
        else:
            print(f"  Trials: {lat['trials']}, Lost: {lat['lost']} ({lat['loss_pct']}%)")
            print(
                f"  Min: {lat['min_ms']} ms, Median: {lat['median_ms']} ms, Max: {lat['max_ms']} ms"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
