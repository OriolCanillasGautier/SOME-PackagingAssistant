@echo off
title PackAssist - Aplicació Principal

REM Activar entorn virtual si existeix
if exist "packassist_env\Scripts\activate.bat" (
    call packassist_env\Scripts\activate.bat
)

REM Executar aplicació principal directament
python packassist_simple.py
