@echo off
title Sonya
cd /d "%~dp0"

call .venv\Scripts\activate.bat

start "Sonya Core" cmd /k "python -m sonya"
timeout /t 2 >nul
start "Sonya Admin" cmd /k "python -m sonya.admin"

echo.
echo Sonya started.
echo Core: running in background
echo Admin: http://localhost:8877
echo.
pause
