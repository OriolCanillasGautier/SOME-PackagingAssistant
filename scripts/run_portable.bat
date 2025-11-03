@echo off
setlocal enabledelayedexpansion

REM Change to bundle root (this script is in scripts/)
cd /d "%~dp0.."

set EMBED_PY=python\python.exe
if not exist "%EMBED_PY%" (
  echo [PackAssist] ERROR: Embedded Python not found at %EMBED_PY%.
  echo            This script is intended for the portable bundle.
  pause
  exit /b 1
)

echo [PackAssist] Using embedded Python at %EMBED_PY%
"%EMBED_PY%" app.py

echo [PackAssist] App exited. Press any key to close.
pause >nul
