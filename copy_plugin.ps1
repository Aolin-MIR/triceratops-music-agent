# Single Canonical VST3 Installation Script for Triceratops
$ErrorActionPreference = "Stop"
$Source = "E:\text2score\vst3\build-windows-msvcrt\Triceratops_artefacts\Release\VST3\Triceratops.vst3"
$CanonicalDest = "C:\Program Files\Common Files\VST3"
$UserLocalDest = "$env:LOCALAPPDATA\Programs\Common\VST3\Triceratops.vst3"
$BinaryRelative = "Contents\x86_64-win\Triceratops.vst3"

Write-Host "=========================================="
Write-Host "Deploying Triceratops VST3 Plugin"
Write-Host "=========================================="

# Verify the build before touching the installed copy.
if (-not (Test-Path -LiteralPath (Join-Path $Source $BinaryRelative))) {
    throw "Newly built VST3 binary not found: $Source"
}

# 1. Never kill the DAW: an unsaved project may be open.
$ReaperProc = Get-Process reaper -ErrorAction SilentlyContinue
if ($ReaperProc) {
    throw "REAPER is running. Save and close it, then run this installer again."
}

# 2. Clean up the known duplicate path only after the preflight passes.
if (Test-Path $UserLocalDest) {
    Write-Host "Removing duplicate VST3 path at $UserLocalDest..."
    Remove-Item -LiteralPath $UserLocalDest -Recurse -Force
}

# 3. Copy newly compiled VST3 to canonical path
if (Test-Path $Source) {
    try {
        Copy-Item -LiteralPath $Source -Recurse -Force -Destination $CanonicalDest
    } catch {
        Write-Host "Standard copy failed due to permissions. Requesting Administrator elevation..."
        $ElevatedScript = Join-Path $env:TEMP "install-triceratops-vst3.ps1"
        @"
`$ErrorActionPreference = 'Stop'
Copy-Item -LiteralPath '$Source' -Recurse -Force -Destination '$CanonicalDest'
"@ | Set-Content -LiteralPath $ElevatedScript -Encoding UTF8
        $Process = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $ElevatedScript
        )
        if ($Process.ExitCode -ne 0) { throw "Elevated installation failed." }
    }
} else {
    Write-Error "Source VST3 file not found: $Source"
}

$InstalledBinary = Join-Path (Join-Path $CanonicalDest "Triceratops.vst3") $BinaryRelative
if (-not (Test-Path -LiteralPath $InstalledBinary)) { throw "Installed VST3 binary is missing." }
if ((Get-FileHash -LiteralPath $InstalledBinary).Hash -ne
    (Get-FileHash -LiteralPath (Join-Path $Source $BinaryRelative)).Hash) {
    throw "Installed VST3 hash does not match the build."
}
Write-Host "[SUCCESS] Installed and verified $InstalledBinary"
