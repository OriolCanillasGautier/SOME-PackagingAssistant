@echo off
setlocal enabledelayedexpansion

REM Change to repo root (this script is in scripts/)
cd /d "%~dp0.."

REM Simple runner: expects .venv created by install_windows.bat
set VENV_DIR=.venv
set PY="%VENV_DIR%\Scripts\python.exe"

if not exist %PY% (
  echo [PackAssist] ERROR: Virtual environment not found at %VENV_DIR%.
  echo            Please run scripts\install_windows.bat first.
  pause
  exit /b 1
)

echo [PackAssist] Starting app ...
%PY% app.py

echo [PackAssist] App exited. Press any key to close.
pause >nul
