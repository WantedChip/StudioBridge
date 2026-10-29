<#
.SYNOPSIS
    Automated environment capture for StudioBridge hardware spike S0.

.DESCRIPTION
    Captures baseline operating system, CPU architecture, Python interpreters
    (detecting native win_arm64 vs Prism x64 emulation), uv, Node, midisrv status,
    and FL Studio installation metadata.
    Compatible with Windows PowerShell 5.1 and PowerShell 7+.

.PARAMETER Json
    If set, outputs raw JSON instead of human-readable text.

.PARAMETER SaveReport
    If set, writes the captured data to spikes/S0/baseline_env.json.
#>

[CmdletBinding()]
param (
    [switch]$Json,
    [switch]$SaveReport
)

$ErrorActionPreference = "SilentlyContinue"

# 1. Host and Timestamp
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$computerName = $env:COMPUTERNAME

# 2. Operating System
$os = Get-CimInstance Win32_OperatingSystem
$osCaption = $os.Caption
$osVersion = $os.Version
$osBuild = $os.BuildNumber
$osArch = $os.OSArchitecture

# Read UBR from registry
$ubr = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name UBR -ErrorAction SilentlyContinue).UBR
$fullBuild = if ($ubr) { "$osBuild.$ubr" } else { "$osBuild" }

# 3. CPU Architecture
$proc = Get-CimInstance Win32_Processor | Select-Object -First 1
$cpuName = $proc.Name
$cpuArchCode = $proc.Architecture
# WMI Architecture codes: 0=x86, 9=x64, 12=ARM64
$cpuArch = switch ($cpuArchCode) {
    0 { "x86" }
    9 { "x64" }
    12 { "ARM64" }
    default { "Unknown ($cpuArchCode)" }
}
$envArch = $env:PROCESSOR_ARCHITECTURE

$machineType = if ($cpuArch -eq "ARM64" -or $envArch -eq "ARM64") {
    "Machine A (ARM64 Snapdragon)"
} else {
    "Machine B (x86_64)"
}

# 4. Python Interpreters
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
$pythonVersion = ""
$pythonArch = ""
$pythonUnderPrism = $false

if ($pythonPath) {
    $pythonVersion = (& python -c "import sys; print(sys.version.replace('\n', ' '))" 2>$null)
    $pyMachine = (& python -c "import platform; print(platform.machine())" 2>$null)
    $pythonArch = $pyMachine
    if ($cpuArch -eq "ARM64" -and ($pyMachine -like "*AMD64*" -or $pyMachine -like "*x86_64*")) {
        $pythonUnderPrism = $true
    }
}

# Check for py launcher
$pyList = @()
$pyLauncher = (Get-Command py -ErrorAction SilentlyContinue).Source
if ($pyLauncher) {
    $pyList = & py -0p 2>$null
}

# 5. Developer Toolchain
$uvVersion = ""
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVersion = (& uv --version 2>$null)
}

$nodeVersion = ""
$nodeArch = ""
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = (& node -v 2>$null)
    $nodeArch = (& node -p "process.arch" 2>$null)
}

# 6. MIDI Subsystem & Windows MIDI Services
$midisrvService = Get-Service midisrv -ErrorAction SilentlyContinue
$midisrvStatus = if ($midisrvService) { $midisrvService.Status.ToString() } else { "Not Installed" }
$midisrvStartType = if ($midisrvService) { $midisrvService.StartType.ToString() } else { "N/A" }

$wmsRegKey = Test-Path "HKLM:\SOFTWARE\Microsoft\Windows MIDI Services"

# 7. FL Studio Installation Metadata
$flInstalls = @()
$progFilesIL = "C:\Program Files\Image-Line"
if (Test-Path $progFilesIL) {
    Get-ChildItem $progFilesIL -Directory | ForEach-Object {
        $flExe = Join-Path $_.FullName "FL64.exe"
        if (Test-Path $flExe) {
            $verInfo = (Get-Item $flExe).VersionInfo
            $flInstalls += [PSCustomObject]@{
                Path = $_.FullName
                Version = $verInfo.ProductVersion
                FileVersion = $verInfo.FileVersion
            }
        }
    }
}

# FL User Data Folder
$docsFolder = [Environment]::GetFolderPath('MyDocuments')
$flUserData = Join-Path $docsFolder "Image-Line\FL Studio"
$flUserDataExists = Test-Path $flUserData

# FL Registry Keys
$flRegVersions = @()
if (Test-Path "HKCU:\Software\Image-Line") {
    Get-ChildItem "HKCU:\Software\Image-Line" | Where-Object { $_.PSChildName -like "FL Studio*" } | ForEach-Object {
        $flRegVersions += $_.PSChildName
    }
}

# Running FL Studio instances
$runningFL = @()
Get-Process FL64 -ErrorAction SilentlyContinue | ForEach-Object {
    $wsMB = [math]::Round($_.WorkingSet64 / 1048576, 2)
    $runningFL += [PSCustomObject]@{
        Id = $_.Id
        ProcessName = $_.ProcessName
        Path = $_.Path
        WorkingSetMB = $wsMB
    }
}

# Build consolidated data structure
$result = [PSCustomObject]@{
    Timestamp = $timestamp
    Host = $computerName
    MachineType = $machineType
    OS = [PSCustomObject]@{
        Caption = $osCaption
        Version = $osVersion
        Build = $fullBuild
        Architecture = $osArch
    }
    CPU = [PSCustomObject]@{
        Name = $cpuName
        Architecture = $cpuArch
        EnvironmentArch = $envArch
    }
    Python = [PSCustomObject]@{
        Path = $pythonPath
        Version = $pythonVersion
        Architecture = $pythonArch
        RunningUnderPrism = $pythonUnderPrism
        PyLauncherInstalled = [bool]$pyLauncher
        PyList = $pyList
    }
    Toolchain = [PSCustomObject]@{
        Uv = $uvVersion
        Node = $nodeVersion
        NodeArch = $nodeArch
    }
    MIDI = [PSCustomObject]@{
        MidisrvStatus = $midisrvStatus
        MidisrvStartType = $midisrvStartType
        WmsRegistryPresent = $wmsRegKey
    }
    FLStudio = [PSCustomObject]@{
        InstalledVersions = $flInstalls
        UserDataFolder = $flUserData
        UserDataExists = $flUserDataExists
        RegistryVersions = $flRegVersions
        RunningProcesses = $runningFL
    }
}

if ($SaveReport) {
    $targetDir = $PSScriptRoot
    $jsonPath = Join-Path $targetDir "baseline_env.json"
    $result | ConvertTo-Json -Depth 5 | Set-Content $jsonPath -Encoding utf8
    Write-Host "[+] Saved baseline environment data to $jsonPath"
}

if ($Json) {
    $result | ConvertTo-Json -Depth 5
    return
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " StudioBridge S0 - Baseline Hardware and Environment Capture" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Timestamp:    $timestamp"
Write-Host "Machine:      $machineType ($computerName)"
Write-Host "OS:           $osCaption (Build $fullBuild, $osArch)"
Write-Host "CPU:          $cpuName [$cpuArch]"
Write-Host ""
Write-Host "--- Python Environment ---" -ForegroundColor Yellow
Write-Host "Python Path:  $pythonPath"
Write-Host "Python Ver:   $pythonVersion"
Write-Host "Python Arch:  $pythonArch (Prism Emulation: $pythonUnderPrism)"
if ($uvVersion) {
    Write-Host "uv:           $uvVersion"
}
if ($nodeVersion) {
    Write-Host "Node:         $nodeVersion ($nodeArch)"
}
Write-Host ""
Write-Host "--- MIDI Subsystem ---" -ForegroundColor Yellow
Write-Host "midisrv:      $midisrvStatus ($midisrvStartType)"
Write-Host "WMS Registry: $wmsRegKey"
Write-Host ""
Write-Host "--- FL Studio Installation ---" -ForegroundColor Yellow
Write-Host "User Data:    $flUserData (Exists: $flUserDataExists)"
if ($flInstalls.Count -gt 0) {
    foreach ($inst in $flInstalls) {
        Write-Host "Installed:    $($inst.Path) [v$($inst.Version)]"
    }
} else {
    Write-Host "Installed:    None detected in Program Files"
}
if ($flRegVersions.Count -gt 0) {
    $regStr = $flRegVersions -join ', '
    Write-Host "Registry:     $regStr"
}
if ($runningFL.Count -gt 0) {
    foreach ($fl in $runningFL) {
        Write-Host "Running FL:   PID $($fl.Id) ($($fl.WorkingSetMB) MB)"
    }
} else {
    Write-Host "Running FL:   No active FL64.exe process"
}
Write-Host "============================================================" -ForegroundColor Cyan
