@echo off
setlocal EnableExtensions
title CampaignCodex5e
REM CampaignCodex5e: starts your campaign site at http://127.0.0.1:8000, plus the save helper, and
REM opens it in your browser once it's ready. Leave this window open while you use the site;
REM close it to stop.
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "VPY=.venv\Scripts\python.exe"
if exist ".venv-path" set /p VENV=<".venv-path"
if defined VENV set "VPY=%VENV%\Scripts\python.exe"
if not exist "%VPY%" (
  echo CampaignCodex5e isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
"%VPY%" -m codex serve
set "CODE=%errorlevel%"
exit /b %CODE%
