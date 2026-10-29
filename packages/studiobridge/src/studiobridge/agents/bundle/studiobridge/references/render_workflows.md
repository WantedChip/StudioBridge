# Audio Render Workflows, Job Tracking, and Audio Validation

StudioBridge coordinates high-quality audio renders, stem bounces, and preview exports directly from FL Studio projects.

## 1. The Render Pipeline

Rendering audio in FL Studio involves an asynchronous lifecycle:

```
[ Preflight Check ] ──> [ Job Initiation ] ──> [ Background Poll ] ──> [ Audio Metrics Validation ]
         │                                              │                            │
   (not saved / busy)                             (dialog block)               (clipped / silent)
         │                                              │                            │
         ▼                                              ▼                            ▼
  [ Reject / Wait ]                              [ Remedy / Dismiss ]         [ Flag Quality Error ]
```

## 2. Preflight Checks

Before triggering any render operation, agents must verify host readiness:
1. **Host State**: Ensure transport is stopped (`transport_get().isPlaying == false`).
2. **Project Saved**: Verify project path exists on disk (`project_get().path`). Rendering an unsaved project (`Untitled.flp`) can write to unexpected temp folders.
3. **Disk Space**: Verify target volume has at least 500 MB free for high-bitrate WAV exports.
4. **Output Directory**: Ensure the target export folder exists and is writable.

## 3. Render Execution and Job Tracking

### Initiating Render:
Render requests are initiated via the render tools suite:
```json
{
  "name": "render_start",
  "arguments": {
    "format": "wav",
    "quality": "high",
    "tail_mode": "cut",
    "output_path": "exports/mix_preview.wav"
  }
}
```

### Job Polling:
Renders execute asynchronously. Agents poll the active job ID:
```json
{
  "name": "render_poll",
  "arguments": {
    "job_id": "rnd_409"
  }
}
```

### Tracking States:
- `pending`: Export queued, FL Studio preparing buffers.
- `rendering`: Actively rendering; `progress` float between `0.0` and `1.0`.
- `completed`: WAV file finalized and closed on disk.
- `failed`: Render aborted or timed out. Look at `error` details.

## 4. Audio Quality Validation Metrics

Once `render_poll` reports `status: "completed"`, the output audio file undergoes automated acoustic validation (`render/validate.py`):

| Metric | Target / Threshold | Purpose |
|---|---|---|
| **File Integrity** | Header valid, size > 1 KB | Detects zero-byte corruption or incomplete write |
| **Duration Check** | Within ±0.5s of song length | Verifies entire arrangement was bounced without early cut-off |
| **Peak Level** | `<= 0.0 dBFS` (target: -0.3 dBFS) | Flags digital clipping or over-the-ceiling distortion |
| **RMS Loudness** | `-24.0 dBFS` to `-8.0 dBFS` | Checks dynamic range and loudness consistency |
| **Silence Detection** | No consecutive silence > 2.0s | Detects empty bounces, missing sample paths, or muted buses |

### Audio Validator Output:
```json
{
  "valid": true,
  "duration_seconds": 128.4,
  "peak_dbfs": -0.42,
  "rms_dbfs": -14.1,
  "clipping_detected": false,
  "silent": false,
  "channels": 2,
  "sample_rate": 44100
}
```

## 5. Troubleshooting Render Failures

- **Render Never Starts**: FL Studio may have a modal dialog open (e.g. "Missing sample files" or "Plugin license trial"). Inspect `ui_status` or dismiss dialog.
- **Silent WAV Exported**: Check if mixer master track or target stem tracks were muted.
- **Clipping Detected**: If `peak_dbfs > 0.0 dBFS`, instruct the agent to reduce mixer bus gain (`mixer_set`) before re-rendering.
