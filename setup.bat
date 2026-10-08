@echo off
setlocal EnableExtensions
title campaign-codex - setup
cd /d "%~dp0"

echo.
echo  ==============================================
echo    campaign-codex - one-time setup
echo  ==============================================
echo.
echo  Installs what the site needs into a private folder (.venv) here - nothing else on this
echo  computer is changed. Run it again any time to update.
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
if not exist ".venv\Scripts\python.exe" (
  echo  Creating .venv ...
  "%PY%" -m venv .venv
  if errorlevel 1 (
    echo  Couldn't create .venv - see the message above.
    pause
    exit /b 1
  )
)
echo  Installing the site's packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  Package install failed - see the messages above.
  pause
  exit /b 1
)
if /i "%~1"=="--with-transcribe" (
  echo.
  echo  Installing session transcription ^(a large download^)...
  ".venv\Scripts\python.exe" -m pip install -r requirements-transcribe.txt
)

REM ---- 3. Your campaign
echo.
echo  Setup complete.
echo.
set "ANSWER="
set /p "ANSWER=  Set up your own campaign now? (Y = yes, N = keep exploring the demo first) [Y/N]: "
if /i "%ANSWER%"=="Y" ".venv\Scripts\python.exe" -m codex new

echo.
echo  Starting the site - leave this window open while you use it. From now on, just run serve.bat.
echo.
".venv\Scripts\python.exe" -m codex serve
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
