@echo off
title DST Proximity Voice Launcher
cd /d "%~dp0"
python launcher.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Fehler beim Starten des Launchers.
    pause
)
