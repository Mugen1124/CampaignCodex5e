@echo off
setlocal EnableExtensions
REM The live site at http://127.0.0.1:8000, plus the save helper. Leave the window open; close it to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex serve
set "CODE=%errorlevel%"
exit /b %CODE%
