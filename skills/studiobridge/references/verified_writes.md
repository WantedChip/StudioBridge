# Verified Writes, Tolerances, and Receipts

Digital Audio Workstations (DAWs) like FL Studio process parameters through non-linear curves, smoothing filters, internal decibel conversions, and GUI thread synchronization. Writing a parameter does not guarantee the DAW immediately or accurately reached that state.

StudioBridge solves this with the **Verified Write Loop** (`[VER-01..04]`).

## 1. The Verified Write Architecture

Every mutating operation in StudioBridge executes the following pipeline:

```
[Target Value] ──> [Apply Write] ──> [Read-Back Probe] ──> [Tolerance Check] ──> [Receipt & Journal]
                                                                  │
                                                          (mismatch > tol)
                                                                  │
                                                                  ▼
                                                      [UnverifiedWriteError]
                                                                  │
                                                                  ▼
                                                      [Compensating Rollback]
```

1. **Pre-flight & Read-Before-Write**: Current parameter value is cached.
2. **Apply Write**: Sysex command is sent across the wire protocol to the FL controller script.
3. **Read-Back Probe**: SDK queries the host state for the active value.
4. **Tolerance Comparison**: Evaluates `abs(expected - actual) <= tolerance`.
5. **Receipt Generation**: Emits structured receipt with `verified: true`, `plane`, and `journal_id`.
6. **Journal Recording**: Mutation is appended to the monotonic audit journal.

## 2. Parameter Tolerances & Unit Conversions

FL Studio normalizes most UI sliders (volume, pan, stereo separation) to the range `[0.0, 1.0]`, which maps logarithmically to decibels or linear pan angles.

### Declared Tolerances:

| Parameter / API Function | Tolerance Margin | Rationale |
|---|---|---|
| `mixer.setTrackVolume` | `0.01` (~0.2 dB) | Internal 32-bit float to 14-bit MIDI quantization |
| `mixer.setTrackPan` | `0.01` | Non-linear pan law centering deadband |
| `channels.setChannelVolume`| `0.01` | Channel rack fader interpolation |
| `channels.setChannelPan` | `0.01` | Panning curve smoothing |
| `transport.setTempo` | `0.005` (0.01 BPM) | High-precision tempo clock quantization |
| `transport.setSongPos` | `0.01` | PPQ (Pulses Per Quarter) tick grid quantization |
| **Default Fallback** | `0.005` | Standard numeric comparison threshold |

### Decibel and Linear Units:
- Always use the helper methods or declare whether values are normalized (`0.0 - 1.0`) or in decibels (`dB`).
- When setting `volume=0.80`, this represents FL Studio's default 0 dB unity gain.
- A volume of `0.0` represents silence (-infinity dB); `1.0` represents +5.6 dB boost.

## 3. Proof Levels

StudioBridge defines three verification proof levels (`V1-A3`):

1. **`readback`**: Parameter is re-queried from the host engine via getter API and compared. This is the standard for mixer, channels, transport, and patterns.
2. **`display_only`**: Host returns UI hint without an authoritative numerical engine getter. Verified if UI state changed.
3. **`none`**: One-way commands (e.g. `general.undo`, window focus). No readback possible; reported as `verified: true` with proof level `none`.

## 4. Structured Write Receipts

Every mutating tool returns a receipt block:

```json
{
  "verified": true,
  "plane": "live",
  "journal_id": 142,
  "details": {
    "track": 3,
    "volume": 0.70,
    "actual": 0.701,
    "tolerance": 0.01
  }
}
```

- `verified`: `true` if within tolerance, `false` otherwise.
- `plane`: `"live"` for hardware/WMS loopback connection, `"emulator"` for test runner.
- `journal_id`: Integer index for audit tracing and selective rollback.

## 5. Checkpoints and Rollback Guarantees

StudioBridge provides checkpointing and atomic transactions:

### Checkpoint Operations:
```json
// Create checkpoint before major edits
{
  "name": "checkpoint_create",
  "arguments": {
    "name": "pre_mix_balance"
  }
}
```

```json
// Revert all edits made since checkpoint
{
  "name": "checkpoint_rollback",
  "arguments": {
    "checkpoint_id": "cp_101"
  }
}
```

### Rollback Guarantee Levels:
- **G0 (None)**: Irreversible operations (audio rendering, disk saving). Cannot be rolled back.
- **G1 (Best Effort)**: Rollback executed via inverse compensating operations or `general.undo()`, but not all targets were read-back verified.
- **G2 (Verified)**: Every mutated target was restored to its exact `before` state and verified within tolerance.
