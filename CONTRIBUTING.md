# Contributing to StudioBridge

Thank you for your interest in contributing to StudioBridge! We welcome issues, bug reports, feature requests, and pull requests.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

---

## 1. Development Setup

StudioBridge uses [uv](https://docs.astral.sh/uv/) for ultra-fast, deterministic Python dependency management.

### Prerequisites

- **Python:** 3.10, 3.11, or 3.12 (64-bit)
- **Git:** Standard git client
- **uv:** Install via `pip install uv` or `winget install astral-sh.uv`

### Clone & Install

```bash
# Clone the repository
git clone https://github.com/WantedChip/studiobridge.git
cd studiobridge

# Create virtual environment and sync all dependencies
uv sync --all-extras
```

---

## 2. Running Quality Checks & Tests

Before submitting a pull request, all automated checks must pass cleanly:

```bash
# 1. Run the test suite
uv run pytest

# 2. Run Python linting and formatting checks
uv run ruff check .
uv run ruff format --check .

# 3. Run static type checking
uv run pyright

# 4. Verify architectural layering contracts
uv run lint-imports

# 5. Verify brand token and protocol integrity
python tools/rename.py --check

# 6. Run the security audit gate
uv run python tools/security_audit.py --check
```

---

## 3. Core Architectural Rules

All contributions must adhere to our core project rules:

1. **Zero Native Compiled Dependencies on Windows:**
   - The runtime package must remain universal pure-Python (`py3-none-any`).
   - The Windows MIDI backend uses standard library `ctypes` bindings to `winmm.dll` and Windows MIDI Services.
2. **Device Script Sandbox Restrictions:**
   - Any code intended for FL Studio's controller script context (`device/assets/*`) must be Python 3.9-compatible and import only standard library builtins and sibling files. No sockets, no ctypes, no external packages.
3. **Clean-Room Provenance:**
   - Never copy, decompile, or port code from GPL-licensed projects. All format facts, binary layouts, and protocol specifications come from our clean-room documentation and hardware corpus experiments.
4. **Third-Party Driver Safety:**
   - Never bundle, distribute, or require proprietary kernel-mode virtual MIDI drivers. Windows routing uses Windows MIDI Services (WMS) loopback as primary.
5. **Verified, Reversible Writes:**
   - Writes to FL Studio state must be verified with read-back comparison and recorded in the mutation journal.
6. **Token-Based Branding:**
   - Centralize brand strings using the token table (`studiobridge`, `sbridge`, `SBridge`).

---

## 4. Commit Message Conventions

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat`: A new user-facing feature or capability
- `fix`: A bug fix
- `docs`: Documentation updates or additions
- `test`: Adding or correcting tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `chore`: Maintenance tasks, dependencies, tooling updates

*Example:*
```bash
git commit -m "feat(mixer): add stereo width control to mixer strip API"
```

---

## 5. Submitting a Pull Request

1. Fork the repository and create your feature branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Make your changes and add tests covering the new functionality.
3. Run all checks to ensure 100% pass rate.
4. Push your branch to GitHub and open a Pull Request using the [PR Template](.github/pull_request_template.md).
