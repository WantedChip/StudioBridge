"""Windows Multimedia (WinMM) ctypes backend for MIDI port communication."""

from __future__ import annotations

import contextlib
import ctypes
import queue
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from studiobridge.core.errors import PortError
from studiobridge.ports.base import MidiPortInfo, PortStats

# WinMM callback calling convention
if hasattr(ctypes, "WINFUNCTYPE"):
    MIDI_CALLBACK_TYPE = ctypes.WINFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )
else:
    MIDI_CALLBACK_TYPE = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )

# WinMM API Constants
CALLBACK_FUNCTION = 0x00030000

MIM_OPEN = 0x3C1
MIM_CLOSE = 0x3C2
MIM_DATA = 0x3C3
MIM_LONGDATA = 0x3C4
MIM_ERROR = 0x3C5
MIM_LONGERROR = 0x3C6
MOM_OPEN = 0x3C7
MOM_CLOSE = 0x3C8
MOM_DONE = 0x3C9

MHDR_DONE = 0x00000001
MHDR_PREPARED = 0x00000002
MHDR_INQUEUE = 0x00000004
MHDR_ISSTRM = 0x00000008

MAXPNAMELEN = 32

# WinMM Error Codes
MMSYSERR_NOERROR = 0
MMSYSERR_ERROR = 1
MMSYSERR_BADDEVICEID = 2
MMSYSERR_NOTENABLED = 3
MMSYSERR_ALLOCATED = 4
MMSYSERR_INVALHANDLE = 5
MMSYSERR_NODRIVER = 6
MMSYSERR_NOMEM = 7
MMSYSERR_NOTSUPPORTED = 8
MMSYSERR_BADERRNUM = 9
MMSYSERR_INVALFLAG = 10
MMSYSERR_INVALPARAM = 11
MMSYSERR_HANDLEBUSY = 12

MIDIERR_UNPREPARED = 64
MIDIERR_STILLPLAYING = 65
MIDIERR_NOMAP = 66
MIDIERR_NOTREADY = 67
MIDIERR_NODEVICE = 68

# Structured error mapping table [PORT-19]
WINMM_ERROR_MAPPINGS: dict[int, tuple[str, str, str, bool]] = {
    MMSYSERR_ALLOCATED: (
        "MMSYSERR_ALLOCATED",
        "MIDI port is already opened by another application.",
        (
            "Close any application holding exclusive lock on the MIDI port. "
            "Windows MIDI Services (WMS) enables multi-client port sharing; "
            "with legacy loopMIDI only one client may bind at a time."
        ),
        True,
    ),
    MMSYSERR_BADDEVICEID: (
        "MMSYSERR_BADDEVICEID",
        "Invalid or obsolete MIDI device ID.",
        (
            "Re-enumerate MIDI ports by name. The port device index may have "
            "shifted due to hardware changes."
        ),
        False,
    ),
    MMSYSERR_NODRIVER: (
        "MMSYSERR_NODRIVER",
        "No MIDI driver installed or driver failed to load.",
        (
            "Verify MIDI driver installation. On Windows 11 24H2+, ensure the "
            "'midisrv' service is running ('sc start midisrv')."
        ),
        True,
    ),
    MIDIERR_STILLPLAYING: (
        "MIDIERR_STILLPLAYING",
        "MIDI buffers are still playing or queued in the driver.",
        (
            "Reset MIDI port buffers with midiInReset/midiOutReset before "
            "attempting to unprepare headers or close."
        ),
        True,
    ),
    MIDIERR_NOTREADY: (
        "MIDIERR_NOTREADY",
        "MIDI hardware or driver is not ready to receive data.",
        "Wait briefly for the MIDI endpoint to initialize and retry the transmission.",
        True,
    ),
    MMSYSERR_NOMEM: (
        "MMSYSERR_NOMEM",
        "System is unable to allocate memory for MIDI buffers.",
        "Free system memory or reduce MIDI buffer allocation count / buffer size.",
        False,
    ),
    MMSYSERR_INVALHANDLE: (
        "MMSYSERR_INVALHANDLE",
        "Specified MIDI device handle is invalid or already closed.",
        "Reopen the MIDI device handle before sending or receiving.",
        False,
    ),
    MMSYSERR_INVALPARAM: (
        "MMSYSERR_INVALPARAM",
        "Invalid parameter passed to WinMM API.",
        "Check buffer parameters, pointers, and struct sizes.",
        False,
    ),
    MIDIERR_UNPREPARED: (
        "MIDIERR_UNPREPARED",
        "MIDI buffer header was not prepared with midiInPrepareHeader or midiOutPrepareHeader.",
        "Ensure MIDIHDR is successfully prepared before adding to buffer queue or sending.",
        False,
    ),
}


class MIDIHDR(ctypes.Structure):
    """WinMM MIDIHDR ctypes structure with pack(1) alignment [PORT-12].

    Matches Windows SDK mmeapi.h definition under mmsystem.h pack(1) alignment.
    Equals exactly 112 bytes on 64-bit systems.
    """

    _pack_ = 1
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", ctypes.c_uint32),
        ("dwBytesRecorded", ctypes.c_uint32),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", ctypes.c_uint32),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
        ("dwOffset", ctypes.c_uint32),
        ("dwReserved", ctypes.c_size_t * 8),
    ]


# Validate 64-bit size invariant on startup
if ctypes.sizeof(ctypes.c_void_p) == 8:
    assert ctypes.sizeof(MIDIHDR) == 112, (
        f"sizeof(MIDIHDR) must be 112 on 64-bit platforms, got {ctypes.sizeof(MIDIHDR)}"
    )


class MIDIINCAPSW(ctypes.Structure):
    """WinMM MIDIINCAPSW structure for querying input device capabilities."""

    _pack_ = 1
    _fields_ = [
        ("wMid", ctypes.c_uint16),
        ("wPid", ctypes.c_uint16),
        ("vDriverVersion", ctypes.c_uint32),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("dwSupport", ctypes.c_uint32),
    ]


class MIDIOUTCAPSW(ctypes.Structure):
    """WinMM MIDIOUTCAPSW structure for querying output device capabilities."""

    _pack_ = 1
    _fields_ = [
        ("wMid", ctypes.c_uint16),
        ("wPid", ctypes.c_uint16),
        ("vDriverVersion", ctypes.c_uint32),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("wTechnology", ctypes.c_uint16),
        ("wVoices", ctypes.c_uint16),
        ("wNotes", ctypes.c_uint16),
        ("wChannelMask", ctypes.c_uint16),
        ("dwSupport", ctypes.c_uint32),
    ]


def setup_winmm_signatures(dll: Any) -> None:
    """Explicitly configure restype and argtypes for all WinMM C API functions [PORT-11]."""
    dll.midiInGetNumDevs.argtypes = []
    dll.midiInGetNumDevs.restype = ctypes.c_uint

    dll.midiInGetDevCapsW.argtypes = [
        ctypes.c_size_t,
        ctypes.POINTER(MIDIINCAPSW),
        ctypes.c_uint,
    ]
    dll.midiInGetDevCapsW.restype = ctypes.c_uint

    dll.midiOutGetNumDevs.argtypes = []
    dll.midiOutGetNumDevs.restype = ctypes.c_uint

    dll.midiOutGetDevCapsW.argtypes = [
        ctypes.c_size_t,
        ctypes.POINTER(MIDIOUTCAPSW),
        ctypes.c_uint,
    ]
    dll.midiOutGetDevCapsW.restype = ctypes.c_uint

    dll.midiInOpen.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_uint32,
    ]
    dll.midiInOpen.restype = ctypes.c_uint

    dll.midiInPrepareHeader.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiInPrepareHeader.restype = ctypes.c_uint

    dll.midiInAddBuffer.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiInAddBuffer.restype = ctypes.c_uint

    dll.midiInStart.argtypes = [ctypes.c_void_p]
    dll.midiInStart.restype = ctypes.c_uint

    dll.midiInStop.argtypes = [ctypes.c_void_p]
    dll.midiInStop.restype = ctypes.c_uint

    dll.midiInReset.argtypes = [ctypes.c_void_p]
    dll.midiInReset.restype = ctypes.c_uint

    dll.midiInUnprepareHeader.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiInUnprepareHeader.restype = ctypes.c_uint

    dll.midiInClose.argtypes = [ctypes.c_void_p]
    dll.midiInClose.restype = ctypes.c_uint

    dll.midiOutOpen.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_uint32,
    ]
    dll.midiOutOpen.restype = ctypes.c_uint

    dll.midiOutPrepareHeader.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiOutPrepareHeader.restype = ctypes.c_uint

    dll.midiOutLongMsg.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiOutLongMsg.restype = ctypes.c_uint

    dll.midiOutUnprepareHeader.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MIDIHDR),
        ctypes.c_uint,
    ]
    dll.midiOutUnprepareHeader.restype = ctypes.c_uint

    dll.midiOutReset.argtypes = [ctypes.c_void_p]
    dll.midiOutReset.restype = ctypes.c_uint

    dll.midiOutClose.argtypes = [ctypes.c_void_p]
    dll.midiOutClose.restype = ctypes.c_uint

    dll.midiInGetErrorTextW.argtypes = [
        ctypes.c_uint,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    dll.midiInGetErrorTextW.restype = ctypes.c_uint

    dll.midiOutGetErrorTextW.argtypes = [
        ctypes.c_uint,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    dll.midiOutGetErrorTextW.restype = ctypes.c_uint


def map_winmm_error(
    err_num: int,
    action: str,
    *,
    dll: Any = None,
    is_input: bool = True,
) -> PortError:
    """Map a WinMM error return code to a typed PortError with remedy [PORT-19]."""
    system_text = ""
    if dll is not None:
        try:
            buf = ctypes.create_unicode_buffer(256)
            fn = dll.midiInGetErrorTextW if is_input else dll.midiOutGetErrorTextW
            if fn(err_num, buf, 256) == MMSYSERR_NOERROR:
                system_text = buf.value.strip()
        except Exception:
            pass

    if err_num in WINMM_ERROR_MAPPINGS:
        name, default_msg, remedy, retryable = WINMM_ERROR_MAPPINGS[err_num]
        msg = f"{action} failed with {name} ({err_num}): {default_msg}"
        if system_text:
            msg += f" [System: {system_text}]"
        return PortError(
            msg,
            code="E_ENV_PORT",
            details={
                "winmm_error": name,
                "error_code": err_num,
                "action": action,
                "system_text": system_text,
            },
            retryable=retryable,
            remedy=remedy,
        )

    msg = f"{action} failed with unknown WinMM error {err_num}."
    if system_text:
        msg += f" [System: {system_text}]"
    return PortError(
        msg,
        code="E_ENV_PORT",
        details={"error_code": err_num, "action": action, "system_text": system_text},
        retryable=False,
        remedy="Check Windows Event Viewer and verify MIDI hardware / loopback driver status.",
    )


class WinMmMidiPort:
    """Windows Multimedia (WinMM) ctypes implementation of MidiPort.

    Features:
    - Zero compile step; identical execution on x64 and ARM64 Windows [PORT-10].
    - Ring buffer pool of prepared headers for incoming SysEx reception [PORT-13, PORT-14].
    - Queue worker thread decoupling WinMM callbacks from client delivery [PORT-13, PORT-18].
    - Synchronous sequential transmission with MOM_DONE event synchronization [PORT-15].
    """

    def __init__(
        self,
        *,
        winmm_dll: Any = None,
        send_timeout: float = 5.0,
        inter_frame_gap_ms: float = 0.0,
    ) -> None:
        self.send_timeout: float = send_timeout
        self.inter_frame_gap_ms: float = inter_frame_gap_ms

        self._winmm = winmm_dll
        if self._winmm is None and sys.platform == "win32":
            try:
                self._winmm = ctypes.WinDLL("winmm", use_last_error=True)
                setup_winmm_signatures(self._winmm)
            except Exception:
                self._winmm = None
        elif self._winmm is not None:
            setup_winmm_signatures(self._winmm)

        self._in_name: str | None = None
        self._out_name: str | None = None
        self._is_open = False
        self._stats = PortStats()

        self._h_in: ctypes.c_void_p | None = None
        self._h_out: ctypes.c_void_p | None = None

        # Callbacks and buffers strong references
        self._in_cb_ref: Any = None
        self._out_cb_ref: Any = None
        self._in_buffers: dict[int, tuple[Any, MIDIHDR]] = {}

        self._sysex_callbacks: list[Callable[[bytes], None]] = []
        self._error_callbacks: list[Callable[[PortError], None]] = []

        self._in_queue: queue.SimpleQueue[tuple[int, int] | None] = queue.SimpleQueue()
        self._worker_thread: threading.Thread | None = None
        self._accumulator = bytearray()

        self._out_done_event = threading.Event()
        self._send_lock = threading.Lock()
        self._state_lock = threading.RLock()

    def _ensure_winmm(self) -> Any:
        if self._winmm is None:
            raise PortError(
                "WinMM MIDI backend is unavailable (requires Windows x64 or ARM64).",
                code="E_ENV_OS",
                remedy=(
                    "Use FakeMidiPort for testing on non-Windows platforms or "
                    "install Windows MIDI drivers."
                ),
            )
        return self._winmm

    def list_ports(self) -> list[MidiPortInfo]:
        """Enumerate all visible WinMM input and output ports."""
        winmm = self._ensure_winmm()
        ports: list[MidiPortInfo] = []

        num_in = int(winmm.midiInGetNumDevs())
        for idx in range(num_in):
            caps = MIDIINCAPSW()
            res = winmm.midiInGetDevCapsW(idx, ctypes.byref(caps), ctypes.sizeof(caps))
            if res == MMSYSERR_NOERROR:
                v_major = (caps.vDriverVersion >> 8) & 0xFF
                v_minor = caps.vDriverVersion & 0xFF
                ports.append(
                    MidiPortInfo(
                        direction="in",
                        index=idx,
                        name=caps.szPname,
                        api="winmm",
                        manufacturer=f"0x{caps.wMid:04X}",
                        driver_version=f"{v_major}.{v_minor}",
                    )
                )

        num_out = int(winmm.midiOutGetNumDevs())
        for idx in range(num_out):
            caps = MIDIOUTCAPSW()
            res = winmm.midiOutGetDevCapsW(idx, ctypes.byref(caps), ctypes.sizeof(caps))
            if res == MMSYSERR_NOERROR:
                v_major = (caps.vDriverVersion >> 8) & 0xFF
                v_minor = caps.vDriverVersion & 0xFF
                ports.append(
                    MidiPortInfo(
                        direction="out",
                        index=idx,
                        name=caps.szPname,
                        api="winmm",
                        manufacturer=f"0x{caps.wMid:04X}",
                        driver_version=f"{v_major}.{v_minor}",
                    )
                )

        return ports

    def open(
        self,
        in_name: str,
        out_name: str,
        *,
        sysex_buf: int = 16384,
        nbufs: int = 8,
    ) -> None:
        """Open input and output WinMM endpoints by name [PORT-16, PORT-17]."""
        with self._state_lock:
            if self._is_open:
                self.close()

            winmm = self._ensure_winmm()

            # Resolve names to indices
            from studiobridge.ports.discovery import PortResolver

            resolver = PortResolver(self)
            in_info = resolver.resolve(in_name, direction="in")
            out_info = resolver.resolve(out_name, direction="out")

            # Setup input callback
            self._in_cb_ref = MIDI_CALLBACK_TYPE(self._in_callback)
            h_in = ctypes.c_void_p()
            in_cb_addr = ctypes.cast(self._in_cb_ref, ctypes.c_void_p).value or 0
            res = winmm.midiInOpen(
                ctypes.byref(h_in),
                in_info.index,
                in_cb_addr,
                0,
                CALLBACK_FUNCTION,
            )
            if res != MMSYSERR_NOERROR:
                raise map_winmm_error(res, f"midiInOpen({in_name!r})", dll=winmm, is_input=True)
            self._h_in = h_in

            # Setup output callback
            self._out_cb_ref = MIDI_CALLBACK_TYPE(self._out_callback)
            h_out = ctypes.c_void_p()
            out_cb_addr = ctypes.cast(self._out_cb_ref, ctypes.c_void_p).value or 0
            res = winmm.midiOutOpen(
                ctypes.byref(h_out),
                out_info.index,
                out_cb_addr,
                0,
                CALLBACK_FUNCTION,
            )
            if res != MMSYSERR_NOERROR:
                winmm.midiInClose(self._h_in)
                self._h_in = None
                raise map_winmm_error(res, f"midiOutOpen({out_name!r})", dll=winmm, is_input=False)
            self._h_out = h_out

            # Allocate input buffer ring pool [PORT-13, PORT-14]
            self._in_buffers.clear()
            for idx in range(nbufs):
                raw_buf = (ctypes.c_char * sysex_buf)()
                hdr = MIDIHDR()
                hdr.lpData = ctypes.cast(raw_buf, ctypes.c_void_p)
                hdr.dwBufferLength = sysex_buf
                hdr.dwBytesRecorded = 0
                hdr.dwUser = idx
                hdr.dwFlags = 0

                res = winmm.midiInPrepareHeader(
                    self._h_in, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR)
                )
                if res != MMSYSERR_NOERROR:
                    self.close()
                    raise map_winmm_error(res, "midiInPrepareHeader", dll=winmm, is_input=True)

                res = winmm.midiInAddBuffer(self._h_in, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))
                if res != MMSYSERR_NOERROR:
                    self.close()
                    raise map_winmm_error(res, "midiInAddBuffer", dll=winmm, is_input=True)

                self._in_buffers[ctypes.addressof(hdr)] = (raw_buf, hdr)

            # Start recording input
            res = winmm.midiInStart(self._h_in)
            if res != MMSYSERR_NOERROR:
                self.close()
                raise map_winmm_error(res, "midiInStart", dll=winmm, is_input=True)

            self._in_name = in_name
            self._out_name = out_name
            self._is_open = True

            # Start worker thread
            self._start_worker()

    def _start_worker(self) -> None:
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name=f"WinMmMidiWorker-{self._in_name or 'port'}",
                daemon=True,
            )
            self._worker_thread.start()

    def _in_callback(
        self,
        hMidiIn: Any,
        wMsg: int,
        dwInstance: int,
        dwParam1: int,
        dwParam2: int,
    ) -> None:
        """Driver input callback running on WinMM thread.

        Per [PORT-13], performs zero heap allocation or heavy WinMM calls,
        enqueuing buffer notifications directly to SimpleQueue.
        """
        if wMsg == MIM_LONGDATA:
            try:
                hdr_ptr = ctypes.cast(dwParam1, ctypes.POINTER(MIDIHDR))
                bytes_recorded = int(hdr_ptr.contents.dwBytesRecorded)
                self._in_queue.put((dwParam1, bytes_recorded))
            except Exception:
                self._in_queue.put((dwParam1, -1))
        elif wMsg == MIM_LONGERROR:
            self._in_queue.put((dwParam1, -1))
        elif wMsg == MIM_CLOSE:
            self._in_queue.put((0, -2))

    def _out_callback(
        self,
        hMidiOut: Any,
        wMsg: int,
        dwInstance: int,
        dwParam1: int,
        dwParam2: int,
    ) -> None:
        """Driver output callback signaling send completion on MOM_DONE [PORT-15]."""
        if wMsg == MOM_DONE:
            self._out_done_event.set()

    def _worker_loop(self) -> None:
        """Background worker thread draining input queue and recycling buffers [PORT-13]."""
        winmm = self._winmm
        while True:
            try:
                item = self._in_queue.get()
            except Exception:
                break

            if item is None:
                break

            hdr_addr, bytes_rec = item

            if bytes_rec == -2:
                # Unexpected port close
                if self._is_open:
                    self._notify_error(
                        PortError(
                            "WinMM MIDI input port closed unexpectedly by system or driver.",
                            code="E_DISCONNECTED",
                            retryable=True,
                            remedy="Re-enumerate ports and restart session connection.",
                        )
                    )
                continue

            if hdr_addr not in self._in_buffers:
                continue

            raw_buf, hdr = self._in_buffers[hdr_addr]

            if bytes_rec == -1:
                # MIM_LONGERROR
                with self._state_lock:
                    self._stats.long_errors += 1
                    self._stats.dropped += 1
                if winmm is not None and self._h_in is not None:
                    hdr.dwBytesRecorded = 0
                    hdr.dwFlags &= ~MHDR_DONE
                    winmm.midiInAddBuffer(self._h_in, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))
                continue

            # Process received bytes
            if bytes_rec > 0:
                chunk = bytes(raw_buf[:bytes_rec])
                self._accumulator.extend(chunk)

                # Accumulate SysEx frames until 0xF7 [PORT-14]
                while 0xF7 in self._accumulator:
                    f7_idx = self._accumulator.index(0xF7)
                    if 0xF0 in self._accumulator:
                        f0_idx = self._accumulator.index(0xF0)
                        if f0_idx <= f7_idx:
                            msg = bytes(self._accumulator[f0_idx : f7_idx + 1])
                            self._accumulator = self._accumulator[f7_idx + 1 :]
                            with self._state_lock:
                                self._stats.bytes_recv += len(msg)
                                self._stats.frames_recv += 1
                            self._dispatch_sysex(msg)
                        else:
                            # Stale trailing bytes before F0
                            self._accumulator = self._accumulator[f0_idx:]
                    else:
                        # Corrupt fragment without start byte F0
                        self._accumulator = self._accumulator[f7_idx + 1 :]

            # Recycle input buffer back to WinMM ring [PORT-13]
            if winmm is not None and self._h_in is not None and self._is_open:
                hdr.dwBytesRecorded = 0
                hdr.dwFlags &= ~MHDR_DONE
                winmm.midiInAddBuffer(self._h_in, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))

    def _dispatch_sysex(self, msg: bytes) -> None:
        with self._state_lock:
            callbacks = list(self._sysex_callbacks)
        for cb in callbacks:
            try:
                cb(msg)
            except Exception as exc:
                self._notify_error(
                    PortError(
                        f"Unhandled exception in SysEx callback handler: {exc}",
                        code="E_FL",
                        details={"error": str(exc)},
                        remedy="Fix exception inside SysEx callback handler.",
                    )
                )

    def _notify_error(self, err: PortError) -> None:
        with self._state_lock:
            callbacks = list(self._error_callbacks)
        for cb in callbacks:
            with contextlib.suppress(Exception):
                cb(err)

    def send_sysex(self, data: bytes) -> None:
        """Send SysEx bytes synchronously, waiting on MOM_DONE completion [PORT-15]."""
        with self._state_lock:
            if not self._is_open or self._h_out is None or self._winmm is None:
                raise PortError(
                    "Cannot send SysEx: MIDI output port is closed.",
                    code="E_ENV_PORT",
                    remedy="Open the MIDI port before attempting transmission.",
                )

        if not (data.startswith(b"\xf0") and data.endswith(b"\xf7")):
            raise PortError(
                "Invalid SysEx message: payload must begin with 0xF0 and end with 0xF7.",
                code="E_PROTO",
                details={"length": len(data)},
                remedy="Ensure packet framing conforms to MIDI SysEx specification.",
            )

        with self._send_lock:
            winmm = self._winmm
            h_out = self._h_out
            if h_out is None or winmm is None:
                raise PortError("MIDI output port closed during send.", code="E_ENV_PORT")

            raw_buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
            hdr = MIDIHDR()
            hdr.lpData = ctypes.cast(raw_buf, ctypes.c_void_p)
            hdr.dwBufferLength = len(data)
            hdr.dwFlags = 0

            # Prepare output header
            res = winmm.midiOutPrepareHeader(h_out, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))
            if res != MMSYSERR_NOERROR:
                raise map_winmm_error(res, "midiOutPrepareHeader", dll=winmm, is_input=False)

            self._out_done_event.clear()

            try:
                # Transmit long message
                res = winmm.midiOutLongMsg(h_out, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))
                if res != MMSYSERR_NOERROR:
                    raise map_winmm_error(res, "midiOutLongMsg", dll=winmm, is_input=False)

                # Wait for MOM_DONE driver notification
                finished = self._out_done_event.wait(timeout=self.send_timeout)
                if not finished:
                    winmm.midiOutReset(h_out)
                    raise PortError(
                        f"MIDI output timed out waiting for driver completion "
                        f"({self.send_timeout}s).",
                        code="E_TIMEOUT",
                        retryable=True,
                        remedy=(
                            "Check if receiving endpoint / FL Studio device script is responsive."
                        ),
                    )
            finally:
                # Always unprepare header
                winmm.midiOutUnprepareHeader(h_out, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR))

            with self._state_lock:
                self._stats.bytes_sent += len(data)
                self._stats.frames_sent += 1

            if self.inter_frame_gap_ms > 0:
                time.sleep(self.inter_frame_gap_ms / 1000.0)

    def on_sysex(self, cb: Callable[[bytes], None]) -> None:
        """Register a callback for incoming SysEx messages."""
        with self._state_lock:
            if cb not in self._sysex_callbacks:
                self._sysex_callbacks.append(cb)

    def on_error(self, cb: Callable[[PortError], None]) -> None:
        """Register a callback for port errors and disconnects."""
        with self._state_lock:
            if cb not in self._error_callbacks:
                self._error_callbacks.append(cb)

    def close(self) -> None:
        """Close endpoints, unprepare buffers, and shut down worker thread."""
        with self._state_lock:
            if not self._is_open and self._h_in is None and self._h_out is None:
                return

            self._is_open = False
            winmm = self._winmm

            # Stop and reset input
            if winmm is not None and self._h_in is not None:
                try:
                    winmm.midiInStop(self._h_in)
                    winmm.midiInReset(self._h_in)
                    for _, hdr in self._in_buffers.values():
                        winmm.midiInUnprepareHeader(
                            self._h_in, ctypes.byref(hdr), ctypes.sizeof(MIDIHDR)
                        )
                    winmm.midiInClose(self._h_in)
                except Exception:
                    pass
                self._h_in = None
            self._in_buffers.clear()

            # Signal worker thread to terminate
            self._in_queue.put(None)
            if self._worker_thread is not None and self._worker_thread.is_alive():
                if threading.current_thread() != self._worker_thread:
                    self._worker_thread.join(timeout=1.0)
                self._worker_thread = None

            # Reset and close output
            if winmm is not None and self._h_out is not None:
                try:
                    winmm.midiOutReset(self._h_out)
                    winmm.midiOutClose(self._h_out)
                except Exception:
                    pass
                self._h_out = None

            self._in_cb_ref = None
            self._out_cb_ref = None
            self._in_name = None
            self._out_name = None

    @property
    def is_open(self) -> bool:
        """Return True if port is open."""
        with self._state_lock:
            return self._is_open

    @property
    def stats(self) -> PortStats:
        """Return port telemetry counters."""
        return self._stats

    @property
    def in_name(self) -> str | None:
        """Return active input port name."""
        with self._state_lock:
            return self._in_name

    @property
    def out_name(self) -> str | None:
        """Return active output port name."""
        with self._state_lock:
            return self._out_name
