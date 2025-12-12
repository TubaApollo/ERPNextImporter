@echo off
echo.
echo ===================================================================
echo   ERPNext Produkt-Importer v2
echo ===================================================================
echo.

REM Prüfe Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden!
    echo Bitte Python 3.9+ installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Erstelle venv falls nicht vorhanden
if not exist "venv" (
    echo [INFO] Erstelle virtuelle Umgebung...
    python -m venv venv
    if errorlevel 1 (
        echo [FEHLER] Konnte venv nicht erstellen!
        pause
        exit /b 1
    )
)

REM Aktiviere venv
call venv\Scripts\activate.bat

REM Installiere Dependencies
pip show flet >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installiere Abhängigkeiten...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [FEHLER] Installation fehlgeschlagen!
        pause
        exit /b 1
    )
)

REM Erstelle Ordner
if not exist "templates" mkdir templates
if not exist "logs" mkdir logs

REM Starte App
echo.
echo [INFO] Starte ERPNext Importer...
echo.
python main.py

pause
