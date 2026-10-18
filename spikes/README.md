# StudioBridge Hardware Spikes & Live Probes

This directory contains executable hardware spike scripts, probes, and report templates for investigating physical hardware and FL Studio runtime truths on:
- **Machine A:** ARM64 Snapdragon X Plus (Lenovo Yoga Slim / Copilot+ PC), Windows 11 ARM64, running FL Studio under Prism x64 emulation.
- **Machine B:** Native x86_64 (AMD64), Windows 11 x64, running FL Studio natively.

> **Gating Rule (`13_spikes_roadmap_risks.md §1`):** A spike answers a specific unknown with empirical evidence on physical hardware. Results are recorded in `spikes/Sx/REPORT.md` using `spikes/REPORT_TEMPLATE.md`. Spikes gate architectural decisions; do not skip or simulate them.

---

## Directory Layout

```
spikes/
├── README.md              <- This operator guide
├── REPORT_TEMPLATE.md     <- Standard report template for all spikes
├── S0/                    <- S0: Environment & Hardware Capture
│   ├── capture_env.ps1    <- Automated baseline capture script
│   └── baseline_env.json  <- Captured environment facts
├── S1/                    <- S1: Embedded Python Interpreter & Sandbox Truth
│   ├── device_SBProbe.py  <- Controller script probe (Python 3.9)
│   ├── _sbp_dummy.py      <- Sibling module import test
│   └── SBProbePR.pyscript <- Piano roll script probe
├── S2/                    <- S2: SysEx Latency, Loss & OnIdle Cadence
│   └── device_SBEcho.py   <- SysEx echo and OnIdle cadence controller script
├── S3/                    <- S3: WinMM ctypes Port Plumbing & Loopback Latency
│   └── test_ports.py      <- WinMM port enumeration, multi-open, and duplex latency
└── S4/                    <- S4: FL Studio MIDI Settings Diffing & Storage
    ├── diff_settings.ps1  <- Registry export & settings file tree diff automation
    └── snapshots/         <- Snapshot storage and diff reports
```

---

## Step-by-Step Operator Procedures

### S0 — Baseline Hardware & Environment Capture

**Goal:** Establish exact hardware, OS build, Python interpreters (`win_arm64` vs Prism `x64`), `uv`, Node, `midisrv`, and FL Studio installation metadata.

1. Open PowerShell terminal in the repository root.
2. Run the environment capture script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File spikes/S0/capture_env.ps1 -SaveReport
   ```
3. Inspect output on console and verify `spikes/S0/baseline_env.json` was generated.
4. Copy the facts into `spikes/S0/REPORT.md` using `spikes/REPORT_TEMPLATE.md`.

---

### S1 — Embedded Interpreter & Sandbox Truth

**Goal:** Determine what modules, file I/O paths, API versions, and sibling imports work inside FL Studio's stripped Python 3.9 sandbox.

#### Controller Script Probe (`device_SBProbe.py`)

1. Copy the probe script and dummy sibling module to FL Studio's user hardware folder:
   ```powershell
   $hwDir = "$([Environment]::GetFolderPath('MyDocuments'))\Image-Line\FL Studio\Settings\Hardware\SBProbe"
   New-Item -ItemType Directory -Path $hwDir -Force
   Copy-Item spikes/S1/device_SBProbe.py $hwDir/
   Copy-Item spikes/S1/_sbp_dummy.py $hwDir/
   ```
2. Start FL Studio.
3. In FL Studio, open **Options -> MIDI settings** (`F10`).
4. Select any active MIDI input device (physical device or virtual loopback).
5. In the **Controller type** dropdown, select `SBProbe (user)`.
6. Enable the controller.
7. Open **View -> Script output** (`Alt+F10`).
8. Copy all console lines starting with `[SBP]` into `spikes/S1/output.txt`.
9. Press **Reload script** button in the Script Output window and verify clean reload.

#### Piano Roll Script Probe (`SBProbePR.pyscript`)

1. Copy the piano roll probe to FL Studio's piano roll scripts folder:
   ```powershell
   $prDir = "$([Environment]::GetFolderPath('MyDocuments'))\Image-Line\FL Studio\Settings\Piano roll scripts"
   New-Item -ItemType Directory -Path $prDir -Force
   Copy-Item spikes/S1/SBProbePR.pyscript $prDir/
   ```
2. Open FL Studio, open any pattern, and open the **Piano Roll** (`F7`).
3. Click the Piano Roll menu dropdown (top-left wrench / arrow) -> **Tools -> Script -> SBProbePR**.
4. Check whether script output appears in Script Output window or message box.
5. Verify whether file I/O succeeded (`sbp_pr_rel.txt` and `C:\Users\Public\sbp_pr_pub.txt`).

---

### S2 — SysEx Latency, Loss & OnIdle Cadence

**Goal:** Measure `OnIdle` call rates and real-world SysEx round-trip time, maximum chunk size, and packet loss.

1. Install `device_SBEcho.py` into FL Studio:
   ```powershell
   $echoDir = "$([Environment]::GetFolderPath('MyDocuments'))\Image-Line\FL Studio\Settings\Hardware\SBEcho"
   New-Item -ItemType Directory -Path $echoDir -Force
   Copy-Item spikes/S2/device_SBEcho.py $echoDir/
   ```
2. Open FL Studio -> Options -> MIDI settings.
3. Assign a MIDI loopback port pair to controller type `SBEcho (user)`.
4. Observe the `[SBE] idle:` prints in **View -> Script output** under four states:
   - FL Studio focused and idle.
   - FL Studio unfocused (background window).
   - FL Studio minimized to taskbar.
   - FL Studio during active playback (`Space`).
5. Record the `hz`, `min`, `med`, and `max` interval times reported in `[SBE] idle:` messages.

---

### S3 — WinMM Port Plumbing & Loopback Latency

**Goal:** Check Windows MIDI Services loopback names, 31-character truncation, multi-client port opening, and duplex latency.

1. Enumerate all system MIDI ports using WinMM ctypes:
   ```bash
   uv run python spikes/S3/test_ports.py
   ```
2. Test whether your platform allows multi-client port binding (opening the same port twice):
   ```bash
   uv run python spikes/S3/test_ports.py --multi-open --in-port 0 --out-port 0
   ```
3. Test duplex loopback latency across a configured port pair:
   ```bash
   uv run python spikes/S3/test_ports.py --latency --in-port <in_index> --out-port <out_index> --trials 100
   ```
4. Output JSON for automated recording:
   ```bash
   uv run python spikes/S3/test_ports.py --json > spikes/S3/ports_report.json
   ```

---

### S4 — FL Studio MIDI Settings Diffing & Storage

**Goal:** Discover whether FL Studio MIDI controller port assignments can be automated via registry or configuration files.

1. Ensure FL Studio is completely closed.
2. Capture the baseline snapshot:
   ```powershell
   powershell -ExecutionPolicy Bypass -File spikes/S4/diff_settings.ps1 -Action Snapshot -Name before
   ```
3. Launch FL Studio, open **Options -> MIDI settings**, configure a port assignment or controller type, and close FL Studio cleanly.
4. Capture the modified snapshot:
   ```powershell
   powershell -ExecutionPolicy Bypass -File spikes/S4/diff_settings.ps1 -Action Snapshot -Name after
   ```
5. Run the automated diff comparison:
   ```powershell
   powershell -ExecutionPolicy Bypass -File spikes/S4/diff_settings.ps1 -Action Diff -Before before -After after
   ```
6. Open the generated report in `spikes/S4/snapshots/diff_before_vs_after.md` and assess if assignments can be automated safely.

---

## Live Integration Test Suite (`tests/live/`)

In addition to standalone spike scripts, the `tests/live/` test suite runs end-to-end verification against a live FL Studio instance.

- **Standard CI / Offline Runs:**
  All tests decorated with `@pytest.mark.live` are safely deselected by default.
  ```bash
  uv run pytest -q
  ```
- **Executing Live Tests on Machine A or B:**
  Launch FL Studio with the StudioBridge controller script enabled on a loopback port, then execute:
  ```bash
  uv run pytest -m live --run-live -v
  ```
