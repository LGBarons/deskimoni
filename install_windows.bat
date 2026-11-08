@echo off
setlocal enabledelayedexpansion
title Deskimoni - Windows Installation

echo ========================================================
echo         Deskimoni v2 - Windows Ein-Klick-Installation
echo ========================================================
echo.

cd /d "%~dp0"

REM 1. Python pruefen
where python >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht im PATH gefunden!
    echo Bitte installiere Python 3.10+ von https://www.python.org/downloads/
    echo und setze das Haekchen bei "Add Python to PATH"!
    echo.
    echo Alternativ im Terminal: winget install Python.Python.3.12
    pause
    exit /b 1
)
echo [OK] Python gefunden.

REM 2. Git pruefen (optional, fuer git pull)
where git >nul 2>&1
if errorlevel 1 (
    echo [HINWEIS] Git ist noch nicht installiert.
    echo Tipp: Installiere Git mit: winget install --id Git.Git -e --source winget
) else (
    echo [OK] Git gefunden.
)

REM 3. Virtuelle Umgebung (.venv) anlegen
if not exist ".venv\Scripts\python.exe" (
    echo [*] Erstelle virtuelle Umgebung (.venv) ...
    python -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] Konnte virtuelle Umgebung nicht erstellen.
        pause
        exit /b 1
    )
    echo [OK] Virtuelle Umgebung erstellt.
) else (
    echo [OK] Virtuelle Umgebung existiert bereits.
)

REM 4. Pip aktualisieren & Abhaengigkeiten installieren
echo [*] Installiere benoetigte Python-Pakete aus requirements.txt ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

REM 5. PyAudio fuer Windows-Mikrofon pruefen/installieren
echo [*] Pruefe PyAudio fuer Mikrofon-Sprachsteuerung ...
".venv\Scripts\python.exe" -m pip install pyaudio >nul 2>&1
if errorlevel 1 (
    echo [HINWEIS] PyAudio konnte nicht automatisch kompiliert werden.
    echo Sprachausgabe (TTS), KI, Mausverfolgung und Musik funktionieren trotzdem vollstaendig!
) else (
    echo [OK] PyAudio fuer Mikrofon-Spracheingabe erfolgreich installiert!
)

REM 6. FFmpeg pruefen
where ffplay >nul 2>&1
if errorlevel 1 (
    echo.
    echo [TIPP] FFmpeg wird fuer MP3/Web-Radio und Audio-Wiedergabe empfohlen.
    echo Du kannst es ganz einfach installieren mit:
    echo winget install --id Gyan.FFmpeg -e --source winget
    echo.
) else (
    echo [OK] FFmpeg / ffplay gefunden.
)

REM 7. Desktop-Verknuepfung erstellen
echo [*] Erstelle Desktop-Verknuepfung ...
set "DESKIMONI_START=%~dp0start_windows.bat"
powershell.exe -NoProfile -Command ^
    "$ErrorActionPreference = 'SilentlyContinue';" ^
    "$desktop = [Environment]::GetFolderPath('Desktop');" ^
    "$shell = New-Object -ComObject WScript.Shell;" ^
    "$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Deskimoni.lnk'));" ^
    "$shortcut.TargetPath = '%DESKIMONI_START%';" ^
    "$shortcut.WorkingDirectory = '%~dp0';" ^
    "$shortcut.Description = 'Deskimoni Desktop Companion';" ^
    "$shortcut.IconLocation = ($env:SystemRoot + '\System32\shell32.dll,0');" ^
    "$shortcut.Save();"

echo.
echo ========================================================
echo   Installation erfolgreich abgeschlossen!
echo   Du kannst Deskimoni jetzt ueber die neue
echo   Desktop-Verknuepfung oder start_windows.bat starten!
echo ========================================================
echo.
pause
endlocal
