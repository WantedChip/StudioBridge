---
title: "FL Studio API Reference Overview"
description: "Authoritative reference for StudioBridge FL Studio API v44, detailing 119 RPC functions across 8 modules."
---

The **StudioBridge API Reference** documents the normalized Python API surface exposed by FL Studio's controller script runtime (API v44 / FL Studio 24.1+).

Coding agents access these functions via the Live MIDI RPC Plane using standard tool calls and MCP resource URIs (`studio://api/{module}/{function}`).

## Module Index

| Module | Title | Functions | Mutating | Execution Plane | Reference Link |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `channels` | Channel Rack & Generators | 21 | 10 | `midi` | [channels API](/docs/api/channels/) |
| `device` | Hardware Controller & Device Surface | 9 | 6 | `midi` | [device API](/docs/api/device/) |
| `general` | General FL Studio DAW Engine | 10 | 7 | `midi` | [general API](/docs/api/general/) |
| `mixer` | Mixer Tracks, Routing & Volume | 23 | 11 | `midi` | [mixer API](/docs/api/mixer/) |
| `patterns` | Patterns, Clips & Sequencer | 12 | 6 | `midi` | [patterns API](/docs/api/patterns/) |
| `plugins` | Plugin Parameters & VST/AU | 12 | 2 | `midi` | [plugins API](/docs/api/plugins/) |
| `transport` | Transport, Playback & Recording | 17 | 11 | `midi` | [transport API](/docs/api/transport/) |
| `ui` | User Interface Windows & Focus | 15 | 9 | `midi` | [ui API](/docs/api/ui/) |

**Total Surface:** 119 functions (62 mutating, 57 read-only) across 8 modules.

---

## Architectural Principles

### 1. Unified Resource URIs
Every function in the FL Studio Python API maps to a canonical resource URI:
```
studio://api/{module}/{function}
```
Examples:
- `studio://api/transport/isPlaying`
- `studio://api/mixer/getTrackVolume`
- `studio://api/channels/setChannelVolume`

### 2. Execution Planes & Sandboxing
- **Live MIDI RPC Plane (`midi`):** All functions listed in this reference execute inside the FL Studio controller script sandbox on the host audio thread.
- **Python 3.9 Runtime:** Functions execute inside the embedded Python environment with builtin types (`int`, `float`, `str`, `bool`, `None`). No sockets or external C-extensions are loaded.

### 3. Read-Only Default & Safety Guarantees
- By default, sessions operate in **read-only mode**. Mutating calls require explicit safety elevation or safe session unlocking.
- Mutating operations implement automatic **read-back verification** and record entries in the mutation journal with rollback capability (`G0-G2` guarantee levels).

### 4. Parameter Validation & Range Bounds
- Integer and float parameters are strictly validated against hardware ranges before dispatch across the MIDI wire.
- Out-of-bounds parameters are rejected client-side with descriptive error messages, preventing DAW instability.
