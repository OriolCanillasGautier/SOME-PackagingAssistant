@echo off
title PackAssist - Simplificador STL Avançat

REM Activar entorn virtual si existeix
if exist "packassist_env\Scripts\activate.bat" (
    call packassist_env\Scripts\activate.bat
)

REM Executar simplificador STL avançat
python actiu\tools\mesh_simplifiers\advanced_stl_simplifier.py
