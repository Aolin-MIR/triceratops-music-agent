# Triceratops VST3 Plugin Updater
$Source = "E:\text2score\vst3\build-windows-msvcrt\Triceratops_artefacts\Release\VST3\Triceratops.vst3"
$DestProgramFiles = "C:\Program Files\Common Files\VST3"
$DestUserLocal = "$env:LOCALAPPDATA\Programs\Common\VST3"

Write-Host "=========================================="
Write-Host "Triceratops VST3 Installer / Updater"
Write-Host "=========================================="

$ReaperProcesses = Get-Process reaper -ErrorAction SilentlyContinue

if ($ReaperProcesses) {
    Write-Warning "REAPER process is currently RUNNING (PID: $($ReaperProcesses.Id))."
    Write-Warning "Windows locks loaded VST3 files while REAPER is running."
    Write-Host "Closing REAPER to unlock VST3 files..."
    Stop-Process -Name reaper -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (Test-Path $Source) {
    # 1. Update User Local AppData VST3
    New-Item -ItemType Directory -Force -Path $DestUserLocal | Out-Null
    Copy-Item -Recurse -Force $Source $DestUserLocal
    Write-Host "[SUCCESS] Updated $DestUserLocal\Triceratops.vst3"

    # 2. Update System Program Files VST3
    try {
        New-Item -ItemType Directory -Force -Path $DestProgramFiles | Out-Null
        Copy-Item -Recurse -Force $Source $DestProgramFiles -ErrorAction Stop
        Write-Host "[SUCCESS] Updated $DestProgramFiles\Triceratops.vst3"
    } catch {
        Write-Warning "Could not copy to Program Files (requires Admin rights). User local VST3 path updated successfully."
    }

    Write-Host "=========================================="
    Write-Host "VST3 Update Completed Successfully!"
    Write-Host "You can now open REAPER and insert Triceratops."
    Write-Host "=========================================="
} else {
    Write-Error "Source VST3 file not found: $Source"
}
