# StudioBridge Documentation

Welcome to the **StudioBridge** technical documentation. StudioBridge is an open-source, local-first bridge and Model Context Protocol (MCP) server connecting modern AI coding agents (Claude Desktop, Cursor, Windsurf, Copilot, Cline, Codex, Antigravity) and Python automation scripts directly to FL Studio on Windows (x64 and ARM64).

StudioBridge operates with **zero kernel-mode drivers**, **zero compiled native dependencies** in Python, and **zero telemetry**.

---

## Documentation Directory

| Document | Description |
| :--- | :--- |
| **[Quickstart Guide](quickstart.md)** | Step-by-step setup in under 5 minutes for AI coding agents and Python scripts |
| **[Architecture & Protocol](architecture.md)** | Deep dive into the 4 control planes, SysEx wire protocol, and security model |
| **[Troubleshooting & Doctor Checks](troubleshooting.md)** | Comprehensive index of all 26 `sbridge doctor` diagnostic codes and fixes |
| **[Compatibility Matrix](compatibility.md)** | Hardware and DAW capability matrix across FL 21–26 on ARM64 and x64 |
| **[Python SDK Reference](api.md)** | Programmatic automation reference for mixer, transport, channels, and render |
| **[FLP Format Provenance](flp/PROVENANCE.md)** | Clean-room documentation and research notes on the binary FLP project format |

---

## The Four Control Planes

StudioBridge provides four complementary control planes depending on the automation task:

```
+--------------------------------------------------------------------------------+
|                                  AI AGENTS                                     |
|           Claude Desktop | Cursor | Windsurf | Copilot | Cline | Codex         |
+--------------------------------------------------------------------------------+
                                        |  MCP (JSON-RPC 2.0 / Streamable HTTP)
                                        v
+--------------------------------------------------------------------------------+
|                              STUDIOBRIDGE CORE                                 |
|               Broker Daemon (127.0.0.1) | Token Auth | Verification            |
+--------------------------------------------------------------------------------+
         |                        |                     |                 |
         | Plane 1                | Plane 2             | Plane 3         | Plane 4
         v                        v                     v                 v
+------------------+    +------------------+    +---------------+   +------------+
|  Live MIDI SysEx |    | Win32 UI         |    | Headless      |   | Offline    |
|  2-Way RPC Bus   |    | Actuator Guard   |    | Render Sup.   |   | FLP Engine |
+------------------+    +------------------+    +---------------+   +------------+
         |                        |                     |                 |
         v                        v                     v                 v
+--------------------------------------------------------------------------------+
|                                   FL STUDIO                                    |
|              DAW Engine | Mixer | Channels | Piano Roll | Exporter             |
+--------------------------------------------------------------------------------+
```

1. **Plane 1: Live MIDI SysEx RPC Bus**
   - Sub-millisecond bidirectional communication with FL Studio's Python controller script engine.
   - Real-time transport control, mixer faders, stereo panning, mute/solo, and parameter telemetry.
   - 100% verified writes with read-back tolerance matching and mutation journal records.

2. **Plane 2: Win32 UI Actuator & Window Guard**
   - Focus-aware desktop actuation for operations requiring graphical focus (e.g., Piano Roll script dispatch).
   - Modal dialog detection, target window verification, and automatic cursor restoration.

3. **Plane 3: Headless Render Supervisor**
   - Background audio exporting (`FL64.exe /R /Fwav ...`) with process isolation.
   - Preflight environment verification, process supervision, timeout guards, and audio acoustic signal validation (WAV format, RMS, peak level).

4. **Plane 4: Offline FLP Binary Engine**
   - Pure-Python parser and mutation engine for binary `.flp` project files.
   - Inspect, modify, and generate FL Studio projects offline with lossless round-trip guarantees and structural invariant verification.

---

## Essential CLI Commands

```bash
# 1. Environment and connection diagnosis
sbridge doctor

# 2. Automated setup and script installation
sbridge setup install
sbridge setup loopback

# 3. Quick handshake probe
sbridge hello

# 4. Model Context Protocol (MCP) server for agents
sbridge mcp

# 5. Local HTTP REST and Streamable HTTP server
sbridge serve --port 8080

# 6. Direct command dispatch
sbridge call transport.isPlaying
sbridge call mixer.getTrackVolume --args '{"track": 0}'

# 7. Offline FLP project inspection
sbridge flp inspect path/to/project.flp
```

---

## Safety & Verification Model

StudioBridge is designed from the ground up for safe use with autonomous AI agents:

- **Read-Only by Default:** Sessions default to read-only mode. Any mutating action requires explicit challenge confirmation tokens or explicit mode elevation.
- **Verified Writes:** Writes to FL Studio state are verified with read-back comparison against target values within configurable tolerances.
- **Mutation Journal:** Every mutation is assigned a monotonic ID (`MID`) and logged with read-back receipts, enabling automated rollback checkpoints.
- **Containment Allowlists:** Strict path traversal defenses prevent access outside authorized project workspace directories.
- **Loopback Isolation:** The local broker and REST servers strictly bind to `127.0.0.1` with constant-time Bearer token verification matching `%LOCALAPPDATA%\studiobridge\broker.token`.

---

## License & Non-Affiliation

StudioBridge is licensed under the [MIT License](../LICENSE).

*Disclaimer:* StudioBridge is an independent open-source project and is not affiliated with, endorsed by, or associated with Image-Line Software NV. FL Studio is a registered trademark of Image-Line Software NV.
