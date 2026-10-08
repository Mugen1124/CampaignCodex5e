@echo off
setlocal EnableExtensions
REM Puts both sites online (see Going online in the guide). Builds, runs the leak check, uploads.
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex publish
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
