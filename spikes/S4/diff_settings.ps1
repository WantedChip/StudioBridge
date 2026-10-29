<#
.SYNOPSIS
    Registry and settings diff automation for StudioBridge hardware spike S4.

.DESCRIPTION
    Automates registry export (HKCU\Software\Image-Line) and FL Studio User
    Settings folder snapshot comparison to investigate where FL Studio stores
    MIDI controller assignments and port configuration.

.PARAMETER Action
    Operation to perform: 'Snapshot' or 'Diff'. Default: 'Snapshot'.

.PARAMETER Name
    Name for the snapshot (e.g. 'before_midi_config', 'after_midi_config').

.PARAMETER Before
    Name or directory of the 'before' snapshot for diffing.

.PARAMETER After
    Name or directory of the 'after' snapshot for diffing.

.PARAMETER OutputDir
    Base directory where snapshots and diff reports are stored.

.PARAMETER Json
    If set, outputs machine-readable JSON.
#>

[CmdletBinding()]
param (
    [ValidateSet("Snapshot", "Diff", "Compare")]
    [string]$Action = "Snapshot",

    [string]$Name = "",

    [string]$Before = "before",

    [string]$After = "after",

    [string]$OutputDir = "",

    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not $OutputDir) {
    $OutputDir = Join-Path $PSScriptRoot "snapshots"
}

# Ensure output directory exists
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

function Get-FLSettingsDir {
    $docs = [Environment]::GetFolderPath('MyDocuments')
    $path = Join-Path $docs "Image-Line\FL Studio\Settings"
    if (Test-Path $path) {
        return $path
    }
    return ""
}

function Take-Snapshot {
    param ([string]$SnapName)

    if (-not $SnapName) {
        $SnapName = (Get-Date).ToString("yyyyMMdd_HHmmss")
    }

    $snapDir = Join-Path $OutputDir $SnapName
    if (-not (Test-Path $snapDir)) {
        New-Item -ItemType Directory -Path $snapDir -Force | Out-Null
    }

    Write-Host "[*] Capturing snapshot: '$SnapName' -> $snapDir" -ForegroundColor Cyan

    # 1. Registry Export
    $regFile = Join-Path $snapDir "image_line.reg"
    Write-Host "  -> Exporting registry HKCU\Software\Image-Line..."
    & reg.exe export "HKCU\Software\Image-Line" $regFile /y 2>$null

    # 2. Settings folder file tree and hash manifest
    $settingsDir = Get-FLSettingsDir
    $fileManifest = @()
    if ($settingsDir -and (Test-Path $settingsDir)) {
        Write-Host "  -> Scanning settings folder: $settingsDir..."
        Get-ChildItem -Path $settingsDir -Recurse -File | ForEach-Object {
            $relPath = $_.FullName.Substring($settingsDir.Length).TrimStart('\', '/')
            $hash = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash
            $fileManifest += [PSCustomObject]@{
                RelativePath = $relPath
                Size = $_.Length
                SHA256 = $hash
                LastWriteTimeUtc = $_.LastWriteTimeUtc.ToString("o")
            }
        }
    } else {
        Write-Host "  -> Warning: FL Studio Settings folder not found at $settingsDir" -ForegroundColor Yellow
    }

    $manifestPath = Join-Path $snapDir "files_manifest.json"
    $fileManifest | ConvertTo-Json -Depth 3 | Set-Content -Path $manifestPath -Encoding utf8

    # 3. Metadata
    $meta = [PSCustomObject]@{
        SnapshotName = $SnapName
        Timestamp = (Get-Date).ToUniversalTime().ToString("o")
        SettingsDir = $settingsDir
        FileCount = $fileManifest.Count
        RegistryExported = (Test-Path $regFile)
    }
    $metaPath = Join-Path $snapDir "metadata.json"
    $meta | ConvertTo-Json | Set-Content -Path $metaPath -Encoding utf8

    Write-Host "[+] Snapshot '$SnapName' completed successfully ($($fileManifest.Count) files recorded)." -ForegroundColor Green
    return $meta
}

function Compare-Snapshots {
    param ([string]$BeforeName, [string]$AfterName)

    $dirBefore = if (Test-Path $BeforeName) { $BeforeName } else { Join-Path $OutputDir $BeforeName }
    $dirAfter = if (Test-Path $AfterName) { $AfterName } else { Join-Path $OutputDir $AfterName }

    if (-not (Test-Path $dirBefore)) {
        throw "Before snapshot directory not found: $dirBefore"
    }
    if (-not (Test-Path $dirAfter)) {
        throw "After snapshot directory not found: $dirAfter"
    }

    Write-Host "[*] Comparing '$BeforeName' vs '$AfterName'..." -ForegroundColor Cyan

    # Compare Files
    $manifestBeforePath = Join-Path $dirBefore "files_manifest.json"
    $manifestAfterPath = Join-Path $dirAfter "files_manifest.json"

    $filesBefore = @{}
    if (Test-Path $manifestBeforePath) {
        $rawBefore = Get-Content $manifestBeforePath -Raw | ConvertFrom-Json
        foreach ($f in $rawBefore) {
            $filesBefore[$f.RelativePath] = $f
        }
    }

    $filesAfter = @{}
    if (Test-Path $manifestAfterPath) {
        $rawAfter = Get-Content $manifestAfterPath -Raw | ConvertFrom-Json
        foreach ($f in $rawAfter) {
            $filesAfter[$f.RelativePath] = $f
        }
    }

    $addedFiles = @()
    $removedFiles = @()
    $modifiedFiles = @()
    $unchangedFiles = @()

    foreach ($key in $filesAfter.Keys) {
        if (-not $filesBefore.ContainsKey($key)) {
            $addedFiles += $filesAfter[$key]
        } elseif ($filesBefore[$key].SHA256 -ne $filesAfter[$key].SHA256) {
            $modifiedFiles += [PSCustomObject]@{
                RelativePath = $key
                BeforeSize = $filesBefore[$key].Size
                AfterSize = $filesAfter[$key].Size
                BeforeHash = $filesBefore[$key].SHA256
                AfterHash = $filesAfter[$key].SHA256
            }
        } else {
            $unchangedFiles += $key
        }
    }

    foreach ($key in $filesBefore.Keys) {
        if (-not $filesAfter.ContainsKey($key)) {
            $removedFiles += $filesBefore[$key]
        }
    }

    # Compare Registry lines
    $regBeforePath = Join-Path $dirBefore "image_line.reg"
    $regAfterPath = Join-Path $dirAfter "image_line.reg"

    $regChanges = @()
    if ((Test-Path $regBeforePath) -and (Test-Path $regAfterPath)) {
        $linesBefore = Get-Content $regBeforePath
        $linesAfter = Get-Content $regAfterPath
        $diff = Compare-Object $linesBefore $linesAfter
        if ($diff) {
            foreach ($d in $diff) {
                # Filter out pure noise lines
                if ($d.InputObject.Trim() -and -not ($d.InputObject.StartsWith("Windows Registry Editor"))) {
                    $side = if ($d.SideIndicator -eq "=>") { "Added/Modified in After" } else { "Removed from Before" }
                    $regChanges += [PSCustomObject]@{
                        Side = $side
                        Line = $d.InputObject.Trim()
                    }
                }
            }
        }
    }

    $diffResult = [PSCustomObject]@{
        Before = $BeforeName
        After = $AfterName
        Timestamp = (Get-Date).ToUniversalTime().ToString("o")
        AddedFiles = $addedFiles
        RemovedFiles = $removedFiles
        ModifiedFiles = $modifiedFiles
        UnchangedFileCount = $unchangedFiles.Count
        RegistryDifferenceCount = $regChanges.Count
        RegistryDifferences = $regChanges
    }

    # Save Markdown Diff Report
    $reportPath = Join-Path $OutputDir "diff_${BeforeName}_vs_${AfterName}.md"
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add("# S4 Diff Report: $BeforeName vs $AfterName")
    $lines.Add("")
    $lines.Add("- **Generated:** $($diffResult.Timestamp)")
    $lines.Add("- **Before Snapshot:** $BeforeName")
    $lines.Add("- **After Snapshot:** $AfterName")
    $lines.Add("")
    $lines.Add("## 1. Settings File Changes")
    $lines.Add("")
    $lines.Add("- Added files: $($addedFiles.Count)")
    $lines.Add("- Removed files: $($removedFiles.Count)")
    $lines.Add("- Modified files: $($modifiedFiles.Count)")
    $lines.Add("- Unchanged files: $($unchangedFiles.Count)")
    $lines.Add("")

    if ($modifiedFiles.Count -gt 0) {
        $lines.Add("### Modified Files")
        $lines.Add("| Relative Path | Before Size | After Size |")
        $lines.Add("|---|---|---|")
        foreach ($mf in $modifiedFiles) {
            $lines.Add("| ``$($mf.RelativePath)`` | $($mf.BeforeSize) B | $($mf.AfterSize) B |")
        }
        $lines.Add("")
    }

    if ($addedFiles.Count -gt 0) {
        $lines.Add("### Added Files")
        foreach ($af in $addedFiles) {
            $lines.Add("- ``$($af.RelativePath)`` ($($af.Size) B)")
        }
        $lines.Add("")
    }

    $lines.Add("## 2. Registry Differences (HKCU\Software\Image-Line)")
    $lines.Add("")
    $lines.Add("Total lines changed: $($regChanges.Count)")
    $lines.Add("")
    if ($regChanges.Count -gt 0) {
        $lines.Add('```')
        $firstN = $regChanges | Select-Object -First 50
        foreach ($rc in $firstN) {
            $lines.Add("[$($rc.Side)] $($rc.Line)")
        }
        if ($regChanges.Count -gt 50) {
            $omitted = $regChanges.Count - 50
            $lines.Add("... ($omitted more lines omitted)")
        }
        $lines.Add('```')
    } else {
        $lines.Add("No registry differences detected.")
    }

    $lines | Set-Content -Path $reportPath -Encoding utf8
    Write-Host "[+] Wrote diff report to $reportPath" -ForegroundColor Green

    return $diffResult
}

# Main Execution Flow
if ($Action -eq "Snapshot") {
    $res = Take-Snapshot -SnapName $Name
    if ($Json) {
        $res | ConvertTo-Json
    }
} else {
    $res = Compare-Snapshots -BeforeName $Before -AfterName $After
    if ($Json) {
        $res | ConvertTo-Json -Depth 4
    } else {
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host " StudioBridge S4 - Settings and Registry Diff Summary" -ForegroundColor Cyan
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host "Files Modified:     $($res.ModifiedFiles.Count)"
        Write-Host "Files Added:        $($res.AddedFiles.Count)"
        Write-Host "Files Removed:      $($res.RemovedFiles.Count)"
        Write-Host "Registry Changes:   $($res.RegistryDifferenceCount) lines"
        Write-Host "============================================================" -ForegroundColor Cyan
    }
}
