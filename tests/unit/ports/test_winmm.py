"""Unit and mock integration tests for WinMM ctypes backend and WMS detector [PORT-10..19]."""

import sys
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from studiobridge.core.errors import PortError
from studiobridge.ports.fake import FakeMidiPort
from studiobridge.ports.winmm import (
    MIDIERR_NOTREADY,
    MIDIERR_STILLPLAYING,
    MIM_LONGDATA,
    MMSYSERR_ALLOCATED,
    MMSYSERR_BADDEVICEID,
    MMSYSERR_NODRIVER,
    MMSYSERR_NOERROR,
    MOM_DONE,
    WinMmMidiPort,
    map_winmm_error,
)
from studiobridge.ports.wms import WmsDetector, WmsDiagnostics


@pytest.mark.winmm
def test_winmm_error_code_mapping_allocated() -> None:
    """Verify MMSYSERR_ALLOCATED maps to PortError with multi-client sharing remedy [PORT-19]."""
    err = map_winmm_error(MMSYSERR_ALLOCATED, "midiInOpen")
    assert isinstance(err, PortError)
    assert err.code == "E_ENV_PORT"
    assert err.retryable is True
    assert "MMSYSERR_ALLOCATED" in err.message
    assert "already opened" in err.message
    assert "Windows MIDI Services (WMS) enables multi-client port sharing" in err.remedy


@pytest.mark.winmm
def test_winmm_error_code_mapping_baddeviceid() -> None:
    """Verify MMSYSERR_BADDEVICEID maps to non-retryable PortError with re-enumerate remedy."""
    err = map_winmm_error(MMSYSERR_BADDEVICEID, "midiOutOpen")
    assert isinstance(err, PortError)
    assert err.code == "E_ENV_PORT"
    assert err.retryable is False
    assert "MMSYSERR_BADDEVICEID" in err.message
    assert "Re-enumerate MIDI ports" in err.remedy


@pytest.mark.winmm
def test_winmm_error_code_mapping_nodriver() -> None:
    """Verify MMSYSERR_NODRIVER maps to retryable PortError referencing midisrv."""
    err = map_winmm_error(MMSYSERR_NODRIVER, "midiInOpen")
    assert isinstance(err, PortError)
    assert err.retryable is True
    assert "midisrv" in err.remedy


@pytest.mark.winmm
def test_winmm_error_code_mapping_stillplaying() -> None:
    """Verify MIDIERR_STILLPLAYING maps to PortError with reset remedy."""
    err = map_winmm_error(MIDIERR_STILLPLAYING, "midiOutClose")
    assert isinstance(err, PortError)
    assert err.retryable is True
    assert "Reset MIDI port buffers" in err.remedy


@pytest.mark.winmm
def test_winmm_error_code_mapping_notready() -> None:
    """Verify MIDIERR_NOTREADY maps to retryable PortError with wait remedy."""
    err = map_winmm_error(MIDIERR_NOTREADY, "midiOutLongMsg")
    assert isinstance(err, PortError)
    assert err.retryable is True
    assert "Wait briefly" in err.remedy


@pytest.mark.winmm
def test_winmm_unknown_error_mapping() -> None:
    """Verify unmapped error code returns formatted PortError with diagnostic details."""
    err = map_winmm_error(999, "customAction")
    assert isinstance(err, PortError)
    assert err.code == "E_ENV_PORT"
    assert "999" in err.message
    assert err.details["error_code"] == 999


def _get_struct(ptr: Any) -> Any:
    """Extract underlying ctypes Structure from POINTER or byref CArgObject."""
    return getattr(ptr, "_obj", getattr(ptr, "contents", ptr))


@pytest.mark.winmm
def test_winmm_mock_device_enumeration() -> None:
    """Verify WinMmMidiPort parses enumerated device caps correctly using mock DLL."""
    mock_dll = MagicMock()
    mock_dll.midiInGetNumDevs.return_value = 1
    mock_dll.midiOutGetNumDevs.return_value = 1

    def _mock_in_caps(idx, ptr, sz):
        caps = _get_struct(ptr)
        caps.wMid = 0x0047
        caps.vDriverVersion = (2 << 8) | 1
        caps.szPname = "Mock In Loopback"
        return MMSYSERR_NOERROR

    def _mock_out_caps(idx, ptr, sz):
        caps = _get_struct(ptr)
        caps.wMid = 0x0047
        caps.vDriverVersion = (2 << 8) | 1
        caps.szPname = "Mock Out Loopback"
        return MMSYSERR_NOERROR

    mock_dll.midiInGetDevCapsW.side_effect = _mock_in_caps
    mock_dll.midiOutGetDevCapsW.side_effect = _mock_out_caps

    port = WinMmMidiPort(winmm_dll=mock_dll)
    ports = port.list_ports()

    assert len(ports) == 2
    in_port = next(p for p in ports if p.direction == "in")
    out_port = next(p for p in ports if p.direction == "out")

    assert in_port.name == "Mock In Loopback"
    assert in_port.driver_version == "2.1"
    assert out_port.name == "Mock Out Loopback"


@pytest.mark.winmm
def test_winmm_mock_open_buffer_pool_and_lifecycle() -> None:
    """Verify WinMmMidiPort.open initializes 8 prepared buffers and feeds ring [PORT-13]."""
    mock_dll = MagicMock()
    mock_dll.midiInGetNumDevs.return_value = 1
    mock_dll.midiOutGetNumDevs.return_value = 1

    def _mock_in_caps(idx, ptr, sz):
        _get_struct(ptr).szPname = "Mock Loopback (A)"
        return MMSYSERR_NOERROR

    def _mock_out_caps(idx, ptr, sz):
        _get_struct(ptr).szPname = "Mock Loopback (B)"
        return MMSYSERR_NOERROR

    mock_dll.midiInGetDevCapsW.side_effect = _mock_in_caps
    mock_dll.midiOutGetDevCapsW.side_effect = _mock_out_caps

    captured_in_cb = None
    captured_out_cb = None

    def _mock_in_open(h_ptr, dev_id, cb_ptr, inst, flags):
        nonlocal captured_in_cb
        _get_struct(h_ptr).value = 1001
        captured_in_cb = cb_ptr
        return MMSYSERR_NOERROR

    def _mock_out_open(h_ptr, dev_id, cb_ptr, inst, flags):
        nonlocal captured_out_cb
        _get_struct(h_ptr).value = 2002
        captured_out_cb = cb_ptr
        return MMSYSERR_NOERROR

    mock_dll.midiInOpen.side_effect = _mock_in_open
    mock_dll.midiOutOpen.side_effect = _mock_out_open
    mock_dll.midiInPrepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiInAddBuffer.return_value = MMSYSERR_NOERROR
    mock_dll.midiInStart.return_value = MMSYSERR_NOERROR

    port = WinMmMidiPort(winmm_dll=mock_dll)
    port.open("Mock Loopback (A)", "Mock Loopback (B)", sysex_buf=16384, nbufs=8)

    assert port.is_open
    assert port.in_name == "Mock Loopback (A)"
    assert port.out_name == "Mock Loopback (B)"

    # Assert 8 ring buffers were prepared and added [PORT-14]
    assert mock_dll.midiInPrepareHeader.call_count == 8
    assert mock_dll.midiInAddBuffer.call_count == 8
    assert mock_dll.midiInStart.call_count == 1

    received_msgs: list[bytes] = []
    rx_event = threading.Event()

    def _on_rx(d: bytes) -> None:
        received_msgs.append(d)
        rx_event.set()

    port.on_sysex(_on_rx)

    # Simulate driver sending MIM_LONGDATA to the input callback
    # Pick the first prepared buffer from the pool
    hdr_addr, (buf_raw, hdr) = next(iter(port._in_buffers.items()))
    test_sysex = b"\xf0\x7d\x53\x42\x01\x11\x22\xf7"
    for i, b in enumerate(test_sysex):
        buf_raw[i] = b
    hdr.dwBytesRecorded = len(test_sysex)

    port._in_callback(None, MIM_LONGDATA, 0, hdr_addr, 0)
    assert rx_event.wait(timeout=1.0)
    assert received_msgs == [test_sysex]
    assert port.stats.bytes_recv == len(test_sysex)
    assert port.stats.frames_recv == 1

    # Assert midiInAddBuffer was called again to recycle the buffer [PORT-13]
    assert mock_dll.midiInAddBuffer.call_count == 9

    # Close and verify unprepare and cleanup
    mock_dll.midiInStop.return_value = MMSYSERR_NOERROR
    mock_dll.midiInReset.return_value = MMSYSERR_NOERROR
    mock_dll.midiInUnprepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiInClose.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutReset.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutClose.return_value = MMSYSERR_NOERROR

    port.close()
    assert not port.is_open
    assert mock_dll.midiInUnprepareHeader.call_count == 8
    assert mock_dll.midiInClose.call_count == 1
    assert mock_dll.midiOutClose.call_count == 1


@pytest.mark.winmm
def test_winmm_mock_send_sysex_and_mom_done() -> None:
    """Verify WinMmMidiPort.send_sysex waits on MOM_DONE and unprepares [PORT-15]."""
    mock_dll = MagicMock()
    mock_dll.midiInGetNumDevs.return_value = 1
    mock_dll.midiOutGetNumDevs.return_value = 1

    mock_dll.midiInGetDevCapsW.side_effect = lambda idx, ptr, sz: (
        setattr(_get_struct(ptr), "szPname", "Mock A"),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiOutGetDevCapsW.side_effect = lambda idx, ptr, sz: (
        setattr(_get_struct(ptr), "szPname", "Mock B"),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiInOpen.side_effect = lambda h, d, cb, i, f: (
        setattr(_get_struct(h), "value", 1),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiOutOpen.side_effect = lambda h, d, cb, i, f: (
        setattr(_get_struct(h), "value", 2),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiInPrepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiInAddBuffer.return_value = MMSYSERR_NOERROR
    mock_dll.midiInStart.return_value = MMSYSERR_NOERROR

    mock_dll.midiOutPrepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutUnprepareHeader.return_value = MMSYSERR_NOERROR

    port = WinMmMidiPort(winmm_dll=mock_dll, send_timeout=1.0)
    port.open("Mock A", "Mock B")

    # Simulate driver signaling MOM_DONE upon midiOutLongMsg
    def _mock_out_long_msg(h, ptr, sz):
        # Trigger MOM_DONE asynchronously
        threading.Thread(
            target=lambda: (time.sleep(0.01), port._out_callback(h, MOM_DONE, 0, 0, 0))
        ).start()
        return MMSYSERR_NOERROR

    mock_dll.midiOutLongMsg.side_effect = _mock_out_long_msg

    test_msg = b"\xf0\x7d\x53\x42\x01\x99\xf7"
    port.send_sysex(test_msg)

    assert mock_dll.midiOutPrepareHeader.call_count == 1
    assert mock_dll.midiOutLongMsg.call_count == 1
    assert mock_dll.midiOutUnprepareHeader.call_count == 1
    assert port.stats.bytes_sent == len(test_msg)
    assert port.stats.frames_sent == 1

    port.close()


@pytest.mark.winmm
def test_winmm_mock_send_timeout() -> None:
    """Verify WinMmMidiPort.send_sysex raises E_TIMEOUT and resets port when MOM_DONE times out."""
    mock_dll = MagicMock()
    mock_dll.midiInGetNumDevs.return_value = 1
    mock_dll.midiOutGetNumDevs.return_value = 1
    mock_dll.midiInGetDevCapsW.side_effect = lambda idx, ptr, sz: (
        setattr(_get_struct(ptr), "szPname", "Mock A"),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiOutGetDevCapsW.side_effect = lambda idx, ptr, sz: (
        setattr(_get_struct(ptr), "szPname", "Mock B"),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiInOpen.side_effect = lambda h, d, cb, i, f: (
        setattr(_get_struct(h), "value", 1),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiOutOpen.side_effect = lambda h, d, cb, i, f: (
        setattr(_get_struct(h), "value", 2),
        MMSYSERR_NOERROR,
    )[1]
    mock_dll.midiInPrepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiInAddBuffer.return_value = MMSYSERR_NOERROR
    mock_dll.midiInStart.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutPrepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutLongMsg.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutUnprepareHeader.return_value = MMSYSERR_NOERROR
    mock_dll.midiOutReset.return_value = MMSYSERR_NOERROR

    # Short timeout 0.05s, driver does not signal MOM_DONE
    port = WinMmMidiPort(winmm_dll=mock_dll, send_timeout=0.05)
    port.open("Mock A", "Mock B")

    with pytest.raises(PortError) as exc_info:
        port.send_sysex(b"\xf0\x7d\x53\x42\x01\x00\xf7")

    assert exc_info.value.code == "E_TIMEOUT"
    assert mock_dll.midiOutReset.call_count == 1
    assert mock_dll.midiOutUnprepareHeader.call_count == 1

    port.close()


@pytest.mark.winmm
def test_live_winmm_enumeration() -> None:
    """Verify live WinMM enumeration succeeds on Windows without crashing."""
    if sys.platform != "win32":
        pytest.skip("Live WinMM requires Windows platform.")

    port = WinMmMidiPort()
    ports = port.list_ports()
    assert isinstance(ports, list)
    for p in ports:
        assert p.api == "winmm"
        assert p.direction in ("in", "out")
        assert len(p.name) > 0


@pytest.mark.winmm
def test_wms_detector_diagnostics_and_verification() -> None:
    """Verify WmsDetector queries build, service, and produces WmsDiagnostics."""
    diagnostics = WmsDetector.detect(port_backend=FakeMidiPort())
    assert isinstance(diagnostics, WmsDiagnostics)
    assert isinstance(diagnostics.is_windows, bool)
    assert isinstance(diagnostics.guidance_urls, list)
    assert len(diagnostics.guidance_urls) >= 2

    # Verify loopback endpoint probe with FakeMidiPort
    fake_port = FakeMidiPort()
    fake_port.register_port("Probe Loopback (A)", "Probe Loopback (B)")
    success = WmsDetector.verify_endpoints(fake_port, "Probe Loopback", timeout=1.0)
    assert success is True
