@echo off
setlocal
title Deskimoni

cd /d "%~dp0"
set "QT_QPA_PLATFORM=windows"
set "PATH=%CD%\.venv\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

echo Deskimoni wird gestartet ...
echo.

".venv\Scripts\python.exe" "deskimoni.py"

echo.
echo Deskimoni wurde beendet.
pause
endlocal
