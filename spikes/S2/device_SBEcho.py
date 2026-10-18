# name=SBEcho
"""Hardware probe controller script for S2 spike: idle cadence and SysEx echo.

Measures OnIdle call rates across different window and playback states,
and echoes StudioBridge SysEx frames back to sender verbatim for latency
and packet loss measurement.
"""

from __future__ import annotations

import time
from typing import Any

try:
    import device
except ImportError:
    device = None

_last = [0.0]
_n = [0]
_d: list[float] = []
_t0 = [0.0]


def _now() -> float:
    return time.time()


def OnInit() -> None:
    print("[SBE] SBEcho controller initialized")


def OnIdle() -> None:
    try:
        t = _now()
        if _last[0]:
            _d.append(t - _last[0])
        _last[0] = t
        if _t0[0] == 0.0:
            _t0[0] = t
        if t - _t0[0] >= 10.0 and _d:
            s = sorted(_d)
            duration = t - _t0[0]
            hz = len(s) / duration if duration > 0 else 0.0
            print(
                f"[SBE] idle: n={len(s)} hz={hz:.1f} min={s[0]:.4f} "
                f"med={s[len(s) // 2]:.4f} max={s[-1]:.4f}"
            )
            del _d[:]
            _t0[0] = t
    except Exception as e:
        print("[SBE] idle err", type(e).__name__)


def OnSysEx(event: Any) -> None:
    try:
        sysex_raw = getattr(event, "sysex", None)
        if sysex_raw is None:
            return
        data = bytes(sysex_raw)
        # StudioBridge manufacturer + product ID header: F0 7D 53 42 ...
        if len(data) > 4 and data[1] == 0x7D and data[2] == 0x53 and data[3] == 0x42:
            event.handled = True
            if device is not None and hasattr(device, "midiOutSysex"):
                device.midiOutSysex(data)  # echo verbatim
    except Exception as e:
        print("[SBE] sysex err", type(e).__name__)


if __name__ == "__main__":
    OnInit()
    print("[SBE] Running standalone test loop (5 iterations)...")
    for _ in range(5):
        time.sleep(0.01)
        OnIdle()
    print("[SBE] Standalone test loop complete.")
