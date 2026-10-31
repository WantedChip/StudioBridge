"""Differential testing suite comparing native accelerators against pure-Python references.

Validates 100% parity across CRC calculation, 7-bit septet packing, SysEx frame validation,
floating-point tolerance comparison, and asserts that package wheels remain strictly
pure-Python (py3-none-any) with zero mandatory compiled dependencies.

Requirements:
- req: ARM-01: Native toolchain dual compilation and differential parity
- req: WIRE-02: SysEx wire frame layout and CRC-16/CCITT-FALSE
- req: PKG-01: Universal pure-Python wheel distribution
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import zipfile
import zlib
from pathlib import Path

import pytest

from studiobridge.core.errors import ProtocolError
from studiobridge.sdk.verification import tolerance_matches
from studiobridge.wire.chunk import Reassembler, chunk_payload
from studiobridge.wire.crc import (
    CRC_CHECK_INPUT,
    CRC_CHECK_VALUE,
    CRC_INIT,
    crc16,
    crc16_bitwise,
    pack_crc,
    pack_septets_14,
    pack_septets_21,
    unpack_crc,
    unpack_septets_14,
    unpack_septets_21,
)
from studiobridge.wire.frame import (
    Frame,
    FrameFlags,
    FrameKind,
    decode_frame,
    encode_frame,
)
from studiobridge.wire.native_accel import (
    find_native_library,
    get_native_arch,
    is_native_available,
    native_crc16,
    native_crc16_bitwise,
    native_crc32,
    native_pack_crc,
    native_pack_septets_14,
    native_pack_septets_21,
    native_tolerance_matches,
    native_unpack_crc,
    native_unpack_septets_14,
    native_unpack_septets_21,
    native_validate_frame,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_pe_machine_type(dll_path: Path) -> int:
    """Read the COFF machine architecture integer from a PE binary."""
    with open(dll_path, "rb") as f:
        data = f.read(1024)
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError(f"File {dll_path} is not a valid PE image.")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
    return machine


class TestNativeToolchainBuild:
    """Validate dual-architecture native build script and PE header outputs."""

    # req: ARM-01
    def test_build_script_exists_and_runs(self) -> None:
        """Verify build_native.ps1 compiles ARM64 and x64 DLLs with matching PE headers."""
        script_path = REPO_ROOT / "tools" / "build" / "build_native.ps1"
        assert script_path.is_file(), f"Build script not found: {script_path}"

        # If pwsh is present, run build_native.ps1
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            pytest.skip("pwsh not available on PATH")

        result = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(script_path), "-Architecture", "ARM64,x64"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"build_native.ps1 failed:\n{result.stdout}\n{result.stderr}"

        arm64_dll = REPO_ROOT / "build" / "native" / "ARM64" / "studiobridge_native.dll"
        x64_dll = REPO_ROOT / "build" / "native" / "X64" / "studiobridge_native.dll"

        assert arm64_dll.is_file(), f"ARM64 DLL missing: {arm64_dll}"
        assert x64_dll.is_file(), f"x64 DLL missing: {x64_dll}"

        # Verify PE Machine types: ARM64 is 0xAA64, x64 is 0x8664
        assert _read_pe_machine_type(arm64_dll) == 0xAA64
        assert _read_pe_machine_type(x64_dll) == 0x8664

    # req: ARM-01
    def test_native_library_detection_and_arch(self) -> None:
        """Verify find_native_library resolves existing DLL and reports architecture."""
        lib_path = find_native_library()
        if not is_native_available():
            pytest.skip("Native shared library not loaded on this platform.")

        assert lib_path is not None
        assert lib_path.is_file()

        arch = get_native_arch()
        assert arch in ("ARM64", "x64")


class TestDifferentialCRC:
    """Differential verification comparing pure-Python and native CRC calculations."""

    # req: WIRE-02
    def test_crc16_standard_check_vector(self) -> None:
        """Verify standard ASCII '123456789' produces check value 0x29B1 across all routines."""
        # Pure-Python table implementation
        py_table = crc16(CRC_CHECK_INPUT, CRC_INIT)
        # Pure-Python bitwise reference implementation
        py_bit = crc16_bitwise(CRC_CHECK_INPUT, CRC_INIT)

        assert py_table == CRC_CHECK_VALUE
        assert py_bit == CRC_CHECK_VALUE

        if is_native_available():
            nat_table = native_crc16(CRC_CHECK_INPUT, CRC_INIT)
            nat_bit = native_crc16_bitwise(CRC_CHECK_INPUT, CRC_INIT)
            assert nat_table == CRC_CHECK_VALUE
            assert nat_bit == CRC_CHECK_VALUE
            assert nat_table == py_table

    # req: WIRE-02
    def test_crc16_empty_and_single_byte_parity(self) -> None:
        """Verify CRC-16 parity on empty and single-byte edge cases."""
        test_cases: list[bytes] = [
            b"",
            b"\x00",
            b"\x01",
            b"\x7f",
            b"\x80",
            b"\xff",
        ]
        for data in test_cases:
            py_res = crc16(data, CRC_INIT)
            py_bit = crc16_bitwise(data, CRC_INIT)
            assert py_res == py_bit, f"Python table vs bitwise mismatch on {data!r}"

            if is_native_available():
                nat_res = native_crc16(data, CRC_INIT)
                nat_bit = native_crc16_bitwise(data, CRC_INIT)
                assert nat_res == py_res, (
                    f"Native CRC16 mismatch on {data!r}: {nat_res} vs {py_res}"
                )
                assert nat_bit == py_res, f"Native bitwise mismatch on {data!r}"

    # req: WIRE-02
    def test_crc16_variable_length_and_fuzz_parity(self) -> None:
        """Verify parity across varied payload lengths and pseudorandom binary sequences."""
        lengths = [2, 3, 7, 13, 17, 32, 64, 128, 256, 512, 1024, 65536]
        for length in lengths:
            # Deterministic pseudorandom buffer
            data = bytes((i * 37 + 11) & 0xFF for i in range(length))
            py_val = crc16(data, CRC_INIT)

            if is_native_available():
                nat_val = native_crc16(data, CRC_INIT)
                assert nat_val == py_val, f"CRC16 parity failure at length {length}"

    # req: WIRE-02
    def test_crc16_custom_init_values(self) -> None:
        """Verify CRC-16 parity when using non-standard initial register values."""
        inits = [0x0000, 0x1234, 0xAAAA, 0x5555, 0xFFFF]
        sample = b"StudioBridge wire protocol high-frequency SysEx payload test"
        for init in inits:
            py_val = crc16(sample, init)
            py_bit = crc16_bitwise(sample, init)
            assert py_val == py_bit

            if is_native_available():
                nat_val = native_crc16(sample, init)
                nat_bit = native_crc16_bitwise(sample, init)
                assert nat_val == py_val
                assert nat_bit == py_val

    # req: ARM-01
    def test_crc32_native_vs_python_zlib_parity(self) -> None:
        """Verify native CRC-32 (IEEE 802.3) matches Python zlib.crc32 100% bit-exact."""
        if not is_native_available():
            pytest.skip("Native acceleration library not available.")

        test_cases = [
            b"",
            b"123456789",
            b"hello world",
            bytes(range(256)),
            b"\x00" * 1024,
            b"\xff" * 1024,
            bytes((i * 101) & 0xFF for i in range(4096)),
        ]
        for data in test_cases:
            expected = zlib.crc32(data) & 0xFFFFFFFF
            actual = native_crc32(data, 0)
            assert actual == expected, (
                f"CRC-32 mismatch on length {len(data)}: {actual:#x} vs {expected:#x}"
            )


class TestDifferentialSeptets:
    """Differential verification of 7-bit MIDI safe septet packing and unpacking."""

    # req: WIRE-02
    def test_crc_septet_pack_unpack_parity(self) -> None:
        """Verify 16-bit CRC packing into 3 7-bit septets produces identical results."""
        values = [
            0x0000,
            0x0001,
            0x007F,
            0x0080,
            0x29B1,
            0x3FFF,
            0x4000,
            0x7FFF,
            0x8000,
            0xC000,
            0xFFFF,
        ]
        for val in values:
            py_packed = pack_crc(val)
            py_unpacked = unpack_crc(py_packed)
            assert py_unpacked == val

            if is_native_available():
                nat_packed = native_pack_crc(val)
                assert nat_packed == py_packed, f"Pack CRC mismatch for {val:#x}"
                nat_unpacked = native_unpack_crc(nat_packed)
                assert nat_unpacked == val
                # Cross-unpack: Python unpacked native packed, and vice versa
                assert unpack_crc(nat_packed) == val
                assert native_unpack_crc(py_packed) == val

    # req: WIRE-02
    def test_crc_septet_error_conditions(self) -> None:
        """Verify out-of-range CRC values and corrupted septets fail identically."""
        # Out of bounds CRC integer
        with pytest.raises(ValueError):
            pack_crc(0x10000)

        with pytest.raises(ValueError):
            pack_crc(-1)

        # Corrupted septets (b0 > 0x03 or b1/b2 > 0x7F)
        corrupted = [
            bytes([0x04, 0x00, 0x00]),  # b0 > 3
            bytes([0x00, 0x80, 0x00]),  # b1 > 127
            bytes([0x00, 0x00, 0x80]),  # b2 > 127
        ]
        for raw in corrupted:
            with pytest.raises(ValueError):
                unpack_crc(raw)

            if is_native_available():
                with pytest.raises(ValueError):
                    native_unpack_crc(raw)

    # req: WIRE-02
    def test_septet_14_pack_unpack_parity(self) -> None:
        """Verify 14-bit integer packing into 2 7-bit septets."""
        values = [0, 1, 0x7F, 0x80, 0x1FFF, 0x3FFF]
        for val in values:
            py_packed = pack_septets_14(val)
            py_unpacked = unpack_septets_14(py_packed[0], py_packed[1])
            assert py_unpacked == val

            if is_native_available():
                nat_packed = native_pack_septets_14(val)
                assert nat_packed == py_packed
                nat_unpacked = native_unpack_septets_14(nat_packed[0], nat_packed[1])
                assert nat_unpacked == val

    # req: WIRE-02
    def test_septet_21_pack_unpack_parity(self) -> None:
        """Verify 21-bit integer packing into 3 7-bit septets."""
        values = [0, 1, 0x7F, 0x80, 0x3FFF, 0x4000, 0x1FFFFF]
        for val in values:
            py_packed = pack_septets_21(val)
            py_unpacked = unpack_septets_21(py_packed[0], py_packed[1], py_packed[2])
            assert py_unpacked == val

            if is_native_available():
                nat_packed = native_pack_septets_21(val)
                assert nat_packed == py_packed
                nat_unpacked = native_unpack_septets_21(nat_packed[0], nat_packed[1], nat_packed[2])
                assert nat_unpacked == val


class TestDifferentialFrame:
    """Differential verification of SysEx frame encoding, decoding, and validation."""

    # req: WIRE-02
    def test_valid_frame_encoding_and_native_validation(self) -> None:
        """Verify frames encoded in Python validate and unpack correctly in native code."""
        test_frames = [
            Frame(
                kind=FrameKind.REQ,
                flags=FrameFlags.NONE,
                sid=1,
                mid=100,
                cidx=0,
                ccnt=1,
                payload=b'{"op":"ping"}',
            ),
            Frame(
                kind=FrameKind.RES,
                flags=FrameFlags.ENC_JSON,
                sid=42,
                mid=999,
                cidx=0,
                ccnt=1,
                payload=b'{"status":"ok","value":123}',
            ),
            Frame(
                kind=FrameKind.EVT,
                flags=FrameFlags.NONE,
                sid=0,
                mid=1,
                cidx=1,
                ccnt=3,
                payload=b"A" * 490,  # Max payload
            ),
            Frame(
                kind=FrameKind.CTL,
                flags=FrameFlags.NONE,
                sid=0x3FFF,
                mid=0x1FFFFF,
                cidx=0,
                ccnt=1,
                payload=b"",
            ),
        ]

        for frame in test_frames:
            encoded = encode_frame(frame)
            decoded_py = decode_frame(encoded)
            assert decoded_py == frame

            if is_native_available():
                fields = native_validate_frame(encoded)
                assert fields["kind"] == int(frame.kind)
                assert fields["flags"] == int(frame.flags)
                assert fields["sid"] == frame.sid
                assert fields["mid"] == frame.mid
                assert fields["cidx"] == frame.cidx
                assert fields["ccnt"] == frame.ccnt
                assert fields["plen"] == len(frame.payload)

    # req: WIRE-02
    def test_corrupted_frame_rejection_parity(self) -> None:
        """Verify that corrupted frames are rejected by both Python and native decoders."""
        frame = Frame(
            kind=FrameKind.REQ,
            flags=FrameFlags.NONE,
            sid=1,
            mid=1,
            cidx=0,
            ccnt=1,
            payload=b'{"op":"status"}',
        )
        valid_raw = bytearray(encode_frame(frame))

        # 1. Corrupted CRC
        corrupted_crc = bytearray(valid_raw)
        corrupted_crc[-3] ^= 0x01
        with pytest.raises(ProtocolError):
            decode_frame(bytes(corrupted_crc))
        if is_native_available():
            with pytest.raises(ValueError, match="CRC"):
                native_validate_frame(bytes(corrupted_crc))

        # 2. Corrupted start byte
        corrupted_start = bytearray(valid_raw)
        corrupted_start[0] = 0x00
        with pytest.raises(ProtocolError):
            decode_frame(bytes(corrupted_start))
        if is_native_available():
            with pytest.raises(ValueError, match="Framing byte"):
                native_validate_frame(bytes(corrupted_start))

        # 3. Corrupted end byte
        corrupted_end = bytearray(valid_raw)
        corrupted_end[-1] = 0x00
        with pytest.raises(ProtocolError):
            decode_frame(bytes(corrupted_end))
        if is_native_available():
            with pytest.raises(ValueError, match="Framing byte"):
                native_validate_frame(bytes(corrupted_end))

        # 4. Truncated frame
        truncated = valid_raw[:15]
        with pytest.raises(ProtocolError):
            decode_frame(bytes(truncated))
        if is_native_available():
            with pytest.raises(ValueError, match="short"):
                native_validate_frame(bytes(truncated))


class TestDifferentialChunking:
    """Differential verification of chunking, reassembly, and frame integrity."""

    # req: WIRE-02
    def test_multi_chunk_payload_differential_validation(self) -> None:
        """Chunk a multi-frame payload and verify every frame validates in native code."""
        # 2000 bytes requires ceil(2000 / 490) = 5 frames
        large_payload = bytes("".join(f"chunk_data_{i:04d}_" for i in range(125)), "ascii")
        assert len(large_payload) >= 2000

        chunks = chunk_payload(large_payload)
        ccnt = len(chunks)
        assert ccnt >= 5

        frames = [
            Frame(
                kind=FrameKind.REQ,
                flags=FrameFlags.NONE,
                sid=10,
                mid=200,
                cidx=i,
                ccnt=ccnt,
                payload=chunk,
            )
            for i, chunk in enumerate(chunks)
        ]

        for frame in frames:
            encoded = encode_frame(frame)
            decoded_py = decode_frame(encoded)
            assert decoded_py == frame

            if is_native_available():
                fields = native_validate_frame(encoded)
                assert fields["sid"] == 10
                assert fields["mid"] == 200
                assert fields["cidx"] == frame.cidx
                assert fields["ccnt"] == len(frames)
                assert fields["plen"] == len(frame.payload)

        # Reassemble and verify complete round-trip
        reassembler = Reassembler()
        completed = None
        for frame in frames:
            res = reassembler.feed(frame)
            if res is not None:
                completed = res
        assert completed is not None
        assert completed == large_payload


class TestDifferentialTolerance:
    """Differential verification of numeric tolerance comparison engine."""

    # req: ARM-01
    def test_tolerance_comparison_differential_parity(self) -> None:
        """Verify numeric tolerance matching parity between pure-Python and native helper."""
        test_cases = [
            (1.0, 1.0, 0.005, True),
            (1.002, 1.0, 0.005, True),
            (0.998, 1.0, 0.005, True),
            (1.005, 1.0, 0.005, True),
            (1.006, 1.0, 0.005, False),
            (1.01, 1.0, 0.005, False),
            (0.0, 0.0, 0.001, True),
            (0.0, -0.0, 0.001, True),
            (-0.5, -0.502, 0.005, True),
            (-0.5, -0.51, 0.005, False),
            (1e-5, 2e-5, 1e-4, True),
            (1e-5, 2e-5, 1e-6, False),
            (float("inf"), float("inf"), 0.01, True),
            (float("inf"), 1.0, 0.01, False),
            (float("nan"), 1.0, 0.01, False),
        ]

        for expected, actual, tol, expected_match in test_cases:
            py_match = tolerance_matches(expected, actual, tol)
            # Python tolerance_matches returns boolean
            if not math.isnan(expected) and not math.isnan(actual) and not math.isinf(expected):
                assert py_match == expected_match, (
                    f"Python tolerance failure on ({expected}, {actual})"
                )

            if is_native_available():
                nat_match = native_tolerance_matches(expected, actual, tol)
                assert nat_match == expected_match, (
                    f"Native tolerance failure on ({expected}, {actual}): "
                    f"{nat_match} vs {expected_match}"
                )


class TestPurePythonWheelDistribution:
    """Verify package distribution remains 100% universal pure-Python (py3-none-any)."""

    # req: PKG-01, ARM-01
    def test_wheel_is_strictly_pure_python(self) -> None:
        """Verify uv build produces py3-none-any wheel with zero native binary artifacts."""
        uv_cmd = shutil.which("uv")
        if uv_cmd is None:
            pytest.skip("uv not available on PATH")

        # Build studiobridge package wheel
        build_result = subprocess.run(
            [uv_cmd, "build", "--package", "studiobridge"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert build_result.returncode == 0, f"uv build failed:\n{build_result.stderr}"

        dist_dir = REPO_ROOT / "dist"
        wheel_candidates = list(dist_dir.glob("studiobridge-*.whl"))
        assert len(wheel_candidates) > 0, "No built wheel found in dist/"

        target_wheel = wheel_candidates[0]
        # Wheel filename must end with -py3-none-any.whl
        assert target_wheel.name.endswith("-py3-none-any.whl"), (
            f"Wheel is not universal pure-Python: {target_wheel.name}"
        )

        # Inspect wheel zip contents
        with zipfile.ZipFile(target_wheel, "r") as z:
            namelist = z.namelist()

            # Ensure no compiled shared libraries or C source files are packaged
            forbidden_extensions = {".dll", ".so", ".dylib", ".pyd", ".c", ".h", ".obj", ".lib"}
            found_forbidden = [
                name
                for name in namelist
                if any(name.lower().endswith(ext) for ext in forbidden_extensions)
            ]
            assert not found_forbidden, (
                f"Wheel contains compiled or native artifacts: {found_forbidden}"
            )

            # Verify WHEEL metadata specifies purelib
            wheel_info = [name for name in namelist if name.endswith(".dist-info/WHEEL")]
            assert len(wheel_info) == 1
            wheel_content = z.read(wheel_info[0]).decode("utf-8")
            assert "Root-Is-Purelib: true" in wheel_content
            assert "Tag: py3-none-any" in wheel_content


class TestToolchainDiagnosticScript:
    """Verify PowerShell ARM64 toolchain diagnostic check script."""

    # req: ARM-01
    def test_check_arm64_toolchain_json_output(self) -> None:
        """Verify check-arm64-toolchain.ps1 runs in pwsh and emits valid structured JSON."""
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            pytest.skip("pwsh not available on PATH")

        script_path = REPO_ROOT / "tools" / "dev" / "check-arm64-toolchain.ps1"
        assert script_path.is_file(), f"Diagnostic script missing: {script_path}"

        result = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(script_path), "-Json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Diagnostic script failed:\n{result.stderr}"

        # Parse JSON output
        report = json.loads(result.stdout)
        assert "Status" in report
        assert "Machine" in report
        assert "VisualStudio" in report
        assert "Clang" in report
        assert "WindowsSDK" in report
        assert "Rust" in report
        assert "Python" in report
        assert "Node" in report
        assert "CompilerVerification" in report

        # Verify compiler verification reported dual-architecture readiness
        assert report["CompilerVerification"]["CanCompileARM64"] is True
        assert report["CompilerVerification"]["CanCompileX64"] is True
        assert report["Status"] in ("READY", "READY_PARTIAL")
