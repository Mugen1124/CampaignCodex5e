@echo off
setlocal EnableExtensions
REM Puts both sites online (see Going online in the guide). Builds, runs the leak check, uploads.
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "VPY=.venv\Scripts\python.exe"
if exist ".venv-path" set /p VENV=<".venv-path"
if defined VENV set "VPY=%VENV%\Scripts\python.exe"
if not exist "%VPY%" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
"%VPY%" -m codex publish
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
