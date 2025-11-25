@echo off
setlocal
pushd %~dp0

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment not found at .venv\Scripts\python.exe
    echo Create the virtual environment before running this script.
    popd
    exit /b 1
)

call .venv\Scripts\activate.bat
python app.py

popd
endlocal
