@echo off
title PackAssist - Empaquetament Intel·ligent

echo.
echo ==========================================
echo    PackAssist - Empaquetament Intel·ligent
echo ==========================================
echo.

REM Activar entorn virtual si existeix
if exist "packassist_env\Scripts\activate.bat" (
    echo Activant entorn virtual...
    call packassist_env\Scripts\activate.bat
) else (
    echo Utilitzant Python del sistema...
)

REM Executar launcher
python launch.py

pause
