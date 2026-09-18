$ErrorActionPreference = "Stop"
$packageRoot = $PSScriptRoot
$vstSource = Join-Path $packageRoot "payload\Triceratops.vst3"
if (-not (Test-Path $vstSource)) {
    $vstSource = "E:\text2score\vst3\build-windows\Triceratops_artefacts\Release\VST3\Triceratops.vst3"
}
$appSource = Join-Path $packageRoot "payload\Standalone"
if (-not (Test-Path $appSource)) {
    $appSource = "E:\text2score\vst3\build-windows\Triceratops_artefacts\Release\Standalone"
}
$userVstDest = Join-Path $env:LOCALAPPDATA "Programs\Common\VST3\Triceratops.vst3"
$sysVstDest = "C:\Program Files\Common Files\VST3\Triceratops.vst3"
$sysVstDir = "C:\Program Files\Common Files\VST3"
$appDestination = Join-Path $env:LOCALAPPDATA "Programs\Triceratops"

if (-not (Test-Path $vstSource)) {
    throw "The VST3 payload is missing at $vstSource"
}

# Clean user VST3 destination to avoid nested directories
if (Test-Path $userVstDest) {
    Remove-Item -Recurse -Force $userVstDest -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $userVstDest) | Out-Null
Copy-Item -Recurse -Force $vstSource (Split-Path -Parent $userVstDest)
Copy-Item -Force "$vstSource\Contents\x86_64-win\*.dll" (Split-Path -Parent $userVstDest) -ErrorAction SilentlyContinue

# Try installing to system VST3 location (Program Files)
try {
    if (Test-Path $sysVstDest) {
        Remove-Item -Recurse -Force $sysVstDest -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $sysVstDir | Out-Null
    Copy-Item -Recurse -Force $vstSource $sysVstDir
    Copy-Item -Force "$vstSource\Contents\x86_64-win\*.dll" $sysVstDir -ErrorAction SilentlyContinue
    Write-Host "System VST3 installed successfully to: $sysVstDest"
} catch {
    Write-Host "Notice: System VST3 install skipped (admin rights required), using User VST3 path."
}

# Standalone application installation
if (Test-Path $appSource) {
    New-Item -ItemType Directory -Force -Path $appDestination | Out-Null
    Copy-Item -Recurse -Force (Join-Path $appSource "*") $appDestination
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut(
        (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Triceratops.lnk")
    )
    $shortcut.TargetPath = Join-Path $appDestination "Triceratops.exe"
    $shortcut.WorkingDirectory = $appDestination
    $shortcut.Save()
}

Write-Host "User VST3 installed: $userVstDest"
Write-Host "Restart or rescan plug-ins in your DAW, then search for Triceratops."

