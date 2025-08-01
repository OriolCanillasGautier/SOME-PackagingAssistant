@echo off
title PackAssist GUI - Interfície Completa

REM Activar entorn virtual si existeix
if exist "packassist_env\Scripts\activate.bat" (
    call packassist_env\Scripts\activate.bat
)

REM Executar la nova GUI
python packassist_gui.py
