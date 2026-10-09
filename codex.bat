@echo off
setlocal EnableExtensions
REM Any command:  codex.bat build | check | new | backup | add-mentions | import-monsters | transcribe | publish | serve
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "VPY=.venv\Scripts\python.exe"
if exist ".venv-path" set /p VENV=<".venv-path"
if defined VENV call :venv
if defined VENV set "VPY=%VENV%\Scripts\python.exe"
if not exist "%VPY%" (
  echo The site isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
"%VPY%" -m codex %*
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%

REM The packages' folder named in .venv-path (setup writes it with output: local). Written on another
REM computer, it names that computer's folder - so use the same place under this computer's AppData.
:venv
call set "VENV=%VENV%"
if exist "%VENV%\Scripts\python.exe" goto :eof
set "TAIL=%VENV:*\CampaignCodex5e\=%"
set "TAIL=%TAIL:*/CampaignCodex5e/=%"
if "%TAIL%"=="%VENV%" goto :eof
set "VENV=%LOCALAPPDATA%\CampaignCodex5e\%TAIL:/=\%"
goto :eof
