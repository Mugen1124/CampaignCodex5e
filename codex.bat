@echo off
setlocal EnableExtensions
REM Any command:  codex.bat build | check | new | backup | add-mentions | import-monsters | transcribe | publish | serve
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex %*
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
