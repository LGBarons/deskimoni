@echo off
setlocal
title Deskimoni

REM In den Ordner dieser Batch-Datei wechseln
cd /d "%~dp0"

REM Windows-Grafik-Plugin verwenden
set "QT_QPA_PLATFORM=windows"

REM Programme der virtuellen Python-Umgebung und WinGet auffindbar machen
set "PATH=%~dp0.venv\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

REM Python-Umgebung pruefen
if not exist ".venv\Scripts\python.exe" (
    echo [FEHLER] Die virtuelle Python-Umgebung wurde noch nicht eingerichtet.
    echo Bitte starte zuerst die Datei 'install_windows.bat'!
    echo.
    pause
    exit /b 1
)

REM Audio-Player Hinweis
where ffplay >nul 2>&1
if errorlevel 1 (
    echo [HINWEIS] ffplay (FFmpeg) wurde nicht im PATH gefunden.
    echo Roboter-Piepser funktionieren trotzdem!
    echo Fuer Web-Radio & mp3 installiere FFmpeg mit:
    echo   winget install --id Gyan.FFmpeg -e --source winget
    echo.
)

REM Deskimoni starten
echo Starte Deskimoni v2 ...
".venv\Scripts\python.exe" "deskimoni.py"

REM Bei einem Fehler das Fenster offen lassen
if errorlevel 1 (
    echo.
    echo Deskimoni wurde mit einem Fehler beendet.
    pause
)

endlocal
