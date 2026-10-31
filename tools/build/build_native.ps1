<#
.SYNOPSIS
    Dual-Architecture (ARM64 / x64) Native Acceleration Helper Build Utility.

.DESCRIPTION
    Compiles optional native acceleration shared libraries (DLLs) for both
    ARM64 (aarch64-pc-windows-msvc) and x64 (x86_64-pc-windows-msvc) architectures.
    Supports LLVM/Clang and Microsoft Visual C++ (MSVC) build toolchains.
    If no compiler is present, logs a diagnostic warning and exits cleanly
    so environments without compilers fall back seamlessly to pure-Python routines.

.PARAMETER Architecture
    Target architectures to build: "ARM64", "x64", or both. Defaults to @("ARM64", "x64").

.PARAMETER Compiler
    Compiler toolchain to use: "auto", "clang", or "msvc". Defaults to "auto".

.PARAMETER SourcePath
    Path to native C source file. Defaults to "src/native/studiobridge_native.c".

.PARAMETER OutputDir
    Base output directory. Defaults to "build/native".

.PARAMETER Clean
    Removes existing output binaries before compilation.

.PARAMETER VerboseOutput
    Emits detailed compilation commands and flags.
#>

[CmdletBinding()]
param(
    [string[]]$Architecture = @("ARM64", "x64"),
    [ValidateSet("auto", "clang", "msvc")]
    [string]$Compiler = "auto",
    [string]$SourcePath = "src/native/studiobridge_native.c",
    [string]$OutputDir = "build/native",
    [switch]$Clean,
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Continue"

# Normalize architecture input list (supports comma-separated values like "x64,ARM64")
$targetArchs = @()
foreach ($item in $Architecture) {
    if ($item -match ",") {
        $parts = $item -split ","
        foreach ($p in $parts) {
            $trimmed = $p.Trim()
            if ($trimmed) { $targetArchs += $trimmed }
        }
    } else {
        $trimmed = $item.Trim()
        if ($trimmed) { $targetArchs += $trimmed }
    }
}
$targetArchs = @($targetArchs | Select-Object -Unique)

# Resolve source path
$resolvedSource = Resolve-Path $SourcePath -ErrorAction SilentlyContinue
if (-not $resolvedSource) {
    # Try relative to repo root
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
    $candidate = Join-Path $repoRoot $SourcePath
    if (Test-Path $candidate) {
        $resolvedSource = (Resolve-Path $candidate).Path
    }
}

if (-not $resolvedSource -or -not (Test-Path $resolvedSource)) {
    Write-Error "Source file not found: $SourcePath"
    exit 1
}

$sourceFile = $resolvedSource.ToString()

# Clean output directory if requested
if ($Clean -and (Test-Path $OutputDir)) {
    Write-Host "Cleaning output directory: $OutputDir" -ForegroundColor Yellow
    Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
}

# 1. Compiler Detection
$selectedCompiler = $null
$clangCmd = Get-Command clang -ErrorAction SilentlyContinue
$vswherePath = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vcvarsallPath = $null

if (Test-Path $vswherePath) {
    $vsInstall = & $vswherePath -latest -products * -property installationPath
    if ($vsInstall) {
        $vcvarsCandidate = Join-Path $vsInstall "VC\Auxiliary\Build\vcvarsall.bat"
        if (Test-Path $vcvarsCandidate) {
            $vcvarsallPath = $vcvarsCandidate
        }
    }
}

if ($Compiler -eq "clang") {
    if ($clangCmd) {
        $selectedCompiler = "clang"
    } else {
        Write-Error "Explicit compiler 'clang' was requested but clang was not found on PATH."
        exit 1
    }
} elseif ($Compiler -eq "msvc") {
    if ($vcvarsallPath) {
        $selectedCompiler = "msvc"
    } else {
        Write-Error "Explicit compiler 'msvc' was requested but Visual Studio vcvarsall.bat was not found."
        exit 1
    }
} else {
    # Auto-detection: prefer Clang for clean cross-targeting, fallback to MSVC
    if ($clangCmd) {
        $selectedCompiler = "clang"
    } elseif ($vcvarsallPath) {
        $selectedCompiler = "msvc"
    }
}

if (-not $selectedCompiler) {
    Write-Warning "No compatible C compiler (Clang or MSVC) detected on this system."
    Write-Warning "Skipping native compilation; pure-Python references will be used exclusively."
    exit 0
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "            StudioBridge Dual-Architecture Native Build                         " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Selected Compiler : $selectedCompiler"
Write-Host "Source File       : $sourceFile"
Write-Host "Target Archs      : $($targetArchs -join ', ')"
Write-Host "Output Directory  : $OutputDir`n"

$buildResults = [ordered]@{}
$hostArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()

foreach ($arch in $targetArchs) {
    $archNorm = $arch.ToUpperInvariant()
    $archDir = Join-Path $OutputDir $archNorm
    if (-not (Test-Path $archDir)) {
        New-Item -ItemType Directory -Path $archDir -Force | Out-Null
    }

    $outDll = Join-Path $archDir "studiobridge_native.dll"
    $expectedMachine = switch ($archNorm) {
        "ARM64" { 0xAA64 }
        "AARCH64" { 0xAA64 }
        "X64" { 0x8664 }
        "AMD64" { 0x8664 }
        "X86_64" { 0x8664 }
        Default { 0 }
    }

    Write-Host "--> Building for $archNorm..." -ForegroundColor Yellow

    $compileSuccess = $false

    if ($selectedCompiler -eq "clang") {
        $targetTriple = switch ($archNorm) {
            "ARM64" { "aarch64-pc-windows-msvc" }
            "AARCH64" { "aarch64-pc-windows-msvc" }
            "X64" { "x86_64-pc-windows-msvc" }
            "AMD64" { "x86_64-pc-windows-msvc" }
            "X86_64" { "x86_64-pc-windows-msvc" }
            Default { "aarch64-pc-windows-msvc" }
        }

        $clangArgs = @(
            "-shared",
            "-O3",
            "--target=$targetTriple",
            "-o", $outDll,
            $sourceFile
        )

        if ($VerboseOutput) {
            Write-Host "    Executing: clang $($clangArgs -join ' ')"
        }

        $out = & clang $clangArgs 2>&1
        if ($LASTEXITCODE -eq 0 -and (Test-Path $outDll)) {
            $compileSuccess = $true
        } else {
            Write-Warning "Clang compilation failed for $archNorm`: $out"
        }
    } elseif ($selectedCompiler -eq "msvc") {
        $vcvarsEnv = switch ($archNorm) {
            "ARM64" {
                if ($hostArch -eq "Arm64") { "arm64" } else { "x64_arm64" }
            }
            "AARCH64" {
                if ($hostArch -eq "Arm64") { "arm64" } else { "x64_arm64" }
            }
            "X64" {
                if ($hostArch -eq "Arm64") { "arm64_x64" } else { "x64" }
            }
            "AMD64" {
                if ($hostArch -eq "Arm64") { "arm64_x64" } else { "x64" }
            }
            "X86_64" {
                if ($hostArch -eq "Arm64") { "arm64_x64" } else { "x64" }
            }
            Default { "x64" }
        }

        $cmdStr = "call `"$vcvarsallPath`" $vcvarsEnv >nul 2>&1 && cl /nologo /O2 /LD /Fe:`"$outDll`" `"$sourceFile`""
        if ($VerboseOutput) {
            Write-Host "    Executing MSVC: $cmdStr"
        }

        $null = cmd /c $cmdStr
        if (Test-Path $outDll) {
            $compileSuccess = $true
            # Clean up intermediate .obj / .lib / .exp files
            $stem = [System.IO.Path]::GetFileNameWithoutExtension($outDll)
            foreach ($ext in @(".obj", ".lib", ".exp")) {
                $tempArtifact = Join-Path $archDir "$stem$ext"
                if (Test-Path $tempArtifact) { Remove-Item $tempArtifact -Force -ErrorAction SilentlyContinue }
            }
        } else {
            Write-Warning "MSVC compilation failed for $archNorm"
        }
    }

    if ($compileSuccess -and (Test-Path $outDll)) {
        # Verify PE Machine Header
        $peOk = $false
        $machineHex = "Unknown"
        try {
            $bytes = [System.IO.File]::ReadAllBytes($outDll)
            if ($bytes.Length -gt 0x40) {
                $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
                $machineType = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
                $machineHex = "0x{0:X4}" -f $machineType
                if ($expectedMachine -ne 0 -and $machineType -eq $expectedMachine) {
                    $peOk = $true
                } elseif ($expectedMachine -eq 0) {
                    $peOk = $true
                }
            }
        } catch {
            $peOk = $false
        }

        $dllSize = (Get-Item $outDll).Length
        if ($peOk) {
            Write-Host "    [OK] Built $archNorm binary: $outDll ($dllSize bytes, PE Machine: $machineHex)" -ForegroundColor Green
            $buildResults[$archNorm] = @{
                "Success" = $true
                "Path"    = $outDll
                "Size"    = $dllSize
                "Machine" = $machineHex
            }
        } else {
            Write-Warning "    [WARN] Built $archNorm binary but PE Machine header ($machineHex) did not match expected (0x$("{0:X4}" -f $expectedMachine))"
            $buildResults[$archNorm] = @{
                "Success" = $false
                "Path"    = $outDll
                "Error"   = "PE machine mismatch ($machineHex)"
            }
        }
    } else {
        Write-Warning "    [FAILED] Could not compile $archNorm binary."
        $buildResults[$archNorm] = @{
            "Success" = $false
            "Error"   = "Compilation failure"
        }
    }
}

Write-Host "`n--------------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Build Summary:"
$allSuccess = $true
foreach ($k in $buildResults.Keys) {
    $res = $buildResults[$k]
    if ($res.Success) {
        Write-Host "  $k : SUCCESS ($($res.Path), $($res.Machine))" -ForegroundColor Green
    } else {
        Write-Host "  $k : FAILED ($($res.Error))" -ForegroundColor Red
        $allSuccess = $false
    }
}
Write-Host "--------------------------------------------------------------------------------`n" -ForegroundColor Cyan

if (-not $allSuccess) {
    exit 1
}

exit 0
