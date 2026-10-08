@echo off
setlocal EnableExtensions
REM Imports the SRD's monsters - or drag a monster sheet (.json, see templates) onto this file.
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex import-monsters %*
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
