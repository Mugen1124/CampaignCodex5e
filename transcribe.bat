@echo off
setlocal EnableExtensions
REM Transcribes the newest recording - or drag a recording onto this file to transcribe that one.
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex transcribe %*
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
