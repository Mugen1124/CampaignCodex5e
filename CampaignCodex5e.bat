@echo off
setlocal EnableExtensions
title CampaignCodex5e
REM CampaignCodex5e: starts your campaign site at http://127.0.0.1:8000, plus the save helper, and
REM opens it in your browser once it's ready. Leave this window open while you use the site;
REM close it to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo CampaignCodex5e isn't set up yet - double-click setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m codex serve
set "CODE=%errorlevel%"
exit /b %CODE%
