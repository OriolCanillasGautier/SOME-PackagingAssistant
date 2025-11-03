@echo off
setlocal enabledelayedexpansion

REM Change to repo root (this script is in scripts/)
cd /d "%~dp0.."

echo [PackAssist] Checking for Python 3.13...
where py >nul 2>&1
if errorlevel 1 (
  echo [PackAssist] ERROR: Python launcher 'py' not found. Install Python 3.13 from https://www.python.org/downloads/windows/ and ensure 'py' is in PATH.
  pause
  exit /b 1
)

for /f "tokens=2 delims= " %%v in ('py -3.13 -V 2^>^&1') do set PYVER=%%v
if not defined PYVER (
  echo [PackAssist] Python 3.13 not explicitly found. Trying default 'py -V'...
  for /f "tokens=2 delims= " %%v in ('py -V 2^>^&1') do set PYVER=%%v
)

set OKVER=
for /f "tokens=1,2,3 delims=." %%a in ("%PYVER%") do (
  set MAJ=%%a
  set MIN=%%b
  set MIC=%%c
)

if "%MAJ%"=="3" if "%MIN%"=="13" set OKVER=1
if not defined OKVER (
  echo [PackAssist] ERROR: Found Python %PYVER%, but 3.13.x is required.
  echo            Install Python 3.13 and retry.
  pause
  exit /b 1
)

echo [PackAssist] Creating virtual environment (.venv) with Python 3.13...
py -3.13 -m venv .venv
if errorlevel 1 (
  echo [PackAssist] ERROR: Failed to create virtual environment.
  pause
  exit /b 1
)

set PY=".venv\Scripts\python.exe"
if not exist %PY% (
  echo [PackAssist] ERROR: Python executable not found in .venv.
  pause
  exit /b 1
)

echo [PackAssist] Upgrading pip, setuptools, wheel...
%PY% -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo [PackAssist] ERROR: Failed to upgrade pip/setuptools/wheel.
  pause
  exit /b 1
)

echo [PackAssist] Installing dependencies from requirements.txt ...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [PackAssist] ERROR: Failed to install dependencies.
  pause
  exit /b 1
)

echo [PackAssist] Verifying core imports...
%PY% -c "import gradio, numpy, pandas; import pyvista; print('OK')" 1>nul 2>nul
if errorlevel 1 (
  echo [PackAssist] WARNING: PyVista or dependencies may not be fully operational.
  echo            The app will still run, but the 3D viewer may not open.
)

echo [PackAssist] Installation completed successfully.
echo [PackAssist] You can now run: scripts\run_windows.bat
pause >nul
