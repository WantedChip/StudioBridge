---
title: "Control Planes Architecture"
description: "Deep dive into the four StudioBridge control planes: Live MIDI RPC, Offline FLP Engine, Headless Render Supervisor, and Win32 UI Actuation."
---

StudioBridge organizes DAW automation into **four distinct control planes**. Each plane operates under strict isolation boundaries, distinct timing guarantees, and dedicated safety interlocks.

```
+-------------------------------------------------------------------------+
|                           CODING AGENT / MCP                           |
+-------------------------------------------------------------------------+
       |                        |                      |             |
       v                        v                      v             v
+--------------+       +------------------+     +------------+ +-----------+
|  PLANE 1:    |       |    PLANE 2:      |     |  PLANE 3:  | | PLANE 4:  |
|  Live MIDI   |       |   Offline FLP    |     |  Headless  | | Win32 UI  |
|  SysEx RPC   |       |      Engine      |     |   Render   | | Actuation |
+--------------+       +------------------+     +------------+ +-----------+
       |                        |                      |             |
       v                        v                      v             v
 [FL Studio Host]      [.flp Binary File]       [FL64.exe CLI] [Win32 HWND]
 (Running Session)     (FL Closed or Open)      (Background)   (Modal Guards)
```

---

## The Four Control Planes

| Attribute | Plane 1: Live MIDI RPC | Plane 2: Offline FLP Engine | Plane 3: Headless Render | Plane 4: Win32 UI Actuation |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Target** | FL Studio active memory session | Binary `.flp` project file on disk | `FL64.exe` rendering engine | Win32 window subsystem |
| **FL Studio State** | **Must be running** | **Closed** (or offline file copy) | Background child process | FL Studio running |
| **Transport / Wire** | Virtual MIDI SysEx loopback | Direct disk file I/O | Win32 process spawning | Win32 API (`user32.dll`) |
| **Latency Profile** | Low latency: p50 < 3ms, p95 < 8ms | Sub-second: 50ms – 300ms | Project dependent: seconds to mins | Immediate: 10ms – 50ms |
| **Safety Interlock** | Read-only default + read-back verification | Mandatory `.flp.bak` timestamped checkpoint | Output file non-zero size verification | Window title & PID strict filtering |
| **Reversibility** | Instant undo (`sbridge rollback`) | Checkpoint restore (`.flp.bak`) | Output audio deletion / overwrite | Window dismissal state |

---

## 1. Plane 1: Live MIDI RPC Plane

The **Live MIDI RPC Plane** provides bidirectional, low-latency control over a running FL Studio instance. It operates by routing structured SysEx frames across virtual MIDI ports between the external Python daemon/agent and an internal Python controller script running inside FL Studio.

### The Device Script Sandbox
Code executing inside FL Studio operates under strict environment constraints:
- **Python 3.9 Runtime:** FL Studio's embedded script interpreter is standard Python 3.9.
- **Zero Native Dependencies:** No compiled C-extensions, no external `pip` packages, no `ctypes`, and no network sockets can be opened inside the script.
- **Single-Threaded Audio Host:** Scripts run synchronously on FL Studio's UI/message pump thread. Long-running or blocking calls cause audio dropouts. StudioBridge guarantees non-blocking frame dispatch.

### Timing & Heartbeat
- **Round-Trip Latency:** Typical round-trip time across the WMS loopback is 1.2ms to 2.8ms on modern Windows hardware.
- **Heartbeat & Keepalive:** A keepalive ping is exchanged every 1000ms. If no heartbeat is received for 3000ms, StudioBridge marks the session as disconnected and blocks mutating writes.

### Capabilities & Limitations
- **Allowed:** Transport controls (play, stop, record, tempo), mixer levels/pans/routing, channel parameters, pattern selection, and plugin parameter adjustment.
- **Disallowed / Impossible:** Dynamically instantiating new third-party VSTs from disk, loading raw WAV audio into samplers via script, or invoking unlicensed internal engine APIs (FL Studio API restrictions).

---

## 2. Plane 2: Offline FLP Engine

The **Offline FLP Engine** reads, validates, and mutates FL Studio project files (`.flp`) directly on disk without requiring FL Studio to be open or running.

### Clean-Room Architecture
- **Zero GPL Code:** Designed entirely from clean-room documentation and binary corpus verification.
- **Preservation of Unknown Chunks:** FL Studio project files contain proprietary vendor chunks and plugin states. StudioBridge parses the chunk stream, modifies only targeted events (e.g. tempo, channel names, note data), and preserves unknown binary chunks byte-for-byte.

### Safety Invariants & Checkpoints
- **Never Overwrite Implicitly:** StudioBridge will never save over an active project file without creating a timestamped backup (`project.flp.20261026_001200.bak`).
- **Binary Invariant Validation:** Before writing changes to disk, the engine verifies project header consistency, chunk byte counters, and checksums. If any invariant fails, the mutation aborts without touching the original file.

---

## 3. Plane 3: Headless Render Supervisor

The **Headless Render Supervisor** orchestrates background audio export by invoking FL Studio's headless command-line rendering flags:

```bash
FL64.exe /R /F"wav" /E"Dither,HQ" /O"C:\Output" "C:\Projects\Track.flp"
```

### Supervisor Guarantees
- **Process Isolation:** The render runs in a dedicated subprocess monitored by a watchdog timer.
- **Hang & Modal Dialog Detection:** If FL Studio gets blocked on an unresolved plugin dialog or missing sample prompt during export, the supervisor detects the freeze and reports a timeout failure rather than hanging the agent indefinitely.
- **Receipt Verification:** Following export, the supervisor checks the target filesystem:
  1. Verifies the rendered `.wav` / `.mp3` file exists.
  2. Asserts the file size is non-zero and greater than the minimum header threshold (≥ 44 bytes).
  3. Validates the RIFF header and sample rate.

---

## 4. Plane 4: Win32 UI Actuation Plane

The **Win32 UI Actuation Plane** handles interactions that are outside the scope of both MIDI scripting and offline file editing, such as dismissing modal dialogs, bringing the DAW window into focus, or handling plugin licensing prompts.

### Technical Implementation
- **Pure-Python Win32 Bindings:** Uses `ctypes.windll.user32` exclusively. No heavy binary dependencies (e.g. `pywin32`) are required.
- **Strict HWND Discipline:** Every actuation requires verifying the target window handle's Process ID against the discovered `FL64.exe` PID. StudioBridge will never send input to arbitrary desktop windows.
- **Gated Behind Capabilities:** UI actuation is gated behind capability flag `CAP_PIANO_ROLL_ACTUATION`. Agents cannot actuate the UI unless the user has opted in.

---

## Cross-Plane Consistency & Mutation Journal

Regardless of which plane executes a command, mutations are logged into a unified **Mutation Journal**:

1. **Transaction ID:** Each write generates a unique UUID `journal_id`.
2. **Pre-State & Post-State:** Records both the original value and the mutated value.
3. **Rollback Receipt:** Provides the exact inverse operation required to restore the previous state.
4. **Safety Level:**
   - `G0`: Fire-and-forget (unverified).
   - `G1`: Read-back verified (state confirmed).
   - `G2`: Reversible with verified rollback.
