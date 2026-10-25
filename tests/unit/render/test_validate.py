"""Unit tests for audio output validators and sidecar metadata generator [RND-05].

Tests WAV RIFF chunk decoding (PCM 16/24/32-bit, IEEE float 32/64-bit), acoustic metrics
(peak linear/dBFS, RMS linear/dBFS, silence ratio, clipping detection), NaN/Inf detection,
non-WAV format parsing (MP3, FLAC, OGG), corruption rejection, and sidecar metadata emission.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from studiobridge.core.errors import InvalidOutputError
from studiobridge.render.discover import FlInstall
from studiobridge.render.job import JobState, RenderJob
from studiobridge.render.runner import RenderRunner
from studiobridge.render.sidecar import (
    SidecarMetadata,
    build_sidecar_dict,
    read_sidecar,
    resolve_sidecar_paths,
    write_sidecar,
)
from studiobridge.render.validate import (
    AudioMetrics,
    AudioValidator,
    ValidationSpec,
    dbfs_to_linear,
    linear_to_dbfs,
)

# --- Helper Generators for Synthetic Audio Fixtures ---


@pytest.fixture
def sample_flp(tmp_path: Path) -> Path:
    """Create a sample source project file."""
    p = tmp_path / "MyProject.flp"
    p.write_bytes(b"FLhd\x06\x00\x00\x00\x01\x00\x00\x00\x60\x00FLdtMockProjectData")
    return p


@pytest.fixture
def mock_fl_install(tmp_path: Path) -> FlInstall:
    """Create a mock FL Studio installation reference."""
    fl_dir = tmp_path / "FL Studio 2026"
    fl_dir.mkdir(parents=True, exist_ok=True)
    fl64 = fl_dir / "FL64.exe"
    fl64.write_bytes(b"mock_binary")
    return FlInstall(
        path=fl_dir,
        exe_path=fl64,
        name="FL Studio 2026",
        major=26,
        minor=1,
        build=3,
        revision=5570,
        architecture="x64",
        is_emulated=False,
        version_str="26.1.3.5570",
    )


def create_pcm_wav(
    dest: Path,
    channels: int = 2,
    sample_rate: int = 44100,
    bits_per_sample: int = 16,
    duration_s: float = 1.0,
    frequency_hz: float = 440.0,
    amplitude: float = 0.5,
) -> Path:
    """Generate a valid synthetic PCM WAV file with a pure sine tone."""
    total_frames = int(sample_rate * duration_s)
    bytes_per_sample = bits_per_sample // 8
    block_align = channels * bytes_per_sample
    data_size = total_frames * block_align
    riff_size = 36 + data_size

    samples_data = bytearray()
    for frame_idx in range(total_frames):
        t = frame_idx / sample_rate
        val = amplitude * math.sin(2.0 * math.pi * frequency_hz * t)
        for _ in range(channels):
            if bits_per_sample == 16:
                int_val = int(val * 32767.0)
                samples_data.extend(struct.pack("<h", int_val))
            elif bits_per_sample == 24:
                int_val = int(val * 8388607.0)
                samples_data.extend(int_val.to_bytes(3, byteorder="little", signed=True))
            elif bits_per_sample == 32:
                int_val = int(val * 2147483647.0)
                samples_data.extend(struct.pack("<i", int_val))

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    dest.write_bytes(header + samples_data)
    return dest


def create_float_wav(
    dest: Path,
    channels: int = 2,
    sample_rate: int = 48000,
    bits_per_sample: int = 32,
    duration_s: float = 1.0,
    amplitude: float = 0.6,
    inject_nan: bool = False,
    inject_inf: bool = False,
) -> Path:
    """Generate a valid synthetic IEEE float WAV file (format 3)."""
    total_frames = int(sample_rate * duration_s)
    bytes_per_sample = bits_per_sample // 8
    block_align = channels * bytes_per_sample
    data_size = total_frames * block_align
    riff_size = 36 + data_size

    samples_data = bytearray()
    fmt_char = "<f" if bits_per_sample == 32 else "<d"

    for frame_idx in range(total_frames):
        t = frame_idx / sample_rate
        val = amplitude * math.sin(2.0 * math.pi * 440.0 * t)

        if inject_nan and frame_idx == 100:
            val = float("nan")
        elif inject_inf and frame_idx == 200:
            val = float("inf")

        for _ in range(channels):
            samples_data.extend(struct.pack(fmt_char, val))

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        3,  # IEEE Float
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    dest.write_bytes(header + samples_data)
    return dest


def create_silent_wav(dest: Path, duration_s: float = 1.0) -> Path:
    """Generate a completely silent 16-bit PCM WAV file."""
    channels = 2
    sample_rate = 44100
    total_frames = int(sample_rate * duration_s)
    data_size = total_frames * channels * 2
    riff_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * 4,
        4,
        16,
        b"data",
        data_size,
    )
    dest.write_bytes(header + (b"\x00" * data_size))
    return dest


def create_clipping_wav(dest: Path, num_clipped_samples: int = 50) -> Path:
    """Generate a 16-bit PCM WAV file with intentional rail-saturated samples."""
    channels = 1
    sample_rate = 44100
    duration_s = 1.0
    total_frames = int(sample_rate * duration_s)
    data_size = total_frames * 2
    riff_size = 36 + data_size

    samples_data = bytearray()
    for i in range(total_frames):
        if i < num_clipped_samples:
            samples_data.extend(struct.pack("<h", 32767))
        else:
            samples_data.extend(struct.pack("<h", 1000))

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    dest.write_bytes(header + samples_data)
    return dest


def create_synthetic_flac(dest: Path, duration_s: float = 1.0) -> Path:
    """Generate a synthetic FLAC file with a valid STREAMINFO block."""
    sample_rate = 44100
    channels = 2
    bits_per_sample = 16
    total_samples = int(sample_rate * duration_s)

    # 4-byte magic marker
    content = bytearray(b"fLaC")

    # Metadata block header: bit 7 = 1 (last-metadata-block flag), type 0 (STREAMINFO), length 34
    content.extend(struct.pack(">B", 0x80))
    content.extend(b"\x00\x00\x22")  # 34 in 24-bit int

    # STREAMINFO payload (34 bytes)
    # min/max block size (4 bytes), min/max frame size (6 bytes)
    content.extend(b"\x10\x00\x10\x00")
    content.extend(b"\x00\x00\x00\x00\x00\x00")

    # 8 bytes encoding: sample_rate (20b), channels-1 (3b),
    # bits_per_sample-1 (5b), total_samples (36b)
    ch_bits = channels - 1
    bps_bits = bits_per_sample - 1
    combined = (
        (sample_rate << 44) | (ch_bits << 41) | (bps_bits << 36) | (total_samples & 0xFFFFFFFFF)
    )
    content.extend(combined.to_bytes(8, byteorder="big"))

    # MD5 signature: 16 bytes
    content.extend(b"\x00" * 16)

    # Dummy audio frame payload
    content.extend(b"\xff\xf8" + b"\x00" * 200)

    dest.write_bytes(content)
    return dest


def create_synthetic_ogg(dest: Path, duration_s: float = 1.0) -> Path:
    """Generate a synthetic Ogg Vorbis file with valid container pages."""
    sample_rate = 44100
    channels = 2
    nominal_bitrate = 128000
    total_samples = int(sample_rate * duration_s)

    content = bytearray()

    # First page: Vorbis identification header packet (30 bytes)
    vorbis_id = bytearray()
    vorbis_id.extend(b"\x01vorbis")
    vorbis_id.extend(struct.pack("<I", 0))  # version
    vorbis_id.extend(struct.pack("<B", channels))
    vorbis_id.extend(struct.pack("<I", sample_rate))
    vorbis_id.extend(struct.pack("<I", 0))  # max bitrate
    vorbis_id.extend(struct.pack("<I", nominal_bitrate))
    vorbis_id.extend(struct.pack("<I", 0))  # min bitrate
    vorbis_id.extend(b"\xb8\x01")  # blocksize, framing

    # Page 1 Header
    content.extend(b"OggS")
    content.extend(b"\x00")  # version
    content.extend(b"\x02")  # header type: BOS (beginning of stream)
    content.extend(struct.pack("<q", 0))  # granule position 0
    content.extend(struct.pack("<I", 0x12345678))  # serial
    content.extend(struct.pack("<I", 0))  # page seq 0
    content.extend(struct.pack("<I", 0))  # CRC
    content.extend(struct.pack("<B", 1))  # 1 segment
    content.extend(struct.pack("<B", len(vorbis_id)))  # segment length
    content.extend(vorbis_id)

    # Final page: encodes total granule position
    content.extend(b"OggS")
    content.extend(b"\x00")
    content.extend(b"\x04")  # EOS (end of stream)
    content.extend(struct.pack("<q", total_samples))  # final granule position
    content.extend(struct.pack("<I", 0x12345678))
    content.extend(struct.pack("<I", 1))
    content.extend(struct.pack("<I", 0))
    content.extend(struct.pack("<B", 1))
    content.extend(struct.pack("<B", 100))
    content.extend(b"\x00" * 100)

    dest.write_bytes(content)
    return dest


def create_synthetic_mp3(dest: Path, duration_s: float = 1.0) -> Path:
    """Generate a synthetic MP3 with ID3v2 header and valid MPEG-1 Layer III frames."""
    sample_rate = 44100
    bitrate_kbps = 128
    channels = 2

    content = bytearray()

    # ID3v2.3 header (10 bytes header + 10 bytes padding)
    content.extend(b"ID3\x03\x00\x00")
    content.extend(b"\x00\x00\x00\x0a")  # 10 bytes tag size
    content.extend(b"\x00" * 10)

    # Frame length for MPEG-1 Layer III 128 kbps 44.1 kHz is ~417 bytes
    frame_len = 144 * (bitrate_kbps * 1000) // sample_rate
    num_frames = max(1, int((duration_s * sample_rate) / 1152))

    for _ in range(num_frames):
        # MPEG-1 Layer III frame sync header
        frame_hdr = bytearray()
        frame_hdr.append(0xFF)
        frame_hdr.append(0xFB)  # MPEG1, Layer 3, no CRC
        frame_hdr.append(0x90)  # 128 kbps, 44100 Hz, padding=0
        channel_mode = 0xC0 if channels == 1 else 0x00
        frame_hdr.append(channel_mode)
        content.extend(frame_hdr)
        content.extend(b"\x00" * (frame_len - 4))

    dest.write_bytes(content)
    return dest


# --- Unit Tests ---


def test_linear_dbfs_conversions():
    """Verify linear amplitude to dBFS conversion roundtrips accurately.

    # req: RND-05
    """
    assert linear_to_dbfs(1.0) == 0.0
    assert round(linear_to_dbfs(0.5), 2) == -6.02
    assert linear_to_dbfs(0.0) == -120.0
    assert linear_to_dbfs(-1.0) == -120.0
    assert linear_to_dbfs(float("nan")) == -120.0

    assert round(dbfs_to_linear(0.0), 4) == 1.0
    assert round(dbfs_to_linear(-6.0206), 4) == 0.5
    assert round(dbfs_to_linear(-60.0), 6) == 0.001


def test_pcm_16bit_wav_validation(tmp_path: Path):
    """Verify 16-bit PCM WAV parses sample rate, channels, RMS, and peak accurately.

    # req: RND-05
    """
    wav_path = tmp_path / "valid_pcm16.wav"
    create_pcm_wav(
        wav_path,
        channels=2,
        sample_rate=44100,
        bits_per_sample=16,
        duration_s=1.0,
        amplitude=0.5,
    )

    validator = AudioValidator()
    result = validator.validate_file(wav_path)

    assert result.is_valid is True
    assert result.format_name == "wav"
    assert result.metrics.sample_rate == 44100
    assert result.metrics.channels == 2
    assert result.metrics.bits_per_sample == 16
    assert abs(result.metrics.duration_s - 1.0) < 0.01
    assert abs(result.metrics.peak_linear - 0.5) < 0.01
    assert abs(result.metrics.peak_dbfs - (-6.02)) < 0.2
    # Sine RMS is amplitude / sqrt(2) = 0.5 * 0.7071 = 0.3535
    assert abs(result.metrics.rms_linear - 0.3535) < 0.05
    assert result.metrics.clipping_count == 0
    assert result.metrics.silence_ratio < 0.05
    assert result.metrics.nan_inf_count == 0


def test_pcm_24bit_and_32bit_wav_validation(tmp_path: Path):
    """Verify 24-bit and 32-bit int PCM WAV parsing and acoustic calculations.

    # req: RND-05
    """
    validator = AudioValidator()

    # 24-bit PCM
    wav_24 = tmp_path / "valid_pcm24.wav"
    create_pcm_wav(
        wav_24,
        channels=1,
        sample_rate=48000,
        bits_per_sample=24,
        duration_s=0.8,
        amplitude=0.75,
    )
    res_24 = validator.validate_file(wav_24)
    assert res_24.is_valid is True
    assert res_24.metrics.sample_rate == 48000
    assert res_24.metrics.channels == 1
    assert res_24.metrics.bits_per_sample == 24
    assert abs(res_24.metrics.peak_linear - 0.75) < 0.01

    # 32-bit int PCM
    wav_32 = tmp_path / "valid_pcm32.wav"
    create_pcm_wav(
        wav_32,
        channels=2,
        sample_rate=96000,
        bits_per_sample=32,
        duration_s=0.6,
        amplitude=0.8,
    )
    res_32 = validator.validate_file(wav_32)
    assert res_32.is_valid is True
    assert res_32.metrics.sample_rate == 96000
    assert res_32.metrics.channels == 2
    assert res_32.metrics.bits_per_sample == 32
    assert abs(res_32.metrics.peak_linear - 0.8) < 0.01


def test_ieee_float_wav_validation(tmp_path: Path):
    """Verify IEEE float WAV (format 3, 32-bit and 64-bit) validation.

    # req: RND-05
    """
    validator = AudioValidator()

    # 32-bit float
    wav_f32 = tmp_path / "valid_float32.wav"
    create_float_wav(
        wav_f32,
        channels=2,
        sample_rate=48000,
        bits_per_sample=32,
        duration_s=1.0,
        amplitude=0.7,
    )
    res_f32 = validator.validate_file(wav_f32)
    assert res_f32.is_valid is True
    assert res_f32.metrics.bits_per_sample == 32
    assert abs(res_f32.metrics.peak_linear - 0.7) < 0.01
    assert res_f32.metrics.nan_inf_count == 0

    # 64-bit float
    wav_f64 = tmp_path / "valid_float64.wav"
    create_float_wav(
        wav_f64,
        channels=1,
        sample_rate=44100,
        bits_per_sample=64,
        duration_s=0.7,
        amplitude=0.4,
    )
    res_f64 = validator.validate_file(wav_f64)
    assert res_f64.is_valid is True
    assert res_f64.metrics.bits_per_sample == 64
    assert abs(res_f64.metrics.peak_linear - 0.4) < 0.01


def test_ieee_float_nan_and_inf_detection(tmp_path: Path):
    """Verify IEEE float streams containing NaN or Inf fail validation.

    # req: RND-05
    """
    validator = AudioValidator()

    # NaN detection
    wav_nan = tmp_path / "corrupted_nan.wav"
    create_float_wav(wav_nan, inject_nan=True)
    res_nan = validator.validate_file(wav_nan)
    assert res_nan.is_valid is False
    assert res_nan.metrics.nan_inf_count > 0
    assert "NaN/Inf" in (res_nan.error_message or "")

    # Inf detection
    wav_inf = tmp_path / "corrupted_inf.wav"
    create_float_wav(wav_inf, inject_inf=True)
    res_inf = validator.validate_file(wav_inf)
    assert res_inf.is_valid is False
    assert res_inf.metrics.nan_inf_count > 0
    assert "NaN/Inf" in (res_inf.error_message or "")

    # validate_or_raise raises InvalidOutputError
    with pytest.raises(InvalidOutputError) as exc_info:
        validator.validate_or_raise(wav_nan)
    assert exc_info.value.code == "E_RND_INVALID"


def test_silent_render_rejection(tmp_path: Path):
    """Verify silent audio exceeding max_silence_ratio threshold fails validation.

    # req: RND-05
    """
    wav_silent = tmp_path / "silent.wav"
    create_silent_wav(wav_silent, duration_s=1.0)

    validator = AudioValidator()
    spec = ValidationSpec(max_silence_ratio=0.98, silence_threshold_dbfs=-60.0)
    result = validator.validate_file(wav_silent, spec=spec)

    assert result.is_valid is False
    assert result.metrics.silence_ratio == 1.0
    assert "silent" in (result.error_message or "").lower()
    assert result.metrics.peak_linear == 0.0

    with pytest.raises(InvalidOutputError) as exc_info:
        validator.validate_or_raise(wav_silent, spec=spec)
    assert exc_info.value.code == "E_RND_INVALID"


def test_clipping_detection_and_thresholds(tmp_path: Path):
    """Verify clipping sample count tracking and clipping limit enforcement.

    # req: RND-05
    """
    wav_clip = tmp_path / "clipped.wav"
    create_clipping_wav(wav_clip, num_clipped_samples=25)

    validator = AudioValidator()

    # When clipping is allowed without count limit, it passes with warnings
    res_warn = validator.validate_file(
        wav_clip,
        spec=ValidationSpec(allow_clipping=True, max_clipping_events=None),
    )
    assert res_warn.is_valid is True
    assert res_warn.metrics.clipping_count == 25
    assert len(res_warn.warnings) > 0
    assert "clipping observed" in res_warn.warnings[0].lower()

    # When clipping is disallowed, it fails
    res_fail_clip = validator.validate_file(
        wav_clip,
        spec=ValidationSpec(allow_clipping=False),
    )
    assert res_fail_clip.is_valid is False
    assert "clipping detected" in (res_fail_clip.error_message or "").lower()

    # When max_clipping_events is exceeded, it fails
    res_fail_count = validator.validate_file(
        wav_clip,
        spec=ValidationSpec(allow_clipping=True, max_clipping_events=10),
    )
    assert res_fail_count.is_valid is False
    assert "exceeds allowed limit" in (res_fail_count.error_message or "").lower()


def test_corrupted_and_truncated_wav_detection(tmp_path: Path):
    """Verify zero-byte, truncated, and malformed WAV headers are rejected.

    # req: RND-05
    """
    validator = AudioValidator()

    # Zero-byte file
    zero_wav = tmp_path / "zero.wav"
    zero_wav.write_bytes(b"")
    res_zero = validator.validate_file(zero_wav)
    assert res_zero.is_valid is False
    assert "zero-byte" in (res_zero.error_message or "").lower()

    # Non-existent file
    res_missing = validator.validate_file(tmp_path / "missing.wav")
    assert res_missing.is_valid is False
    assert "does not exist" in (res_missing.error_message or "").lower()

    # Missing RIFF magic
    bad_magic = tmp_path / "bad_magic.wav"
    bad_magic.write_bytes(b"NOPE" + b"\x00" * 200)
    res_magic = validator.validate_file(bad_magic)
    assert res_magic.is_valid is False
    assert "magic" in (res_magic.error_message or "").lower()

    # Truncated data chunk (header claims 50,000 bytes, file has only 100 bytes)
    trunc_wav = tmp_path / "truncated.wav"
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        50036,
        b"WAVE",
        b"fmt ",
        16,
        1,
        2,
        44100,
        176400,
        4,
        16,
        b"data",
        50000,
    )
    trunc_wav.write_bytes(header + b"\x00" * 200)
    res_trunc = validator.validate_file(trunc_wav)
    assert res_trunc.is_valid is False
    assert "truncated" in (res_trunc.error_message or "").lower()


def test_duration_threshold_rejection(tmp_path: Path):
    """Verify audio files shorter than min_duration_s are rejected.

    # req: RND-05
    """
    short_wav = tmp_path / "short.wav"
    create_pcm_wav(short_wav, duration_s=0.2)

    validator = AudioValidator()
    spec = ValidationSpec(min_duration_s=0.5)
    result = validator.validate_file(short_wav, spec=spec)

    assert result.is_valid is False
    assert "less than minimum" in (result.error_message or "").lower()


def test_non_wav_flac_validation(tmp_path: Path):
    """Verify non-WAV FLAC container and STREAMINFO block parsing.

    # req: RND-05
    """
    flac_path = tmp_path / "sample.flac"
    create_synthetic_flac(flac_path, duration_s=1.0)

    validator = AudioValidator()
    result = validator.validate_file(flac_path)

    assert result.is_valid is True
    assert result.format_name == "flac"
    assert result.metrics.sample_rate == 44100
    assert result.metrics.channels == 2
    assert result.metrics.bits_per_sample == 16
    assert abs(result.metrics.duration_s - 1.0) < 0.01


def test_non_wav_ogg_validation(tmp_path: Path):
    """Verify non-WAV OGG container and Vorbis header parsing.

    # req: RND-05
    """
    ogg_path = tmp_path / "sample.ogg"
    create_synthetic_ogg(ogg_path, duration_s=1.0)

    validator = AudioValidator()
    result = validator.validate_file(ogg_path)

    assert result.is_valid is True
    assert result.format_name == "ogg"
    assert result.metrics.sample_rate == 44100
    assert result.metrics.channels == 2
    assert abs(result.metrics.duration_s - 1.0) < 0.05


def test_non_wav_mp3_validation(tmp_path: Path):
    """Verify non-WAV MP3 ID3v2 container and MPEG frame sync parsing.

    # req: RND-05
    """
    mp3_path = tmp_path / "sample.mp3"
    create_synthetic_mp3(mp3_path, duration_s=1.0)

    validator = AudioValidator()
    result = validator.validate_file(mp3_path)

    assert result.is_valid is True
    assert result.format_name == "mp3"
    assert result.metrics.sample_rate == 44100
    assert result.metrics.channels == 2
    assert result.metrics.duration_s > 0.5


def test_sidecar_path_resolution(tmp_path: Path):
    """Verify primary (.render.json) and compatibility alias (.meta.json) resolution.

    # req: RND-05
    """
    audio = tmp_path / "track.wav"
    primary, alias = resolve_sidecar_paths(audio)
    assert primary == tmp_path / "track.render.json"
    assert alias == tmp_path / "track.meta.json"

    # From primary
    p2, a2 = resolve_sidecar_paths(primary)
    assert p2 == primary
    assert a2 == alias

    # From alias
    p3, a3 = resolve_sidecar_paths(alias)
    assert p3 == primary
    assert a3 == alias


def test_sidecar_metadata_write_and_read(tmp_path: Path):
    """Verify write_sidecar and read_sidecar serialize and parse structured JSON.

    # req: RND-05
    """
    out_file = tmp_path / "rendered_song.wav"
    out_file.write_bytes(b"dummy")

    meta = SidecarMetadata(
        job_id="rnd-20261025-123456-abcdef",
        source="C:/Projects/Song.flp",
        source_hash="sha256-abcdef123456",
        fl_version="26.1.3.5570",
        fl_build="26.1.3.5570",
        fl_architecture="x64",
        is_emulated=False,
        formats=["wav"],
        output_files=["rendered_song.wav"],
        duration_s=3.456,
        validation_status="passed",
        created_at=1000.0,
        completed_at=1005.0,
        peak_linear=0.85,
        peak_dbfs=-1.41,
        rms_linear=0.45,
        rms_dbfs=-6.93,
        clipping_count=0,
        silence_ratio=0.01,
    )

    primary_path = write_sidecar(out_file, meta, create_alias=True)
    assert primary_path.exists()
    assert primary_path.name == "rendered_song.render.json"

    # Check compatibility alias was also written
    alias_path = tmp_path / "rendered_song.meta.json"
    assert alias_path.exists()

    # Read sidecar via primary path
    data = read_sidecar(primary_path)
    assert data["job_id"] == "rnd-20261025-123456-abcdef"
    assert data["source_hash"] == "sha256-abcdef123456"
    assert data["fl_build"] == "26.1.3.5570"
    assert data["peak_linear"] == 0.85
    assert data["peak_dbfs"] == -1.41
    assert data["clipping_count"] == 0
    assert data["validation_status"] == "passed"
    assert "timestamp" in data

    # Read sidecar via base audio file path
    data_from_audio = read_sidecar(out_file)
    assert data_from_audio["job_id"] == data["job_id"]


def test_build_sidecar_dict_helper():
    """Verify build_sidecar_dict helper populates all required metadata fields.

    # req: RND-05
    """
    metrics = AudioMetrics(
        duration_s=10.5,
        sample_rate=44100,
        channels=2,
        peak_linear=0.9,
        peak_dbfs=-0.92,
        rms_linear=0.3,
        rms_dbfs=-10.46,
        clipping_count=2,
        silence_ratio=0.05,
    )

    sidecar = build_sidecar_dict(
        job_id="job-999",
        source="project.flp",
        source_hash="hash-123",
        fl_build="26.1.0.0",
        duration_s=10.5,
        formats=["wav", "mp3"],
        output_files=["project.wav", "project.mp3"],
        validation_status="passed",
        metrics=metrics,
    )

    assert sidecar["job_id"] == "job-999"
    assert sidecar["source_hash"] == "hash-123"
    assert sidecar["fl_build"] == "26.1.0.0"
    assert sidecar["formats"] == ["wav", "mp3"]
    assert sidecar["duration_s"] == 10.5
    assert sidecar["peak_linear"] == 0.9
    assert sidecar["clipping_count"] == 2
    assert sidecar["validation_status"] == "passed"
    assert "settings_warning" in sidecar


def test_render_runner_validates_and_emits_sidecar(
    sample_flp: Path,
    mock_fl_install: FlInstall,
    tmp_path: Path,
):
    """Verify RenderRunner automatically validates output audio and writes sidecar metadata.

    # req: RND-05
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    out_dir = tmp_path / "valid_render_out"

    class ValidAudioPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 4444
            self._handle = 5555
            staged_flp_arg = Path(args[0][3])
            out_wav = staged_flp_arg.parent / f"{staged_flp_arg.stem}.wav"
            # Write a valid 16-bit PCM WAV (1 second sine tone)
            create_pcm_wav(out_wav, duration_s=1.0, amplitude=0.5)

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=ValidAudioPopen,
    )

    job = RenderJob(
        source=sample_flp,
        fl_install=mock_fl_install,
        out_dir=out_dir,
        validate=ValidationSpec(min_duration_s=0.5, max_silence_ratio=0.98),
    )

    completed_job = runner.run(job)

    assert completed_job.state == JobState.DONE
    assert len(completed_job.output_files) == 1
    assert completed_job.sidecar_path is not None
    assert completed_job.sidecar_path.exists()

    sidecar = read_sidecar(completed_job.sidecar_path)
    assert sidecar["job_id"] == completed_job.job_id
    assert sidecar["validation_status"] == "passed"
    assert sidecar["fl_build"] == "26.1.3.5570"
    assert sidecar["peak_linear"] > 0.0
    assert sidecar["clipping_count"] == 0


def test_render_runner_fails_on_silent_output(
    sample_flp: Path,
    mock_fl_install: FlInstall,
    tmp_path: Path,
):
    """Verify RenderRunner fails with E_RND_INVALID when rendered audio is silent.

    # req: RND-05
    """
    mock_wm = MagicMock()
    mock_wm.find_fl_windows.return_value = []

    out_dir = tmp_path / "silent_render_out"

    class SilentAudioPopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.pid = 4445
            self._handle = 5556
            staged_flp_arg = Path(args[0][3])
            out_wav = staged_flp_arg.parent / f"{staged_flp_arg.stem}.wav"
            # Write completely silent WAV
            create_silent_wav(out_wav, duration_s=1.0)

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

    runner = RenderRunner(
        window_mgr=mock_wm,
        popen_factory=SilentAudioPopen,
    )

    job = RenderJob(
        source=sample_flp,
        fl_install=mock_fl_install,
        out_dir=out_dir,
        validate=ValidationSpec(min_duration_s=0.5, max_silence_ratio=0.98),
    )

    with pytest.raises(InvalidOutputError) as exc_info:
        runner.run(job)

    assert exc_info.value.code == "E_RND_INVALID"
    assert "silent" in str(exc_info.value).lower()
    assert job.state == JobState.FAILED
    assert job.error_code == "E_RND_INVALID"

    # Sidecar should have been written with 'failed' status for debugging
    failed_sidecar = out_dir / f"{sample_flp.stem}.render.json"
    assert failed_sidecar.exists()
    sidecar_data = read_sidecar(failed_sidecar)
    assert sidecar_data["validation_status"] == "failed"
