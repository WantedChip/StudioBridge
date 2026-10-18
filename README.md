# StudioBridge

> A unified, open-source toolchain that enables developers and AI coding agents to inspect, control, edit, and render FL Studio projects.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(x64%20%7C%20ARM64)-blue.svg)](#)
[![Status: Planning & Scaffolding](https://img.shields.io/badge/Status-Scaffolding-orange.svg)](#)

## About StudioBridge

StudioBridge provides a coherent, capability-honest bridge across all four FL Studio control planes:
- **Live Control:** Verified real-time transport, mixer, channel, and parameter control via a lightweight, sandboxed MIDI SysEx protocol (`ctypes` WinMM and Windows MIDI Services).
- **Offline `.flp` Engine:** Clean-room, lossless-first project file inspection and mutation.
- **Piano-Roll Actuation:** Programmatic note generation and pattern manipulation.
- **Headless Render Orchestration:** Automated stem and project export validation.

Shipped as a typed Python SDK, Model Context Protocol (MCP) server, command-line interface (`sbridge`), and zero-install runner (`uvx` / `npx`), StudioBridge delivers verified writes, reversibility by default, and day-one support for both Windows ARM64 and x64 environments.

## License

This project is licensed under the terms of the MIT License. See [LICENSE](LICENSE) for details.
