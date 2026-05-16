@echo off
title Sonya
cd /d "%~dp0"

:: Load .env file
if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        set "%%a=%%b"
    )
)

:: Start core hidden
start /b "" .venv\Scripts\pythonw.exe -m sonya > nul 2>&1

:: Wait for core to init
timeout /t 3 /nobreak > nul

:: Start admin hidden
start /b "" .venv\Scripts\pythonw.exe -m sonya.admin > nul 2>&1

echo Sonya running. Admin: http://localhost:8877
echo Press any key to stop.
pause > nul

:: Kill on exit
taskkill /f /im pythonw.exe > nul 2>&1
