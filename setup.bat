@echo off
setlocal EnableExtensions
title CampaignCodex5e - setup
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"

echo.
echo  ==============================================
echo    CampaignCodex5e - one-time setup
echo  ==============================================
echo.
echo  Installs what the site needs into a private folder (.venv here, or on this computer with
echo  output: local) - nothing else on this computer is changed. Run it again any time to update.
echo.

REM ---- 1. Find Python 3.10 or newer (the Microsoft Store "python" stub doesn't count)
set "PY="
call :findpy
if defined PY goto havepy

echo  Python not found. Installing Python 3.12 with winget...
echo.
where winget >nul 2>&1
if errorlevel 1 (
  echo  winget isn't available on this computer.
  echo  Install Python 3.12 from https://www.python.org/downloads/
  echo  ^(tick "Add python.exe to PATH"^), then run setup.bat again.
  echo.
  pause
  exit /b 1
)
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1"
call :findpy
if not defined PY (
  echo.
  echo  Python installed, but this window can't see it yet.
  echo  Close this window and run setup.bat again.
  echo.
  pause
  exit /b 1
)

:havepy
echo  Using:
"%PY%" --version
echo.

REM ---- 2. The project's own Python environment, and the site's packages
REM Normally .venv here; with output: local in campaign.yml, on this computer (its place goes in .venv-path).
set "VENV="
for /f "delims=" %%V in ('""%PY%" codex\paths.py venv"') do set "VENV=%%V"
if not defined VENV set "VENV=.venv"
if /i "%VENV%"==".venv" (
  if exist ".venv-path" del ".venv-path"
) else (
  >".venv-path" echo %VENV%
)
if not exist "%VENV%\Scripts\python.exe" (
  echo  Creating %VENV% ...
  "%PY%" -m venv "%VENV%"
  if errorlevel 1 (
    echo  Couldn't create .venv - see the message above.
    pause
    exit /b 1
  )
)
echo  Installing the site's packages...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  Package install failed - see the messages above.
  pause
  exit /b 1
)
if /i "%~1"=="--with-transcribe" (
  echo.
  echo  Installing session transcription ^(a large download^)...
  "%VENV%\Scripts\python.exe" -m pip install -r requirements-transcribe.txt
)

REM ---- 3. Your campaign
echo.
echo  Setup complete.
echo.
REM Only while the demo is still here - never on a campaign of your own.
set "ANSWER="
if exist "docs\cities\greywater\" set /p "ANSWER=  Set up your own campaign now? (Y = yes, N = keep exploring the demo first) [Y/N]: "
if /i "%ANSWER%"=="Y" "%VENV%\Scripts\python.exe" -m codex new

echo.
echo  Starting the site - leave this window open while you use it. From now on, just double-click CampaignCodex5e.bat.
echo.
"%VENV%\Scripts\python.exe" -m codex serve
exit /b 0


REM ---- helper: sets PY to a Python 3.10+ that actually runs
:findpy
for %%C in (python py) do (
  %%C -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%%C"
    goto :eof
  )
)
for %%V in (313 312 311 310) do (
  if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    goto :eof
  )
)
goto :eof
