"""Audio output validation, acoustic metrics, and corruption detection [RND-05].

Provides pure-Python audio validation routines for exported render artifacts
(WAV, MP3, FLAC, OGG), peak clipping analysis, silence ratio calculation,
and IEEE float NaN/Inf detection [RND-05]. Zero third-party C/native dependencies.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studiobridge.core.errors import InvalidOutputError


def linear_to_dbfs(linear: float, floor_dbfs: float = -120.0) -> float:
    """Convert linear amplitude ratio to decibels relative to full scale (dBFS).

    Args:
        linear: Linear amplitude value (typically 0.0 to 1.0+).
        floor_dbfs: Minimum dBFS floor returned for silent or sub-threshold signals.

    Returns:
        Amplitude in dBFS, clamped to floor_dbfs.
    """
    if linear <= 0.0 or math.isnan(linear):
        return floor_dbfs
    db = 20.0 * math.log10(linear)
    return max(floor_dbfs, db)


def dbfs_to_linear(dbfs: float) -> float:
    """Convert decibels relative to full scale (dBFS) to linear amplitude ratio.

    Args:
        dbfs: Amplitude in dBFS (e.g. -60.0).

    Returns:
        Linear amplitude ratio (e.g. 0.001 for -60 dBFS).
    """
    return 10.0 ** (dbfs / 20.0)


@dataclass
class AudioMetrics:
    """Acoustic and signal quality measurements for rendered audio [RND-05].

    Attributes:
        duration_s: Audio duration in seconds.
        sample_rate: Sampling frequency in Hertz.
        channels: Number of audio channels.
        bits_per_sample: Bit depth per sample (16, 24, 32, 64).
        format_name: Audio container/codec format ('wav', 'mp3', 'flac', 'ogg').
        total_frames: Total number of multi-channel sample frames.
        peak_linear: Peak absolute amplitude in linear scale [0.0, 1.0+].
        peak_dbfs: Peak amplitude in dBFS (clamped to floor, default -120.0).
        rms_linear: Root-mean-square signal energy in linear scale.
        rms_dbfs: Root-mean-square energy in dBFS.
        silence_ratio: Fraction of frames below silence threshold [0.0, 1.0].
        clipping_count: Number of individual samples saturated at or above 0 dBFS / 1.0.
        nan_inf_count: Number of invalid NaN or Inf samples detected in float streams.
        file_size_bytes: Size of audio file in bytes.
    """

    duration_s: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bits_per_sample: int = 0
    format_name: str = "wav"
    total_frames: int = 0
    peak_linear: float = 0.0
    peak_dbfs: float = -120.0
    rms_linear: float = 0.0
    rms_dbfs: float = -120.0
    silence_ratio: float = 0.0
    clipping_count: int = 0
    nan_inf_count: int = 0
    file_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to JSON-serializable dictionary."""
        return {
            "duration_s": round(self.duration_s, 4),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bits_per_sample": self.bits_per_sample,
            "format": self.format_name,
            "total_frames": self.total_frames,
            "peak_linear": round(self.peak_linear, 6),
            "peak_dbfs": round(self.peak_dbfs, 2),
            "rms_linear": round(self.rms_linear, 6),
            "rms_dbfs": round(self.rms_dbfs, 2),
            "silence_ratio": round(self.silence_ratio, 4),
            "clipping_count": self.clipping_count,
            "nan_inf_count": self.nan_inf_count,
            "file_size_bytes": self.file_size_bytes,
        }


@dataclass
class ValidationSpec:
    """Validation thresholds and criteria for rendered audio.

    Attributes:
        min_duration_s: Minimum acceptable duration in seconds (default 0.5s).
        max_silence_ratio: Maximum silence ratio before flagging as silent render (default 0.98).
        silence_threshold_dbfs: Signal level in dBFS below which a frame is considered silent
            (default -60.0).
        max_clipping_events: Maximum allowed clipping samples, or None for no limit (default None).
        allow_clipping: If False and clipping_count > 0, validation fails (default True).
        min_file_size_bytes: Minimum non-zero file size in bytes (default 128 bytes).
        check_nan_inf: Whether to fail validation on NaN/Inf samples (default True).
        require_valid: If True, validation failure raises InvalidOutputError (default True).
    """

    min_duration_s: float = 0.5
    max_silence_ratio: float = 0.98
    silence_threshold_dbfs: float = -60.0
    max_clipping_events: int | None = None
    allow_clipping: bool = True
    min_file_size_bytes: int = 128
    check_nan_inf: bool = True
    require_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert validation specification to dictionary."""
        return {
            "min_duration_s": self.min_duration_s,
            "max_silence_ratio": self.max_silence_ratio,
            "silence_threshold_dbfs": self.silence_threshold_dbfs,
            "max_clipping_events": self.max_clipping_events,
            "allow_clipping": self.allow_clipping,
            "min_file_size_bytes": self.min_file_size_bytes,
            "check_nan_inf": self.check_nan_inf,
            "require_valid": self.require_valid,
        }


@dataclass
class AudioValidationResult:
    """Outcome of audio file validation."""

    is_valid: bool
    file_path: Path
    format_name: str
    metrics: AudioMetrics
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "file_path": str(self.file_path),
            "format": self.format_name,
            "metrics": self.metrics.to_dict(),
            "error_message": self.error_message,
            "warnings": self.warnings,
        }


class AudioValidator:
    """Pure-Python audio validator and signal quality analyzer [RND-05].

    Validates exported audio artifacts across WAV, MP3, FLAC, and OGG formats.
    Computes acoustic metrics (peak, RMS, silence ratio, clipping count) and
    detects corrupted or silent renders without native dependencies.
    """

    def validate_file(
        self,
        file_path: Path | str,
        spec: ValidationSpec | None = None,
    ) -> AudioValidationResult:
        """Validate an audio file against a ValidationSpec.

        Args:
            file_path: Path to audio file.
            spec: Validation criteria and thresholds (default ValidationSpec()).

        Returns:
            AudioValidationResult containing status, metrics, and error messages.
        """
        spec = spec or ValidationSpec()
        path = Path(file_path)

        if not path.exists():
            return AudioValidationResult(
                is_valid=False,
                file_path=path,
                format_name="unknown",
                metrics=AudioMetrics(format_name="unknown"),
                error_message=f"Audio file does not exist: '{path}'",
            )

        file_size = path.stat().st_size
        if file_size == 0:
            return AudioValidationResult(
                is_valid=False,
                file_path=path,
                format_name="unknown",
                metrics=AudioMetrics(format_name="unknown", file_size_bytes=0),
                error_message="Render output is zero-byte empty file.",
            )

        suffix = path.suffix.lower()
        if suffix == ".wav":
            return self.validate_wav(path, spec)
        elif suffix == ".mp3":
            return self.validate_mp3(path, spec)
        elif suffix == ".flac":
            return self.validate_flac(path, spec)
        elif suffix in (".ogg", ".oga"):
            return self.validate_ogg(path, spec)

        # Magic byte detection if extension is absent or unrecognized
        if file_size >= 4:
            try:
                with open(path, "rb") as f:
                    magic = f.read(4)
                if magic == b"RIFF":
                    return self.validate_wav(path, spec)
                elif magic == b"fLaC":
                    return self.validate_flac(path, spec)
                elif magic == b"OggS":
                    return self.validate_ogg(path, spec)
                elif magic[:3] == b"ID3" or (magic[0] == 0xFF and (magic[1] & 0xE0) == 0xE0):
                    return self.validate_mp3(path, spec)
            except OSError as e:
                return AudioValidationResult(
                    is_valid=False,
                    file_path=path,
                    format_name="unknown",
                    metrics=AudioMetrics(format_name="unknown", file_size_bytes=file_size),
                    error_message=f"Cannot read file header: {e}",
                )

        return AudioValidationResult(
            is_valid=False,
            file_path=path,
            format_name="unknown",
            metrics=AudioMetrics(format_name="unknown", file_size_bytes=file_size),
            error_message=f"Unsupported audio format or unrecognized magic bytes: '{path.name}'",
        )

    def validate_or_raise(
        self,
        file_path: Path | str,
        spec: ValidationSpec | None = None,
    ) -> AudioValidationResult:
        """Validate audio file and raise InvalidOutputError if validation fails [RND-05].

        Args:
            file_path: Path to audio file.
            spec: Validation criteria and thresholds.

        Returns:
            AudioValidationResult if validation passes.

        Raises:
            InvalidOutputError: If output is invalid, empty, silent, or corrupted (E_RND_INVALID).
        """
        result = self.validate_file(file_path, spec)
        if not result.is_valid:
            msg = result.error_message or f"Audio validation failed for '{Path(file_path).name}'"
            raise InvalidOutputError(msg, code="E_RND_INVALID")
        return result

    def inspect(self, file_path: Path | str) -> AudioMetrics:
        """Inspect audio file and extract metrics without enforcing failure thresholds."""
        lenient_spec = ValidationSpec(
            min_duration_s=0.0,
            max_silence_ratio=1.0,
            min_file_size_bytes=1,
            allow_clipping=True,
            require_valid=False,
        )
        res = self.validate_file(file_path, lenient_spec)
        return res.metrics

    def validate_wav(self, file_path: Path, spec: ValidationSpec) -> AudioValidationResult:
        """Validate WAV container, parse fmt/data subchunks, and evaluate signal quality."""
        file_size = file_path.stat().st_size
        if file_size < spec.min_file_size_bytes:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="wav",
                metrics=AudioMetrics(format_name="wav", file_size_bytes=file_size),
                error_message=(
                    f"WAV file size ({file_size} bytes) is less than minimum "
                    f"{spec.min_file_size_bytes} bytes."
                ),
            )

        try:
            with open(file_path, "rb") as f:
                header = f.read(12)
                if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(format_name="wav", file_size_bytes=file_size),
                        error_message=(
                            "Invalid WAV header: missing RIFF/WAVE container magic bytes."
                        ),
                    )

                fmt_chunk: bytes | None = None
                data_offset: int | None = None
                data_size: int = 0

                offset = 12
                while offset < file_size:
                    f.seek(offset)
                    chunk_hdr = f.read(8)
                    if len(chunk_hdr) < 8:
                        break
                    chunk_id = chunk_hdr[:4]
                    chunk_sz = struct.unpack("<I", chunk_hdr[4:8])[0]
                    payload_offset = offset + 8

                    if chunk_id == b"fmt ":
                        fmt_chunk = f.read(chunk_sz)
                    elif chunk_id == b"data":
                        data_offset = payload_offset
                        data_size = chunk_sz
                        if fmt_chunk is not None:
                            break

                    offset = payload_offset + chunk_sz + (chunk_sz % 2)

                if fmt_chunk is None or len(fmt_chunk) < 16:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(format_name="wav", file_size_bytes=file_size),
                        error_message="Malformed WAV: missing or truncated 'fmt ' sub-chunk.",
                    )

                audio_fmt, channels, sample_rate, _byte_rate, block_align, bits_per_sample = (
                    struct.unpack("<HHIIHH", fmt_chunk[:16])
                )

                # Check for extensible WAVE format (0xFFFE)
                if audio_fmt == 0xFFFE and len(fmt_chunk) >= 40:
                    guid_prefix = struct.unpack("<H", fmt_chunk[24:26])[0]
                    if guid_prefix == 1:
                        audio_fmt = 1
                    elif guid_prefix == 3:
                        audio_fmt = 3

                if audio_fmt not in (1, 3):
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(
                            sample_rate=sample_rate,
                            channels=channels,
                            bits_per_sample=bits_per_sample,
                            format_name="wav",
                            file_size_bytes=file_size,
                        ),
                        error_message=(
                            f"Unsupported WAV audio format tag: {audio_fmt} "
                            "(only PCM format 1 and IEEE float format 3 supported)."
                        ),
                    )

                if data_offset is None:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(
                            sample_rate=sample_rate,
                            channels=channels,
                            bits_per_sample=bits_per_sample,
                            format_name="wav",
                            file_size_bytes=file_size,
                        ),
                        error_message="Malformed WAV: missing 'data' sub-chunk.",
                    )

                actual_data_bytes = file_size - data_offset
                if actual_data_bytes < data_size:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(
                            sample_rate=sample_rate,
                            channels=channels,
                            bits_per_sample=bits_per_sample,
                            format_name="wav",
                            file_size_bytes=file_size,
                        ),
                        error_message=(
                            f"WAV audio chunk is truncated: header declares {data_size} "
                            f"data bytes, but file only contains {actual_data_bytes} bytes."
                        ),
                    )

                if channels <= 0 or sample_rate <= 0 or block_align <= 0:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="wav",
                        metrics=AudioMetrics(
                            sample_rate=sample_rate,
                            channels=channels,
                            bits_per_sample=bits_per_sample,
                            format_name="wav",
                            file_size_bytes=file_size,
                        ),
                        error_message=(
                            f"Invalid WAV parameters: channels={channels}, "
                            f"sample_rate={sample_rate}, block_align={block_align}."
                        ),
                    )

                bytes_per_sample = bits_per_sample // 8
                if bytes_per_sample * channels != block_align:
                    block_align = bytes_per_sample * channels

                total_frames = data_size // block_align
                duration_s = total_frames / sample_rate if sample_rate > 0 else 0.0

                # Analyze audio signal samples
                silence_linear_threshold = dbfs_to_linear(spec.silence_threshold_dbfs)
                peak_linear = 0.0
                sum_squares = 0.0
                total_samples = 0
                silent_frames = 0
                clipping_count = 0
                nan_inf_count = 0

                f.seek(data_offset)
                bytes_remaining = data_size
                chunk_frames = 4096
                read_block_sz = chunk_frames * block_align

                if audio_fmt == 1 and bits_per_sample == 16:
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, read_block_sz)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        bytes_remaining -= len(buf)
                        samples = struct.unpack(f"<{len(buf) // 2}h", buf)
                        for i in range(0, len(samples), channels):
                            frame = samples[i : i + channels]
                            frame_max = 0.0
                            for s in frame:
                                if s >= 32767 or s <= -32768:
                                    clipping_count += 1
                                s_norm = s / 32768.0
                                abs_s = abs(s_norm)
                                if abs_s > frame_max:
                                    frame_max = abs_s
                                sum_squares += s_norm * s_norm
                                total_samples += 1
                            if frame_max > peak_linear:
                                peak_linear = frame_max
                            if frame_max < silence_linear_threshold:
                                silent_frames += 1

                elif audio_fmt == 1 and bits_per_sample == 24:
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, read_block_sz)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        bytes_remaining -= len(buf)
                        samples_norm: list[float] = []
                        for i in range(0, len(buf) - 2, 3):
                            s = int.from_bytes(buf[i : i + 3], byteorder="little", signed=True)
                            if s >= 8388607 or s <= -8388608:
                                clipping_count += 1
                            samples_norm.append(s / 8388608.0)
                        for i in range(0, len(samples_norm), channels):
                            frame = samples_norm[i : i + channels]
                            frame_max = 0.0
                            for s_norm in frame:
                                abs_s = abs(s_norm)
                                if abs_s > frame_max:
                                    frame_max = abs_s
                                sum_squares += s_norm * s_norm
                                total_samples += 1
                            if frame_max > peak_linear:
                                peak_linear = frame_max
                            if frame_max < silence_linear_threshold:
                                silent_frames += 1

                elif audio_fmt == 1 and bits_per_sample == 32:
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, read_block_sz)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        bytes_remaining -= len(buf)
                        samples = struct.unpack(f"<{len(buf) // 4}i", buf)
                        for i in range(0, len(samples), channels):
                            frame = samples[i : i + channels]
                            frame_max = 0.0
                            for s in frame:
                                if s >= 2147483647 or s <= -2147483648:
                                    clipping_count += 1
                                s_norm = s / 2147483648.0
                                abs_s = abs(s_norm)
                                if abs_s > frame_max:
                                    frame_max = abs_s
                                sum_squares += s_norm * s_norm
                                total_samples += 1
                            if frame_max > peak_linear:
                                peak_linear = frame_max
                            if frame_max < silence_linear_threshold:
                                silent_frames += 1

                elif audio_fmt == 3 and bits_per_sample == 32:
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, read_block_sz)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        bytes_remaining -= len(buf)
                        samples = struct.unpack(f"<{len(buf) // 4}f", buf)
                        for i in range(0, len(samples), channels):
                            frame = samples[i : i + channels]
                            frame_max = 0.0
                            for s in frame:
                                if math.isnan(s) or math.isinf(s):
                                    nan_inf_count += 1
                                    continue
                                abs_s = abs(s)
                                if abs_s >= 1.0:
                                    clipping_count += 1
                                if abs_s > frame_max:
                                    frame_max = abs_s
                                sum_squares += s * s
                                total_samples += 1
                            if frame_max > peak_linear:
                                peak_linear = frame_max
                            if frame_max < silence_linear_threshold:
                                silent_frames += 1

                elif audio_fmt == 3 and bits_per_sample == 64:
                    while bytes_remaining > 0:
                        to_read = min(bytes_remaining, read_block_sz)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        bytes_remaining -= len(buf)
                        samples = struct.unpack(f"<{len(buf) // 8}d", buf)
                        for i in range(0, len(samples), channels):
                            frame = samples[i : i + channels]
                            frame_max = 0.0
                            for s in frame:
                                if math.isnan(s) or math.isinf(s):
                                    nan_inf_count += 1
                                    continue
                                abs_s = abs(s)
                                if abs_s >= 1.0:
                                    clipping_count += 1
                                if abs_s > frame_max:
                                    frame_max = abs_s
                                sum_squares += s * s
                                total_samples += 1
                            if frame_max > peak_linear:
                                peak_linear = frame_max
                            if frame_max < silence_linear_threshold:
                                silent_frames += 1

                rms_linear = math.sqrt(sum_squares / total_samples) if total_samples > 0 else 0.0
                silence_ratio = silent_frames / total_frames if total_frames > 0 else 1.0
                peak_dbfs = linear_to_dbfs(peak_linear)
                rms_dbfs = linear_to_dbfs(rms_linear)

                metrics = AudioMetrics(
                    duration_s=duration_s,
                    sample_rate=sample_rate,
                    channels=channels,
                    bits_per_sample=bits_per_sample,
                    format_name="wav",
                    total_frames=total_frames,
                    peak_linear=peak_linear,
                    peak_dbfs=peak_dbfs,
                    rms_linear=rms_linear,
                    rms_dbfs=rms_dbfs,
                    silence_ratio=silence_ratio,
                    clipping_count=clipping_count,
                    nan_inf_count=nan_inf_count,
                    file_size_bytes=file_size,
                )

                warnings: list[str] = []
                error_message: str | None = None

                if spec.check_nan_inf and nan_inf_count > 0:
                    error_message = (
                        f"Invalid IEEE float stream: detected {nan_inf_count} NaN/Inf samples."
                    )
                elif duration_s < spec.min_duration_s:
                    error_message = (
                        f"Audio duration {duration_s:.3f}s is less than minimum "
                        f"{spec.min_duration_s:.3f}s."
                    )
                elif silence_ratio > spec.max_silence_ratio:
                    error_message = (
                        f"Render is silent: silence ratio {silence_ratio:.1%} exceeds threshold "
                        f"{spec.max_silence_ratio:.1%} "
                        f"(threshold {spec.silence_threshold_dbfs:.1f} dBFS)."
                    )
                elif not spec.allow_clipping and clipping_count > 0:
                    error_message = (
                        f"Audio clipping detected: {clipping_count} saturated samples "
                        "(>= 0.0 dBFS)."
                    )
                elif (
                    spec.max_clipping_events is not None
                    and clipping_count > spec.max_clipping_events
                ):
                    error_message = (
                        f"Audio clipping count {clipping_count} exceeds allowed limit "
                        f"{spec.max_clipping_events}."
                    )

                if clipping_count > 0 and spec.allow_clipping:
                    warnings.append(
                        f"Peak clipping observed: {clipping_count} saturated samples (>= 0.0 dBFS)."
                    )

                return AudioValidationResult(
                    is_valid=error_message is None,
                    file_path=file_path,
                    format_name="wav",
                    metrics=metrics,
                    error_message=error_message,
                    warnings=warnings,
                )

        except Exception as e:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="wav",
                metrics=AudioMetrics(format_name="wav", file_size_bytes=file_size),
                error_message=f"Failed to parse WAV file: {e}",
            )

    def validate_flac(self, file_path: Path, spec: ValidationSpec) -> AudioValidationResult:
        """Validate FLAC container and STREAMINFO metadata header block."""
        file_size = file_path.stat().st_size
        if file_size < spec.min_file_size_bytes:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="flac",
                metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                error_message=(
                    f"FLAC file size ({file_size} bytes) is less than minimum "
                    f"{spec.min_file_size_bytes} bytes."
                ),
            )

        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b"fLaC":
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="flac",
                        metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                        error_message="Invalid FLAC container: missing 'fLaC' magic marker.",
                    )

                block_hdr = f.read(4)
                if len(block_hdr) < 4:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="flac",
                        metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                        error_message="Malformed FLAC: missing metadata block header.",
                    )

                block_type = block_hdr[0] & 0x7F
                block_len = (block_hdr[1] << 16) | (block_hdr[2] << 8) | block_hdr[3]

                if block_type != 0 or block_len < 34:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="flac",
                        metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                        error_message=(
                            "Malformed FLAC: first metadata block must be STREAMINFO (type 0)."
                        ),
                    )

                streaminfo = f.read(34)
                if len(streaminfo) < 34:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="flac",
                        metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                        error_message="Malformed FLAC: truncated STREAMINFO block.",
                    )

                # Bytes 10..17 (8 bytes) encode sample rate (20b), channels-1 (3b),
                # bits_per_sample-1 (5b), and total samples (36b)
                b10, b11, b12, b13, b14, b15, b16, b17 = streaminfo[10:18]
                sample_rate = (b10 << 12) | (b11 << 4) | (b12 >> 4)
                channels = ((b12 >> 1) & 0x07) + 1
                bits_per_sample = (((b12 & 0x01) << 4) | (b13 >> 4)) + 1
                total_samples = ((b13 & 0x0F) << 32) | (b14 << 24) | (b15 << 16) | (b16 << 8) | b17

                duration_s = total_samples / sample_rate if sample_rate > 0 else 0.0

                metrics = AudioMetrics(
                    duration_s=duration_s,
                    sample_rate=sample_rate,
                    channels=channels,
                    bits_per_sample=bits_per_sample,
                    format_name="flac",
                    total_frames=total_samples,
                    file_size_bytes=file_size,
                )

                error_message = None
                if duration_s < spec.min_duration_s:
                    error_message = (
                        f"Audio duration {duration_s:.3f}s is less than minimum "
                        f"{spec.min_duration_s:.3f}s."
                    )

                return AudioValidationResult(
                    is_valid=error_message is None,
                    file_path=file_path,
                    format_name="flac",
                    metrics=metrics,
                    error_message=error_message,
                )

        except Exception as e:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="flac",
                metrics=AudioMetrics(format_name="flac", file_size_bytes=file_size),
                error_message=f"Failed to parse FLAC file: {e}",
            )

    def validate_ogg(self, file_path: Path, spec: ValidationSpec) -> AudioValidationResult:
        """Validate OGG container, Vorbis/Opus headers, and estimated duration."""
        file_size = file_path.stat().st_size
        if file_size < spec.min_file_size_bytes:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="ogg",
                metrics=AudioMetrics(format_name="ogg", file_size_bytes=file_size),
                error_message=(
                    f"OGG file size ({file_size} bytes) is less than minimum "
                    f"{spec.min_file_size_bytes} bytes."
                ),
            )

        try:
            with open(file_path, "rb") as f:
                magic = f.read(4)
                if magic != b"OggS":
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="ogg",
                        metrics=AudioMetrics(format_name="ogg", file_size_bytes=file_size),
                        error_message="Invalid OGG container: missing 'OggS' container header.",
                    )

                # Read remaining first page header
                page_hdr = f.read(23)
                if len(page_hdr) < 23:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="ogg",
                        metrics=AudioMetrics(format_name="ogg", file_size_bytes=file_size),
                        error_message="Malformed OGG: truncated first page header.",
                    )

                num_segments = page_hdr[22]
                segment_table = f.read(num_segments)
                first_packet_size = segment_table[0] if segment_table else 0

                first_packet = f.read(first_packet_size)
                sample_rate = 44100
                channels = 2
                bits_per_sample = 16
                nominal_bitrate = 128000

                if first_packet.startswith(b"\x01vorbis") and len(first_packet) >= 28:
                    channels = first_packet[11]
                    sample_rate = struct.unpack("<I", first_packet[12:16])[0]
                    nominal_bitrate = struct.unpack("<I", first_packet[20:24])[0] or 128000
                elif first_packet.startswith(b"OpusHead") and len(first_packet) >= 12:
                    channels = first_packet[9]
                    sample_rate = struct.unpack("<I", first_packet[12:16])[0]
                    nominal_bitrate = 128000

                # Seek near end to inspect last OggS page for total granule position
                seek_offset = max(0, file_size - 65536)
                f.seek(seek_offset)
                tail = f.read()
                last_idx = tail.rfind(b"OggS")
                duration_s = 0.0
                total_frames = 0

                if last_idx != -1 and last_idx + 14 <= len(tail):
                    granule = struct.unpack("<q", tail[last_idx + 6 : last_idx + 14])[0]
                    if granule > 0 and sample_rate > 0:
                        total_frames = granule
                        duration_s = total_frames / sample_rate

                if duration_s <= 0.0 and nominal_bitrate > 0:
                    # Fallback duration estimate from nominal bitrate and file size
                    duration_s = (file_size * 8.0) / nominal_bitrate
                    total_frames = int(duration_s * sample_rate)

                metrics = AudioMetrics(
                    duration_s=duration_s,
                    sample_rate=sample_rate,
                    channels=channels,
                    bits_per_sample=bits_per_sample,
                    format_name="ogg",
                    total_frames=total_frames,
                    file_size_bytes=file_size,
                )

                error_message = None
                if duration_s < spec.min_duration_s:
                    error_message = (
                        f"Audio duration {duration_s:.3f}s is less than minimum "
                        f"{spec.min_duration_s:.3f}s."
                    )

                return AudioValidationResult(
                    is_valid=error_message is None,
                    file_path=file_path,
                    format_name="ogg",
                    metrics=metrics,
                    error_message=error_message,
                )

        except Exception as e:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="ogg",
                metrics=AudioMetrics(format_name="ogg", file_size_bytes=file_size),
                error_message=f"Failed to parse OGG file: {e}",
            )

    def validate_mp3(self, file_path: Path, spec: ValidationSpec) -> AudioValidationResult:
        """Validate MP3 ID3v2 container, sync frame headers, and estimated duration."""
        file_size = file_path.stat().st_size
        if file_size < spec.min_file_size_bytes:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="mp3",
                metrics=AudioMetrics(format_name="mp3", file_size_bytes=file_size),
                error_message=(
                    f"MP3 file size ({file_size} bytes) is less than minimum "
                    f"{spec.min_file_size_bytes} bytes."
                ),
            )

        try:
            with open(file_path, "rb") as f:
                head = f.read(10)
                offset = 0
                if head.startswith(b"ID3") and len(head) >= 10:
                    # Synchsafe integer size in bytes 6..9
                    b0, b1, b2, b3 = head[6:10]
                    id3_size = (b0 << 21) | (b1 << 14) | (b2 << 7) | b3
                    offset = 10 + id3_size

                f.seek(offset)
                search_buf = f.read(4096)
                if len(search_buf) < 4:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="mp3",
                        metrics=AudioMetrics(format_name="mp3", file_size_bytes=file_size),
                        error_message="Malformed MP3: no audio data following ID3 tag.",
                    )

                sync_idx = -1
                for i in range(len(search_buf) - 3):
                    if search_buf[i] == 0xFF and (search_buf[i + 1] & 0xE0) == 0xE0:
                        sync_idx = i
                        break

                if sync_idx == -1:
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="mp3",
                        metrics=AudioMetrics(format_name="mp3", file_size_bytes=file_size),
                        error_message="Invalid MP3: MPEG audio sync frame header not found.",
                    )

                hdr = search_buf[sync_idx : sync_idx + 4]
                version_bits = (hdr[1] >> 3) & 0x03
                layer_bits = (hdr[1] >> 1) & 0x03
                bitrate_idx = (hdr[2] >> 4) & 0x0F
                samplerate_idx = (hdr[2] >> 2) & 0x03
                channel_mode = (hdr[3] >> 6) & 0x03

                if layer_bits != 1:  # Layer III is value 1 (0b01)
                    return AudioValidationResult(
                        is_valid=False,
                        file_path=file_path,
                        format_name="mp3",
                        metrics=AudioMetrics(format_name="mp3", file_size_bytes=file_size),
                        error_message=(
                            "Unsupported MPEG audio layer: only Layer III (MP3) supported."
                        ),
                    )

                # Lookup tables
                # version_bits: 3=MPEG1, 2=MPEG2, 0=MPEG2.5
                sample_rate_tables = {
                    3: [44100, 48000, 32000],
                    2: [22050, 24000, 16000],
                    0: [11025, 12000, 8000],
                }
                sample_rates = sample_rate_tables.get(version_bits, [44100, 48000, 32000])
                sample_rate = (
                    sample_rates[samplerate_idx] if samplerate_idx < len(sample_rates) else 44100
                )

                # Bitrates for Layer III (kbps)
                if version_bits == 3:  # MPEG 1
                    bitrate_table = [
                        0,
                        32,
                        40,
                        48,
                        56,
                        64,
                        80,
                        96,
                        112,
                        128,
                        160,
                        192,
                        224,
                        256,
                        320,
                    ]
                else:
                    bitrate_table = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]

                bitrate_kbps = (
                    bitrate_table[bitrate_idx] if bitrate_idx < len(bitrate_table) else 128
                )
                channels = 1 if channel_mode == 3 else 2

                # Estimate duration from audio payload bytes and bitrate
                audio_payload_bytes = max(0, file_size - offset)
                duration_s = (
                    (audio_payload_bytes * 8.0) / (bitrate_kbps * 1000.0)
                    if bitrate_kbps > 0
                    else 0.0
                )
                total_frames = int(duration_s * sample_rate)

                metrics = AudioMetrics(
                    duration_s=duration_s,
                    sample_rate=sample_rate,
                    channels=channels,
                    bits_per_sample=16,
                    format_name="mp3",
                    total_frames=total_frames,
                    file_size_bytes=file_size,
                )

                error_message = None
                if duration_s < spec.min_duration_s:
                    error_message = (
                        f"Audio duration {duration_s:.3f}s is less than minimum "
                        f"{spec.min_duration_s:.3f}s."
                    )

                return AudioValidationResult(
                    is_valid=error_message is None,
                    file_path=file_path,
                    format_name="mp3",
                    metrics=metrics,
                    error_message=error_message,
                )

        except Exception as e:
            return AudioValidationResult(
                is_valid=False,
                file_path=file_path,
                format_name="mp3",
                metrics=AudioMetrics(format_name="mp3", file_size_bytes=file_size),
                error_message=f"Failed to parse MP3 file: {e}",
            )
