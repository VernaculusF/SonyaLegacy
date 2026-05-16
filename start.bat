@echo off
title Sonya
cd /d "%~dp0"

:: Load .env
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

call .venv\Scripts\activate.bat

start "Sonya Core" cmd /k "cd /d "%~dp0" && .venv\Scripts\activate.bat && python -m sonya"
timeout /t 2 >nul
start "Sonya Admin" cmd /k "cd /d "%~dp0" && .venv\Scripts\activate.bat && python -m sonya.admin"

echo.
echo Sonya started.
echo Core: running in background
echo Admin: http://localhost:8877
echo.
pause
