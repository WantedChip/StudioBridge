# StudioBridge Agent Rules

When developing or interacting with StudioBridge and FL Studio projects, all coding agents MUST adhere to these 10 hard rules:

1. **Zero native/compiled dependencies on Windows**: Runtime dependencies must provide universal pure-Python wheels or both `win_amd64` and `win_arm64` binary wheels. The Windows MIDI backend is our own `ctypes` WinMM binding.
2. **Device-script sandbox rules**: Any code executing inside FL Studio's controller script context (`device/assets/*`) MUST be Python 3.9-compatible and import ONLY standard builtin modules and sibling script files. No sockets, no ctypes, no external packages.
3. **Clean-room provenance**: Never copy, decompile, or port code from GPL projects. Format facts and protocol specifications come from our clean-room documentation and hardware corpus experiments.
4. **Third-party driver safety**: Never bundle, distribute, or require proprietary kernel-mode virtual MIDI drivers (`loopMIDI`, `virtualMIDI`). Primary Windows routing uses Windows MIDI Services (WMS) loopback.
5. **Verified, reversible writes**: Writes to FL state must be verified with read-back comparison, recorded in the mutation journal, and default to read-only session mode. Always create a checkpoint before mutations. Never save or overwrite user project files implicitly.
6. **Token-based branding**: Centralize brand strings using the token table (`studiobridge`, `sbridge`, `SBridge`).
7. **Tests first**: Reference requirement IDs in test comments (`# req: WIRE-06`). Cover edge cases, timeouts, and error paths.
8. **Capability honesty**: If real FL Studio behavior is unknown or unverified, gate behind a capability flag; do not guess or hallucinate API behavior.
9. **Strict typing and validation**: Keep public APIs fully typed. Enforce linting with `ruff`, type-checking with `pyright`, and module layering with `import-linter`.
10. **Concise reporting**: Output short summaries of operations including verification receipts, journal IDs, safety modes, and remedies for any failure.
