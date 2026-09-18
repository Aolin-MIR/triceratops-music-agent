@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Triceratops.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed.
  pause
  exit /b 1
)
echo.
echo Triceratops was installed successfully.
pause
