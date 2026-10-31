# StudioBridge Compatibility & Capability Matrix

This compatibility matrix is derived from automated diagnostic runs and hardware verification suites executed on real physical hardware.

---

## 1. Capability Matrix Summary

| Capability | Category | FL 26 ARM64 | FL 26 x64 | FL 25 ARM64 | FL 25 x64 | FL 21 ARM64 | FL 21 x64 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Live Transport RPC** | Live Protocol | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Live Mixer Bus & Channel Strips** | Live Protocol | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Live Note Audition & Pattern Actuation** | Live Protocol | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Offline Binary FLP Parser** | Offline FLP Engine | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Offline FLP Mutation Engine** | Offline FLP Engine | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Structural Invariant Verification** | Offline FLP Engine | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Headless Audio Export & Supervisor** | Actuation & Render | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Piano Roll Script Actuation** | Actuation & Render | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Third-Party Plugin Instantiation** | Host Architecture | `UNAVAILABLE` | `UNAVAILABLE` | `UNAVAILABLE` | `UNAVAILABLE` | `UNAVAILABLE` | `UNAVAILABLE` |
| **Native ARM64 Host Execution** | System & Architecture | `DEGRADED` | `AVAILABLE` | `DEGRADED` | `AVAILABLE` | `DEGRADED` | `AVAILABLE` |
| **Offline Playlist Clip Creation** | Offline FLP Engine | `DEGRADED` | `DEGRADED` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |
| **Zero Proprietary Kernel Drivers** | System & Architecture | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` | `AVAILABLE` |

### Status Legend
- **`AVAILABLE`**: Fully implemented, verified against automated test suites, and operational in production.
- **`DEGRADED`**: Functional with known host-level constraints (e.g., FL Studio GUI executing under Prism x64 emulation on ARM64, or new schema chunk format variations in preview builds).
- **`UNAVAILABLE`**: Gated by capability flags due to DAW host limitations or safety boundaries (e.g. third-party VST GUI instantiation without native scripting API hooks).

---

## 2. Tested Reference Hardware

### Machine A (Windows on ARM64 Reference)
- **Model:** Microsoft Surface Pro 11th Edition
- **Processor:** Qualcomm Snapdragon X Elite (X1E-80-100, 12-core @ 3.4 GHz)
- **Memory:** 32 GB LPDDR5x (8448 MT/s)
- **Operating System:** Windows 11 Pro 24H2 (OS Build 10.0.26100)
- **MIDI Routing:** Windows MIDI Services (WMS) Loopback + pure ctypes WinMM (ARM64 native)
- **Python Runtime:** Python 3.12.7 (ARM64 native, `win_arm64`)
- **Health Check Status:** `HEALTHY (8 passed, 0 warned, 0 failed)`

### Machine B (Windows x64 Audio Workstation)
- **Model:** Custom Audio Workstation Rig
- **Processor:** AMD Ryzen 9 7950X (16-core / 32-thread @ 4.5 GHz base / 5.7 GHz boost)
- **Memory:** 64 GB DDR5-6000 CL30
- **Operating System:** Windows 11 Pro 24H2 (OS Build 10.0.26100)
- **MIDI Routing:** Windows MIDI Services (WMS) Loopback + pure ctypes WinMM (x64 native)
- **Python Runtime:** Python 3.12.7 (AMD64 native, `win_amd64`)
- **Health Check Status:** `HEALTHY (8 passed, 0 warned, 0 failed)`

### Community Diagnostic Submissions

| System Identifier | Processor / Platform | Windows OS Build | Architecture | Diagnostic Summary |
| :--- | :--- | :--- | :---: | :--- |
| `community_01_win10_x64` | Intel Core i7-10700K (8C/16T @ 3.8 GHz) | Windows 10 (10.0.19045) | `AMD64` | 7 passed, 1 warned, 0 failed |
| `community_02_win11_x64` | Intel Core i9-13900K (24C/32T @ 5.8 GHz) | Windows 11 (10.0.22631) | `AMD64` | 8 passed, 0 warned, 0 failed |
| `community_03_surface_arm64` | Microsoft SQ3 (8C @ 3.0 GHz) | Windows 11 (10.0.26100) | `ARM64` | 8 passed, 0 warned, 0 failed |

---

## 3. Capability Details & Rationales

### `CAP_LIVE_TRANSPORT` — Live Transport RPC
- **Category:** Live Protocol
- **Description:** Bidirectional SysEx RPC transport control for play, pause, record, seek, tempo, and beat position tracking.
- **Technical Rationale:** SysEx 2-way RPC transport protocol verified with 0.42 ms round-trip latency and zero frame loss.

### `CAP_LIVE_MIXER` — Live Mixer Bus & Channel Strips
- **Category:** Live Protocol
- **Description:** Volume faders, stereo panning, mute, solo, arming, peak level telemetry, and effects slot inspection.
- **Technical Rationale:** Full mixer strip control verified across master bus and all 125 mixer tracks with read-back tolerance verification.

### `CAP_LIVE_NOTES` — Live Note Audition & Pattern Actuation
- **Category:** Live Protocol
- **Description:** Sub-millisecond note triggering, chord auditions, velocity actuation, and live channel rack previewing.
- **Technical Rationale:** Note-on, note-off, velocity scaling, and pitch bend events execute cleanly in real-time over the virtual MIDI bus.

### `CAP_OFFLINE_FLP_PARSE` — Offline Binary FLP Parser
- **Category:** Offline FLP Engine
- **Description:** Complete recursive chunk parser reading project metadata, channels, patterns, and mixer routing.
- **Technical Rationale:** Clean-room binary parser validated against real project corpus across FL 21, 24, 25, and 26.

### `CAP_OFFLINE_FLP_MUTATE` — Offline FLP Mutation Engine
- **Category:** Offline FLP Engine
- **Description:** In-memory modification and serialization of FLP binary events with structural invariant validation.
- **Technical Rationale:** Round-trip serialization preserves project integrity with atomic staging writes.

### `CAP_STRUCTURAL_INVARIANTS` — Structural Invariant Verification
- **Category:** Offline FLP Engine
- **Description:** Pre-save validation ensuring mandatory chunks, valid track references, and correct channel ranges.
- **Technical Rationale:** Prevents generation of unreadable or corrupt project files.

### `CAP_HEADLESS_RENDER` — Headless Audio Export & Supervisor
- **Category:** Actuation & Render
- **Description:** Headless execution of `FL64.exe` to export project stems or master audio in WAV format.
- **Technical Rationale:** Verified process supervision with timeout enforcement and acoustic signal quality validation.

### `CAP_PIANO_ROLL_ACTUATION` — Piano Roll Script Actuation
- **Category:** Actuation & Render
- **Description:** Win32 UI focus-guarded invocation of custom Python Piano Roll generator and editor scripts.
- **Technical Rationale:** Focus guards and modal dialog detection prevent UI desynchronization.

### `CAP_THIRD_PARTY_PLUGINS` — Third-Party Plugin Instantiation
- **Category:** Host Architecture
- **Description:** Programmatic loading and arbitrary VST/CLAP plugin GUI parameter inspection.
- **Technical Rationale:** Gated as UNAVAILABLE because FL Studio's MIDI scripting sandbox only exposes parameters for loaded plugins, not direct headless instantiation of arbitrary third-party VSTs.

### `CAP_NATIVE_ARM64` — Native ARM64 Host Execution
- **Category:** System & Architecture
- **Description:** Execution of DAW host and background broker directly on Windows on ARM64 without binary emulation.
- **Technical Rationale:** StudioBridge and Python run 100% natively on ARM64. FL Studio's GUI binary runs under Windows 11 Prism x64 emulation, while the MIDI subsystem operates natively through WMS.

### `CAP_OFFLINE_PLAYLIST_CLIPS` — Offline Playlist Clip Creation
- **Category:** Offline FLP Engine
- **Description:** Creating audio and automation clips in the playlist offline.
- **Technical Rationale:** Fully supported in FL 21 and 25 formats; marked DEGRADED in preview FL 26 builds due to evolving chunk schema specifications.

### `CAP_ZERO_KERNEL_DRIVERS` — Zero Proprietary Kernel Drivers
- **Category:** System & Architecture
- **Description:** Complete operation using Windows MIDI Services (WMS) loopback or standard user-mode WinMM bindings.
- **Technical Rationale:** Eliminates system-level kernel driver installations, blue-screen risks, and administrative privileges.

---

## 4. Non-Affiliation Notice

StudioBridge is an independent open-source project. FL Studio is a registered trademark of Image-Line Software NV. StudioBridge is not affiliated with, endorsed by, or associated with Image-Line Software NV.
