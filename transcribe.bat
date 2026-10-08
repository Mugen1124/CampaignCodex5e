@echo off
setlocal EnableExtensions
REM Transcribes the newest recording - or drag a recording onto this file to transcribe that one.
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
"%VPY%" -m codex transcribe %*
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
