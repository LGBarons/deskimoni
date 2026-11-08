@echo off
setlocal
title Deskimoni - Desktop-Verknuepfung erstellen

REM Pfad der vorhandenen Startdatei
set "DESKIMONI_DIR=%~dp0"
set "DESKIMONI_START=%~dp0start_windows.bat"

if not exist "%DESKIMONI_START%" (
    echo FEHLER: start_windows.bat wurde nicht gefunden.
    echo.
    echo Speichere diese Datei im selben Ordner
    echo wie deine start_windows.bat.
    pause
    exit /b 1
)

REM Desktop-Pfad ermitteln und Windows-Verknuepfung erstellen
powershell.exe -NoProfile -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "$desktop = [Environment]::GetFolderPath('Desktop');" ^
    "$shell = New-Object -ComObject WScript.Shell;" ^
    "$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Deskimoni.lnk'));" ^
    "$shortcut.TargetPath = $env:DESKIMONI_START;" ^
    "$shortcut.WorkingDirectory = $env:DESKIMONI_DIR;" ^
    "$shortcut.Description = 'Deskimoni aktualisieren und starten';" ^
    "$shortcut.IconLocation = ($env:SystemRoot + '\System32\shell32.dll,0');" ^
    "$shortcut.Save();"

if errorlevel 1 (
    echo.
    echo FEHLER: Die Desktop-Verknuepfung konnte nicht erstellt werden.
    pause
    exit /b 1
)

echo.
echo Die Desktop-Verknuepfung "Deskimoni" wurde erstellt.
echo Du kannst Deskimoni jetzt per Doppelklick darauf starten.
echo.
pause
endlocal