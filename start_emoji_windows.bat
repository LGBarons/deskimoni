@echo off
setlocal
title Emoji-Kryptograf & Dolmetscher

REM In den Ordner dieser Batch-Datei wechseln
cd /d "%~dp0"

REM Windows-Grafik-Plugin verwenden
set "QT_QPA_PLATFORM=windows"

REM Programme der virtuellen Python-Umgebung auffindbar machen
set "PATH=%~dp0.venv\Scripts;%PATH%"

REM Python-Umgebung pruefen
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] Die virtuelle Python-Umgebung wurde noch nicht eingerichtet.
    echo Bitte starte zuerst die Datei 'install_windows.bat'!
    echo.
    pause
    exit /b 1
)

REM Emoji-Kryptograf starten
echo Starte Emoji-Kryptograf & Dolmetscher ...
".venv\Scripts\python.exe" "emojikryptograf.py"

if errorlevel 1 (
    echo.
    echo Emoji-Kryptograf wurde mit einem Fehler beendet.
    pause
)

endlocal
