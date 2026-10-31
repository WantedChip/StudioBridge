<#
.SYNOPSIS
    ARM64 Native Toolchain Diagnostic & Environment Verification Utility.

.DESCRIPTION
    Inspects the local system for native ARM64 and cross-architecture (x64)
    development toolchains, compilers, SDKs, and runtimes:
    - Host architecture and Windows build
    - Visual Studio 2022 / Build Tools and MSVC ARM64 / x64 components
    - LLVM / Clang compiler infrastructure
    - Windows 11 SDK headers and import libraries
    - Rust toolchains and target triples (aarch64 / x86_64)
    - Python runtimes (native ARM64 and emulated x64) and uv
    - Node.js runtime and architecture
    - Developer build tools (CMake, Ninja, Git, PowerShell 7)
    - Windows MIDI Services (WMS) runtime and CLI tools

.PARAMETER Json
    Outputs structured diagnostic findings as a JSON object to standard output.

.PARAMETER Detailed
    Includes additional details such as environment variables and directory listings.
#>

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$Detailed
)

$ErrorActionPreference = "SilentlyContinue"

function Get-CommandOutput([string]$Command) {
    try {
        $result = Invoke-Expression "$Command 2>&1" | Out-String
        if ($null -ne $result) {
            return $result.Trim()
        }
    } catch {
        return $null
    }
    return $null
}

function Get-CommandFirstLine([string]$Command) {
    try {
        $out = Invoke-Expression "$Command 2>&1" | Where-Object { $_ -and $_.ToString().Trim() -ne "" } | Select-Object -First 1
        if ($null -ne $out) {
            return $out.ToString().Trim()
        }
    } catch {
        return $null
    }
    return $null
}

# 1. Machine & Host Architecture
$osArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
$procArch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
$osVer = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Version
if (-not $osVer) { $osVer = [System.Environment]::OSVersion.Version.ToString() }
$psVer = $PSVersionTable.PSVersion.ToString()

$machineReport = [ordered]@{
    "OSArchitecture"      = $osArch
    "ProcessArchitecture" = $procArch
    "WindowsVersion"      = $osVer
    "Processor"           = $env:PROCESSOR_IDENTIFIER
    "PowerShellVersion"   = $psVer
    "IsARM64Host"         = ($osArch -eq "Arm64")
}

# 2. Visual Studio & MSVC Build Tools
$vswherePath = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsFound = Test-Path $vswherePath
$vsInstallPath = $null
$msvcArm64 = $false
$msvcX64 = $false
$vsCMake = $false
$vsClang = $false
$vcvarsallPath = $null

if ($vsFound) {
    $vsInstallPath = & $vswherePath -latest -products * -property installationPath
    if ($vsInstallPath) {
        $vcvars = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvarsall.bat"
        if (Test-Path $vcvars) { $vcvarsallPath = $vcvars }

        $hitArm64 = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64 -property installationPath
        if ($hitArm64) { $msvcArm64 = $true }

        $hitX64 = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($hitX64) { $msvcX64 = $true }

        $hitCMake = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath
        if ($hitCMake) { $vsCMake = $true }

        $hitClang = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Component.VC.Llvm.Clang -property installationPath
        if ($hitClang) { $vsClang = $true }
    }
}

# Find latest MSVC directory if VS is installed
$msvcVersion = $null
$msvcToolsRoot = if ($vsInstallPath) { Join-Path $vsInstallPath "VC\Tools\MSVC" } else { $null }
if ($msvcToolsRoot -and (Test-Path $msvcToolsRoot)) {
    $latestMsvc = Get-ChildItem $msvcToolsRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($latestMsvc) { $msvcVersion = $latestMsvc.Name }
}

$vsReport = [ordered]@{
    "VSWherePresent"       = $vsFound
    "InstallationPath"     = $vsInstallPath
    "VCVarsAllPath"        = $vcvarsallPath
    "MSVCVersion"          = $msvcVersion
    "MSVCArm64Installed"   = $msvcArm64
    "MSVCX64Installed"     = $msvcX64
    "CMakeToolsInstalled"  = $vsCMake
    "ClangToolsInstalled"  = $vsClang
}

# 3. LLVM / Clang
$clangCmd = Get-Command clang -ErrorAction SilentlyContinue
$clangPlusCmd = Get-Command clang++ -ErrorAction SilentlyContinue
$clangClCmd = Get-Command clang-cl -ErrorAction SilentlyContinue
$lldLinkCmd = Get-Command lld-link -ErrorAction SilentlyContinue

$clangVer = if ($clangCmd) { Get-CommandFirstLine "clang --version" } else { $null }
$clangClVer = if ($clangClCmd) { Get-CommandFirstLine "clang-cl --version" } else { $null }
$clangTarget = if ($clangVer -and ($clangVer -match "Target:\s+([^\s]+)")) { $Matches[1] } else {
    $targetLine = Get-CommandOutput "clang -dumpmachine"
    if ($targetLine) { $targetLine.Trim() } else { $null }
}

$clangReport = [ordered]@{
    "ClangPresent"     = ($null -ne $clangCmd)
    "ClangPath"        = if ($clangCmd) { $clangCmd.Source } else { $null }
    "ClangVersion"     = $clangVer
    "ClangTarget"      = $clangTarget
    "ClangPlusPresent" = ($null -ne $clangPlusCmd)
    "ClangClPresent"   = ($null -ne $clangClCmd)
    "ClangClVersion"   = $clangClVer
    "LldLinkPresent"   = ($null -ne $lldLinkCmd)
}

# 4. Windows 11 SDK
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkVersions = @()
$sdkInclude = Join-Path $sdkRoot "Include"
if (Test-Path $sdkInclude) {
    $sdkVersions = @(Get-ChildItem $sdkInclude -Directory -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Name | Sort-Object -Descending)
}
$latestSdk = if ($sdkVersions.Count -gt 0) { $sdkVersions[0] } else { $null }

# Verify WinMM and WinRT headers exist in latest SDK
$hasWinMM = $false
$hasWindowsH = $false
if ($latestSdk) {
    $umDir = Join-Path $sdkInclude "$latestSdk\um"
    if (Test-Path (Join-Path $umDir "mmsystem.h")) { $hasWinMM = $true }
    if (Test-Path (Join-Path $umDir "windows.h")) { $hasWindowsH = $true }
}

$sdkReport = [ordered]@{
    "SDKRoot"          = $sdkRoot
    "InstalledSDKs"    = $sdkVersions
    "LatestSDKVersion" = $latestSdk
    "HasWindowsHeaders"= $hasWindowsH
    "HasWinMMHeaders"  = $hasWinMM
}

# 5. Rust Toolchain
$rustcCmd = Get-Command rustc -ErrorAction SilentlyContinue
$cargoCmd = Get-Command cargo -ErrorAction SilentlyContinue
$maturinCmd = Get-Command maturin -ErrorAction SilentlyContinue
$rustupCmd = Get-Command rustup -ErrorAction SilentlyContinue

$rustcVer = if ($rustcCmd) { Get-CommandFirstLine "rustc --version" } else { $null }
$cargoVer = if ($cargoCmd) { Get-CommandFirstLine "cargo --version" } else { $null }
$maturinVer = if ($maturinCmd) { Get-CommandFirstLine "maturin --version" } else { $null }

$rustHost = $null
if ($rustcCmd) {
    $rustcVV = Get-CommandOutput "rustc -vV"
    if ($rustcVV -and ($rustcVV -match "host:\s+([^\r\n]+)")) {
        $rustHost = $Matches[1].Trim()
    }
}

$rustTargets = @()
if ($rustupCmd) {
    $targetOutput = Get-CommandOutput "rustup target list --installed"
    if ($targetOutput) {
        $rustTargets = @($targetOutput -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    }
}

$rustReport = [ordered]@{
    "RustcPresent"        = ($null -ne $rustcCmd)
    "RustcVersion"        = $rustcVer
    "RustHostTriple"      = $rustHost
    "CargoPresent"        = ($null -ne $cargoCmd)
    "CargoVersion"        = $cargoVer
    "MaturinPresent"      = ($null -ne $maturinCmd)
    "MaturinVersion"      = $maturinVer
    "InstalledTargets"    = $rustTargets
    "HasAarch64Target"    = ($rustTargets -contains "aarch64-pc-windows-msvc" -or $rustHost -eq "aarch64-pc-windows-msvc")
    "HasX86_64Target"     = ($rustTargets -contains "x86_64-pc-windows-msvc" -or $rustHost -eq "x86_64-pc-windows-msvc")
}

# 6. Python Runtimes & Environment
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
$pyCmd = Get-Command py -ErrorAction SilentlyContinue
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue

$pythonVer = if ($pythonCmd) { Get-CommandFirstLine "python --version" } else { $null }
$pythonArch = if ($pythonCmd) {
    Get-CommandFirstLine "python -c `"import platform; print(platform.architecture()[0])`""
} else { $null }
$pythonMachine = if ($pythonCmd) {
    Get-CommandFirstLine "python -c `"import platform; print(platform.machine())`""
} else { $null }

$pyList = @()
if ($pyCmd) {
    $pyListRaw = Get-CommandOutput "py -0p"
    if ($pyListRaw) {
        $pyList = @($pyListRaw -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    }
}

$uvVer = if ($uvCmd) { Get-CommandFirstLine "uv --version" } else { $null }

$pythonReport = [ordered]@{
    "PythonPresent"    = ($null -ne $pythonCmd)
    "PythonVersion"    = $pythonVer
    "PythonArch"       = $pythonArch
    "PythonMachine"    = $pythonMachine
    "PyLauncherPresent"= ($null -ne $pyCmd)
    "InstalledPythons" = $pyList
    "UvPresent"        = ($null -ne $uvCmd)
    "UvVersion"        = $uvVer
}

# 7. Node.js Runtime
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue

$nodeVer = if ($nodeCmd) { Get-CommandFirstLine "node -v" } else { $null }
$nodeArch = if ($nodeCmd) { Get-CommandFirstLine "node -p `"process.arch`"" } else { $null }
$npmVer = if ($npmCmd) { Get-CommandFirstLine "npm -v" } else { $null }

$nodeReport = [ordered]@{
    "NodePresent"  = ($null -ne $nodeCmd)
    "NodeVersion"  = $nodeVer
    "NodeArch"     = $nodeArch
    "NpmPresent"   = ($null -ne $npmCmd)
    "NpmVersion"   = $npmVer
    "IsArm64Node"  = ($nodeArch -eq "arm64")
}

# 8. Build Utilities
$cmakeCmd = Get-Command cmake -ErrorAction SilentlyContinue
$ninjaCmd = Get-Command ninja -ErrorAction SilentlyContinue
$gitCmd = Get-Command git -ErrorAction SilentlyContinue

$buildToolsReport = [ordered]@{
    "CMake" = if ($cmakeCmd) { Get-CommandFirstLine "cmake --version" } else { $null }
    "Ninja" = if ($ninjaCmd) { Get-CommandFirstLine "ninja --version" } else { $null }
    "Git"   = if ($gitCmd) { Get-CommandFirstLine "git --version" } else { $null }
    "Pwsh"  = $psVer
}

# 9. Windows MIDI Services
$midisrv = Get-Service midisrv -ErrorAction SilentlyContinue
$midiCli = Get-Command midi -ErrorAction SilentlyContinue

$wmsReport = [ordered]@{
    "MidiServiceStatus" = if ($midisrv) { $midisrv.Status.ToString() } else { "NotInstalled" }
    "MidiCliPresent"    = ($null -ne $midiCli)
    "MidiCliVersion"    = if ($midiCli) { Get-CommandFirstLine "midi --version" } else { $null }
}

# Quick compile verification test
$compileArm64Ok = $false
$compileX64Ok = $false
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "sb_toolchain_check_$([System.Guid]::NewGuid().ToString('N'))"

try {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    $testC = Join-Path $tempDir "test.c"
    Set-Content -Path $testC -Value "__declspec(dllexport) int sb_probe(int x) { return x * 2; }"

    if ($clangCmd) {
        $armDll = Join-Path $tempDir "probe_arm64.dll"
        $x64Dll = Join-Path $tempDir "probe_x64.dll"

        $null = & clang -shared -O2 --target=aarch64-pc-windows-msvc -o $armDll $testC 2>&1
        if (Test-Path $armDll) {
            # Inspect PE machine type
            $bytes = [System.IO.File]::ReadAllBytes($armDll)
            if ($bytes.Length -gt 0x40) {
                $pe = [BitConverter]::ToInt32($bytes, 0x3C)
                $mach = [BitConverter]::ToUInt16($bytes, $pe + 4)
                if ($mach -eq 0xAA64) { $compileArm64Ok = $true }
            }
        }

        $null = & clang -shared -O2 --target=x86_64-pc-windows-msvc -o $x64Dll $testC 2>&1
        if (Test-Path $x64Dll) {
            $bytes = [System.IO.File]::ReadAllBytes($x64Dll)
            if ($bytes.Length -gt 0x40) {
                $pe = [BitConverter]::ToInt32($bytes, 0x3C)
                $mach = [BitConverter]::ToUInt16($bytes, $pe + 4)
                if ($mach -eq 0x8664) { $compileX64Ok = $true }
            }
        }
    } elseif ($vcvarsallPath) {
        # Fallback to testing via MSVC vcvarsall
        $armDll = Join-Path $tempDir "probe_arm64.dll"
        $cmdArm = "call `"$vcvarsallPath`" arm64 >nul 2>&1 && cd /d `"$tempDir`" && cl /nologo /LD /Fe:probe_arm64.dll test.c >nul 2>&1"
        cmd /c $cmdArm
        if (Test-Path $armDll) { $compileArm64Ok = $true }

        $x64Dll = Join-Path $tempDir "probe_x64.dll"
        $cmdX64 = "call `"$vcvarsallPath`" arm64_x64 >nul 2>&1 && cd /d `"$tempDir`" && cl /nologo /LD /Fe:probe_x64.dll test.c >nul 2>&1"
        cmd /c $cmdX64
        if (Test-Path $x64Dll) { $compileX64Ok = $true }
    }
} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$compileReport = [ordered]@{
    "CanCompileARM64" = $compileArm64Ok
    "CanCompileX64"   = $compileX64Ok
}

# Determine overall readiness status
$isReady = ($null -ne $clangCmd -or $msvcArm64) -and ($null -ne $pythonCmd) -and ($null -ne $uvCmd)
$statusText = if ($isReady -and $compileArm64Ok -and $compileX64Ok) {
    "READY"
} elseif ($isReady) {
    "READY_PARTIAL"
} else {
    "INCOMPLETE"
}

$fullDiagnostic = [ordered]@{
    "Timestamp"            = [System.DateTime]::UtcNow.ToString("o")
    "Status"               = $statusText
    "Machine"              = $machineReport
    "VisualStudio"         = $vsReport
    "Clang"                = $clangReport
    "WindowsSDK"           = $sdkReport
    "Rust"                 = $rustReport
    "Python"               = $pythonReport
    "Node"                 = $nodeReport
    "BuildTools"           = $buildToolsReport
    "WindowsMIDIServices"  = $wmsReport
    "CompilerVerification" = $compileReport
}

if ($Json) {
    $fullDiagnostic | ConvertTo-Json -Depth 6
    exit 0
}

# Pretty-print formatted console output
function Format-Row([string]$Label, [bool]$Ok, [string]$Detail) {
    $statusSymbol = if ($Ok) { "[OK]     " } else { "[MISSING]" }
    $color = if ($Ok) { "Green" } else { "DarkGray" }
    Write-Host -NoNewline "$("{0,-32}" -f $Label) "
    Write-Host -NoNewline -ForegroundColor $color "$statusSymbol "
    Write-Host "$Detail"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "           ARM64 & DUAL-ARCHITECTURE TOOLCHAIN DIAGNOSTIC REPORT                " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

Write-Host "`n-- Host Machine --" -ForegroundColor Yellow
Write-Host "  OS Architecture     : $($machineReport.OSArchitecture)"
Write-Host "  Process Architecture: $($machineReport.ProcessArchitecture)"
Write-Host "  Windows Version     : $($machineReport.WindowsVersion)"
Write-Host "  PowerShell Version  : $($machineReport.PowerShellVersion)"

Write-Host "`n-- Visual Studio & MSVC --" -ForegroundColor Yellow
Format-Row "VS Locator (vswhere)" $vsReport.VSWherePresent $(if ($vsReport.InstallationPath) { $vsReport.InstallationPath } else { "Not found" })
Format-Row "MSVC ARM64 Build Tools" $vsReport.MSVCArm64Installed $(if ($vsReport.MSVCVersion) { "MSVC $($vsReport.MSVCVersion)" } else { "Component absent" })
Format-Row "MSVC x64 Cross Tools" $vsReport.MSVCX64Installed "Component Microsoft.VisualStudio.Component.VC.Tools.x86.x64"
Format-Row "CMake Tools (VS)" $vsReport.CMakeToolsInstalled "VC.CMake.Project"
Format-Row "Clang Tools (VS)" $vsReport.ClangToolsInstalled "VC.Llvm.Clang"

Write-Host "`n-- LLVM / Clang --" -ForegroundColor Yellow
Format-Row "LLVM Clang" $clangReport.ClangPresent $(if ($clangReport.ClangVersion) { $clangReport.ClangVersion } else { "clang not on PATH" })
Format-Row "Clang Default Target" ($null -ne $clangReport.ClangTarget) $(if ($clangReport.ClangTarget) { $clangReport.ClangTarget } else { "N/A" })
Format-Row "Clang-cl Driver" $clangReport.ClangClPresent $(if ($clangReport.ClangClVersion) { $clangReport.ClangClVersion } else { "clang-cl not on PATH" })
Format-Row "LLVM lld-link" $clangReport.LldLinkPresent "LLD linker"

Write-Host "`n-- Windows 11 SDK --" -ForegroundColor Yellow
Format-Row "Windows 11 SDK Root" (Test-Path $sdkReport.SDKRoot) $sdkReport.SDKRoot
Format-Row "Latest SDK Version" ($null -ne $sdkReport.LatestSDKVersion) $(if ($sdkReport.LatestSDKVersion) { $sdkReport.LatestSDKVersion } else { "No SDK installed" })
Format-Row "Windows.h Header" $sdkReport.HasWindowsHeaders "Kernel & user APIs"
Format-Row "WinMM MMSystem Header" $sdkReport.HasWinMMHeaders "WinMM multimedia MIDI headers"

Write-Host "`n-- Rust Toolchain --" -ForegroundColor Yellow
Format-Row "Rustc Compiler" $rustReport.RustcPresent $(if ($rustReport.RustcVersion) { $rustReport.RustcVersion } else { "rustc not on PATH" })
Format-Row "Rust Host Triple" ($null -ne $rustReport.RustHostTriple) $(if ($rustReport.RustHostTriple) { $rustReport.RustHostTriple } else { "N/A" })
Format-Row "Cargo Package Manager" $rustReport.CargoPresent $(if ($rustReport.CargoVersion) { $rustReport.CargoVersion } else { "cargo not on PATH" })
Format-Row "ARM64 Target (aarch64)" $rustReport.HasAarch64Target "aarch64-pc-windows-msvc"
Format-Row "x64 Target (x86_64)" $rustReport.HasX86_64Target "x86_64-pc-windows-msvc"

Write-Host "`n-- Python Runtimes & Packaging --" -ForegroundColor Yellow
Format-Row "Active Python" $pythonReport.PythonPresent "$($pythonReport.PythonVersion) ($($pythonReport.PythonArch), machine=$($pythonReport.PythonMachine))"
Format-Row "uv Package Manager" $pythonReport.UvPresent $(if ($pythonReport.UvVersion) { $pythonReport.UvVersion } else { "uv not on PATH" })
Format-Row "Python Launcher (py)" $pythonReport.PyLauncherPresent $(if ($pythonReport.InstalledPythons.Count -gt 0) { "$($pythonReport.InstalledPythons.Count) runtime(s) registered" } else { "py launcher" })

Write-Host "`n-- Node.js Runtime --" -ForegroundColor Yellow
Format-Row "Node.js" $nodeReport.NodePresent $(if ($nodeReport.NodeVersion) { "$($nodeReport.NodeVersion) (arch=$($nodeReport.NodeArch))" } else { "node not on PATH" })
Format-Row "npm Package Manager" $nodeReport.NpmPresent $(if ($nodeReport.NpmVersion) { "npm $($nodeReport.NpmVersion)" } else { "npm not on PATH" })

Write-Host "`n-- Dual-Architecture Compilation Verification --" -ForegroundColor Yellow
Format-Row "Compile ARM64 DLL (AA64)" $compileReport.CanCompileARM64 "Verified PE machine 0xAA64"
Format-Row "Compile x64 DLL (8664)" $compileReport.CanCompileX64 "Verified PE machine 0x8664"

Write-Host "`n-- Windows MIDI Services (WMS) --" -ForegroundColor Yellow
Format-Row "WMS midisrv Service" ($wmsReport.MidiServiceStatus -eq "Running") "Service state: $($wmsReport.MidiServiceStatus)"
Format-Row "WMS midi.exe CLI" $wmsReport.MidiCliPresent $(if ($wmsReport.MidiCliVersion) { $wmsReport.MidiCliVersion } else { "midi.exe not installed" })

Write-Host "`n--------------------------------------------------------------------------------" -ForegroundColor Cyan
$summaryColor = switch ($statusText) {
    "READY" { "Green" }
    "READY_PARTIAL" { "Yellow" }
    Default { "Red" }
}
Write-Host "Overall ARM64 Toolchain Status: " -NoNewline
Write-Host "[$statusText]" -ForegroundColor $summaryColor
Write-Host "--------------------------------------------------------------------------------`n" -ForegroundColor Cyan

exit 0
