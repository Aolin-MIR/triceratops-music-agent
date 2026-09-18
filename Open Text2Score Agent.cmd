@echo off
setlocal
set "REAPER=C:\Program Files\REAPER (x64)\reaper.exe"
set "PANEL=C:\Users\jinli\AppData\Roaming\REAPER\Scripts\Text2Score\Text2Score - Music Agent Panel.lua"

if not exist "%REAPER%" (
  echo REAPER was not found at: %REAPER%
  pause
  exit /b 1
)
if not exist "%PANEL%" (
  echo Text2Score Agent Panel was not found at: %PANEL%
  pause
  exit /b 1
)

start "Text2Score Music Agent" "%REAPER%" -nonewinst "%PANEL%"
