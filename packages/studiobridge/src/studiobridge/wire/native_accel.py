"""Optional native acceleration helpers and ctypes bindings.

Provides dynamic ctypes bindings for optional native acceleration DLLs (ARM64 and x64)
with transparent fallback to pure-Python reference implementations.

Requirements:
- req: ARM-01: ARM64 and x64 dual-architecture native acceleration
- req: WIRE-02: SysEx wire frame layout and CRC-16/CCITT-FALSE
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

# Protocol polynomial and initial register value constants matching pure-Python wire
CRC_INIT: Final[int] = 0xFFFF

# Global cached ctypes CDLL instance
_NATIVE_LIB: ctypes.CDLL | None = None
_NATIVE_LOADED: bool = False


def _is_arm64_process() -> bool:
    """Detect whether current Python process is running as native ARM64."""
    # On Windows, check sys.version first to distinguish emulated AMD64 from native ARM64
    if "ARM64" in sys.version:
        return True
    if "AMD64" in sys.version or "x86_64" in sys.version:
        return False
    mach = platform.machine().lower()
    return "arm64" in mach or "aarch64" in mach


def find_native_library(base_dir: Path | None = None) -> Path | None:
    """Locate the appropriate native acceleration shared library for this platform.

    Resolution order:
    1. Explicit path from STUDIOBRIDGE_NATIVE_LIB environment variable.
    2. Architecture-specific build directory under workspace or base_dir:
       - ARM64 process: build/native/ARM64/studiobridge_native.dll
       - x64 process: build/native/X64/studiobridge_native.dll
    3. Fallback to alternative architecture (e.g. Prism emulation / cross-test).
    4. Generic build/native/studiobridge_native.dll.
    """
    env_override = os.environ.get("STUDIOBRIDGE_NATIVE_LIB")
    if env_override:
        candidate = Path(env_override).resolve()
        if candidate.is_file():
            return candidate

    search_roots: list[Path] = []
    if base_dir is not None:
        search_roots.append(base_dir)

    # Current module location -> packages/studiobridge/src/studiobridge/wire -> repo root
    module_path = Path(__file__).resolve()
    repo_root = module_path.parents[4]
    search_roots.append(repo_root)
    search_roots.append(Path.cwd())

    # Determine architecture candidate order
    arch_order = ["ARM64", "X64"] if _is_arm64_process() else ["X64", "ARM64"]

    for root in search_roots:
        for arch in arch_order:
            candidate = root / "build" / "native" / arch / "studiobridge_native.dll"
            if candidate.is_file():
                return candidate
        generic = root / "build" / "native" / "studiobridge_native.dll"
        if generic.is_file():
            return generic

    return None


def get_native_library() -> ctypes.CDLL | None:
    """Obtain or initialize the loaded native CDLL handle.

    Returns:
        ctypes.CDLL handle if successfully loaded, None otherwise.
    """
    global _NATIVE_LIB, _NATIVE_LOADED
    if _NATIVE_LOADED:
        return _NATIVE_LIB

    _NATIVE_LOADED = True
    lib_path = find_native_library()
    if lib_path is None:
        _NATIVE_LIB = None
        return None

    try:
        lib = ctypes.CDLL(str(lib_path))
        # Configure function signatures
        lib.sb_version.argtypes = []
        lib.sb_version.restype = ctypes.c_int

        lib.sb_build_arch.argtypes = []
        lib.sb_build_arch.restype = ctypes.c_char_p

        lib.sb_crc16.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint16]
        lib.sb_crc16.restype = ctypes.c_uint16

        lib.sb_crc16_bitwise.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint16]
        lib.sb_crc16_bitwise.restype = ctypes.c_uint16

        lib.sb_crc32.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32]
        lib.sb_crc32.restype = ctypes.c_uint32

        lib.sb_pack_crc.argtypes = [ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8)]
        lib.sb_pack_crc.restype = ctypes.c_int

        lib.sb_unpack_crc.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint16)]
        lib.sb_unpack_crc.restype = ctypes.c_int

        lib.sb_pack_septets_14.argtypes = [ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8)]
        lib.sb_pack_septets_14.restype = ctypes.c_int

        lib.sb_unpack_septets_14.argtypes = [
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint16),
        ]
        lib.sb_unpack_septets_14.restype = ctypes.c_int

        lib.sb_pack_septets_21.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint8)]
        lib.sb_pack_septets_21.restype = ctypes.c_int

        lib.sb_unpack_septets_21.argtypes = [
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        lib.sb_unpack_septets_21.restype = ctypes.c_int

        lib.sb_validate_frame.argtypes = [
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
        ]
        lib.sb_validate_frame.restype = ctypes.c_int

        lib.sb_tolerance_matches.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
        lib.sb_tolerance_matches.restype = ctypes.c_int

        _NATIVE_LIB = lib
        return lib
    except OSError:
        _NATIVE_LIB = None
        return None


def is_native_available() -> bool:
    """Return True if the native acceleration shared library is loaded and operational."""
    return get_native_library() is not None


def get_native_arch() -> str | None:
    """Return the architecture string reported by the loaded native library."""
    lib = get_native_library()
    if lib is None:
        return None
    raw = lib.sb_build_arch()
    return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)


def native_crc16(data: bytes | bytearray | memoryview | Sequence[int], init: int = CRC_INIT) -> int:
    """Compute CRC-16/CCITT-FALSE using the native accelerator."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    buf = bytes(data)
    return int(lib.sb_crc16(buf, len(buf), init & 0xFFFF))


def native_crc16_bitwise(
    data: bytes | bytearray | memoryview | Sequence[int], init: int = CRC_INIT
) -> int:
    """Compute CRC-16/CCITT-FALSE using the native bitwise implementation."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    buf = bytes(data)
    return int(lib.sb_crc16_bitwise(buf, len(buf), init & 0xFFFF))


def native_crc32(data: bytes | bytearray | memoryview | Sequence[int], init: int = 0) -> int:
    """Compute CRC-32 (IEEE 802.3) using the native accelerator."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    buf = bytes(data)
    return int(lib.sb_crc32(buf, len(buf), init & 0xFFFFFFFF))


def native_pack_crc(crc: int) -> bytes:
    """Pack a 16-bit CRC value into 3 7-bit septets via native acceleration."""
    if crc < 0 or crc > 0xFFFF:
        raise ValueError(f"CRC value must be in range 0..0xFFFF (got {crc})")
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    out_buf = (ctypes.c_uint8 * 3)()
    status = lib.sb_pack_crc(crc, out_buf)
    if status != 0:
        raise ValueError("Failed to pack CRC into septets.")
    return bytes(out_buf)


def native_unpack_crc(septets: bytes | Sequence[int]) -> int:
    """Unpack 3 7-bit septets into a 16-bit CRC value via native acceleration."""
    if len(septets) < 3:
        raise ValueError(f"native_unpack_crc requires at least 3 bytes (got {len(septets)})")
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    raw = bytes(septets[:3])
    out_crc = ctypes.c_uint16()
    status = lib.sb_unpack_crc(raw, ctypes.byref(out_crc))
    if status != 0:
        err_msg = f"Invalid CRC septet bytes: [0x{raw[0]:02X}, 0x{raw[1]:02X}, 0x{raw[2]:02X}]"
        raise ValueError(err_msg)
    return int(out_crc.value)


def native_pack_septets_14(val: int) -> bytes:
    """Pack a 14-bit unsigned integer into 2 7-bit septets via native acceleration."""
    if val < 0 or val > 0x3FFF:
        raise ValueError(f"14-bit value out of range 0..0x3FFF (got {val})")
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    out_buf = (ctypes.c_uint8 * 2)()
    status = lib.sb_pack_septets_14(val, out_buf)
    if status != 0:
        raise ValueError(f"Failed to pack 14-bit value: {val}")
    return bytes(out_buf)


def native_unpack_septets_14(b0: int, b1: int) -> int:
    """Unpack 2 7-bit septets into a 14-bit integer via native acceleration."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    out_val = ctypes.c_uint16()
    status = lib.sb_unpack_septets_14(b0, b1, ctypes.byref(out_val))
    if status != 0:
        raise ValueError(f"Septet bytes out of 7-bit range: [0x{b0:02X}, 0x{b1:02X}]")
    return int(out_val.value)


def native_pack_septets_21(val: int) -> bytes:
    """Pack a 21-bit unsigned integer into 3 7-bit septets via native acceleration."""
    if val < 0 or val > 0x1FFFFF:
        raise ValueError(f"21-bit value out of range 0..0x1FFFFF (got {val})")
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    out_buf = (ctypes.c_uint8 * 3)()
    status = lib.sb_pack_septets_21(val, out_buf)
    if status != 0:
        raise ValueError(f"Failed to pack 21-bit value: {val}")
    return bytes(out_buf)


def native_unpack_septets_21(b0: int, b1: int, b2: int) -> int:
    """Unpack 3 7-bit septets into a 21-bit integer via native acceleration."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    out_val = ctypes.c_uint32()
    status = lib.sb_unpack_septets_21(b0, b1, b2, ctypes.byref(out_val))
    if status != 0:
        raise ValueError(f"Septet bytes out of 7-bit range: [0x{b0:02X}, 0x{b1:02X}, 0x{b2:02X}]")
    return int(out_val.value)


def native_validate_frame(raw: bytes | bytearray | memoryview) -> dict[str, int]:
    """Validate a SysEx wire frame and unpack header fields via native acceleration.

    Returns:
        Dictionary with extracted fields (kind, flags, sid, mid, cidx, ccnt, plen, crc).

    Raises:
        ValueError: If frame is invalid or corrupted.
    """
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    buf = bytes(raw)
    out_kind = ctypes.c_uint8()
    out_flags = ctypes.c_uint8()
    out_sid = ctypes.c_uint16()
    out_mid = ctypes.c_uint32()
    out_cidx = ctypes.c_uint16()
    out_ccnt = ctypes.c_uint16()
    out_plen = ctypes.c_uint16()
    out_crc = ctypes.c_uint16()

    status = lib.sb_validate_frame(
        buf,
        len(buf),
        ctypes.byref(out_kind),
        ctypes.byref(out_flags),
        ctypes.byref(out_sid),
        ctypes.byref(out_mid),
        ctypes.byref(out_cidx),
        ctypes.byref(out_ccnt),
        ctypes.byref(out_plen),
        ctypes.byref(out_crc),
    )
    if status != 0:
        error_reasons = {
            -1: "Frame too short (< 22 bytes)",
            -2: "Framing byte mismatch (expected 0xF0 start, 0xF7 end)",
            -3: "Manufacturer or magic identifier mismatch (expected 0x7D 'SB')",
            -4: "Unsupported protocol version",
            -5: "Payload length mismatch",
            -6: "CRC-16 checksum mismatch",
            -7: "Invalid 7-bit septet bounds",
        }
        reason = error_reasons.get(status, f"Validation failure code {status}")
        raise ValueError(f"Frame validation failed: {reason}")

    return {
        "kind": int(out_kind.value),
        "flags": int(out_flags.value),
        "sid": int(out_sid.value),
        "mid": int(out_mid.value),
        "cidx": int(out_cidx.value),
        "ccnt": int(out_ccnt.value),
        "plen": int(out_plen.value),
        "crc": int(out_crc.value),
    }


def native_tolerance_matches(expected: float, actual: float, tol: float = 0.005) -> bool:
    """Evaluate whether actual and expected match within tolerance via native acceleration."""
    lib = get_native_library()
    if lib is None:
        raise RuntimeError("Native acceleration library is not loaded.")
    result = lib.sb_tolerance_matches(
        ctypes.c_double(expected), ctypes.c_double(actual), ctypes.c_double(tol)
    )
    return bool(result == 1)
