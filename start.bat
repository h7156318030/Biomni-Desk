@echo off
rem Start Biomni-Desk on Windows: the backend on port 8765 and the web page on port 3001.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Biomni-Desk is not installed yet. Run install.bat first.
    pause
    exit /b 1
)
set PYTHONIOENCODING=utf-8
rem Local addresses must never go through a system proxy
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1

echo Starting the backend (the agent needs about a minute to load)...
start "Biomni-Desk backend" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m biomni_ui.server"

echo Starting the web page...
start "Biomni-Desk web" /D "%~dp0web" cmd /k "npm run start -- -p 3001"

timeout /t 6 /nobreak >nul
start "" http://localhost:3001
echo.
echo Open http://localhost:3001 and wait until the bottom-left corner says Ready.
echo To stop: close the two Biomni-Desk windows.
