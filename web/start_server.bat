@echo off
REM PackAssist Web - Start local server
REM Requires PHP installed and in PATH

echo.
echo  ========================================
echo   PackAssist Web - Servidor Local
echo  ========================================
echo.

cd /d "%~dp0"

REM Check if PHP is available
where php >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] PHP trobat. Iniciant servidor...
    echo.
    echo     URL: http://localhost:8080
    echo.
    echo     Prem Ctrl+C per aturar
    echo.
    start "" "http://localhost:8080"
    php -S localhost:8080 server.php
) else (
    echo [!] PHP no trobat. Provant Python...
    
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Python trobat. Iniciant servidor...
        echo.
        echo     URL: http://localhost:8080
        echo.
        start "" "http://localhost:8080"
        python -m http.server 8080
    ) else (
        echo [ERROR] No s'ha trobat PHP ni Python.
        echo.
        echo Opcions:
        echo   1. Instal·la PHP: https://windows.php.net/download/
        echo   2. Instal·la Python: https://www.python.org/downloads/
        echo   3. Obre index.html directament al navegador
        echo.
        pause
    )
)
