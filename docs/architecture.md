# StudioBridge Architecture & Wire Protocol

StudioBridge provides a robust, zero-kernel-driver control architecture bridging modern AI coding agents, developer CLI tooling, and Python automation scripts to FL Studio on Windows.

---

## 1. Architectural Topology

```
+--------------------------------------------------------------------------------+
|                             AI AGENT / HOST PROCESS                            |
|             Claude Desktop | Cursor | Windsurf | Copilot | Python CLI          |
+--------------------------------------------------------------------------------+
                                        |
                                        | JSON-RPC 2.0 (stdio) / HTTP REST (/v1)
                                        v
+--------------------------------------------------------------------------------+
|                         STUDIOBRIDGE BROKER DAEMON                             |
|       Loopback Interface (127.0.0.1) | Bearer Token Auth | Request Scheduler   |
|         Mutation Journal (MID) | Safety Mode Interlock | Write Verification     |
+--------------------------------------------------------------------------------+
          |                       |                     |                |
          | Plane 1               | Plane 2             | Plane 3        | Plane 4
          v                       v                     v                v
+-------------------+   +------------------+   +---------------+   +-------------+
| Live MIDI SysEx   |   | Win32 UI         |   | Headless      |   | Offline     |
| 2-Way RPC Bus     |   | Actuator Guard   |   | Render Sup.   |   | FLP Engine  |
+-------------------+   +------------------+   +---------------+   +-------------+
          |                       |                     |                |
          | WinMM / WMS Loopback  | Win32 Window API    | Child Process  | File I/O
          v                       v                     v                v
+--------------------------------------------------------------------------------+
|                                  FL STUDIO                                     |
|  Controller Script (Python 3.9) | Mixer | Channels | Piano Roll | FL64.exe     |
+--------------------------------------------------------------------------------+
```

---

## 2. The Four Control Planes

### Plane 1: Live MIDI SysEx 2-Way RPC Bus

StudioBridge uses standard MIDI System Exclusive (SysEx) messages as a bidirectional Remote Procedure Call (RPC) transport between the host Python broker and FL Studio's controller script context.

- **Framing & Protocol:**
  - Standard framing bytes: `0xF0` (Start of SysEx) to `0xF7` (End of SysEx).
  - Manufacturer ID: `0x00 0x21 0x7E` (Educational & Research assignment).
  - 7-bit MIDI encoding: All binary payload bytes are packed into 7-bit septets to guarantee zero high-bit collision with MIDI status bytes.
- **Reliability & Data Integrity:**
  - CRC-16/CCITT-FALSE validation on every frame.
  - Automatic frame chunking and reassembly for payloads exceeding 256 bytes.
  - HMAC-SHA256 message authentication on all mutating calls.
  - Monotonic Mutation ID (`MID`) tracking to reject replay attacks and dropped packets.
- **Round-Trip Latency:** Typical loopback round-trip response time is under 1.0 ms (measured p50: 0.42 ms on Windows MIDI Services).

### Plane 2: Win32 UI Actuator & Window Guard

Operations that are not exposed via FL Studio's MIDI scripting API (such as executing Piano Roll helper scripts) are handled through the Win32 UI Actuator:

- **Focus Verification:** Ensures FL Studio is the active foreground window before injecting keyboard shortcuts or menu events.
- **Modal Dialog Guard:** Detects blocking dialog windows and modal popups, preventing automation deadlocks.
- **Cursor Position Restoration:** Saves and restores the human user's mouse cursor position across actuation cycles.

### Plane 3: Headless Render Supervisor

StudioBridge orchestrates high-fidelity audio rendering without user interaction:

- **Command Line Invocation:** Launches `FL64.exe` with command line switches (`/R /Fwav /E /O<outdir> <project.flp>`).
- **Process Supervision:** Monitors memory consumption, CPU utilization, and standard output streams, enforcing strict timeout guards.
- **Acoustic Signal Validation:** Automatically inspects the rendered audio file:
  - Validates WAV header and sample rate (44.1 kHz / 48 kHz).
  - Computes RMS energy and true peak levels to verify audio is not silent or hard-clipping.

### Plane 4: Offline FLP Binary Engine

For project file generation, batch inspection, and offline editing, StudioBridge includes a clean-room, pure-Python binary `.flp` parser and serializer:

- **Lossless Round-Trip:** Guarantees bit-exact or semantically preserved project round-tripping.
- **Structural Invariants:** Validates event order, project header structures, channel configurations, and mixer routing prior to saving.
- **Atomic File Replacement:** Writes to temporary staging files before renaming, preventing file corruption if interrupted.

---

## 3. Broker Daemon & Security Model

The StudioBridge Broker Daemon acts as the single point of entry and safety controller:

1. **Strict Loopback Binding:**
   - The broker binds exclusively to `127.0.0.1` (or local IPC named pipes). Remote network connections are rejected at the socket layer.
2. **Bearer Token Authentication:**
   - Every connection must authenticate within 2.0 seconds by presenting the secret token generated in `%LOCALAPPDATA%\studiobridge\broker.token`.
   - Token comparison uses constant-time `hmac.compare_digest` to prevent timing attacks.
3. **Safety Modes & Interlocks:**
   - `READ_ONLY` (default): Mutations return a confirmation challenge token requiring user or agent approval.
   - `PROMPT`: Mutations require approval for high-risk targets (Master track volume, track deletion).
   - `PERMISSIVE`: Allowed for automated test harnesses only.
4. **Verified Writes & Mutation Journal:**
   - Every write operation triggers an immediate read-back query.
   - The read-back value is compared against the target using tolerance thresholds.
   - All mutations, receipts, and rollback snapshots are recorded in the local append-only mutation journal (`sbridge journal`).

---

## 4. Zero Native Dependency Design on Windows

StudioBridge follows a strict **zero-native-dependency** architecture:

- **Pure Python Wheel:** StudioBridge distributes as a universal `py3-none-any` wheel with zero compiled C/C++ requirements.
- **Windows MIDI Routing:** Uses Python's standard `ctypes` library to bind directly to the Windows Multimedia API (`winmm.dll`) and Windows MIDI Services (`midisrv`).
- **Driverless Operation:** On Windows 11 Build 26100+, StudioBridge leverages the built-in Windows MIDI Services loopback driver, eliminating third-party kernel driver requirements (such as `loopMIDI`).
- **Optional Accelerators:** If a C compiler is present, optional native acceleration DLLs (for CRC-16 and septet packing) can be compiled, but the pure-Python fallback is always 100% feature-complete and bit-exact.

---

## 5. Controller Script Sandbox

Code executing inside FL Studio runs in an isolated Python 3.9 runtime:

- Imports are restricted strictly to Python built-in modules (`sys`, `time`, `struct`, `math`) and FL Studio's native scripting namespaces (`mixer`, `transport`, `channels`, `patterns`, `plugins`, `ui`, `general`, `device`).
- No socket connections, no `ctypes`, and no filesystem writes are permitted inside the controller script context. All IPC occurs through the MIDI SysEx interface.
