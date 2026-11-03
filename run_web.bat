@echo off
rem Web app launcher. Extra args pass through, e.g.  run_web.bat --mock
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Setting up virtual environment for the first time...
    python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt

where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js is needed to build the web app: https://nodejs.org
    pause
    exit /b 1
)
pushd web
if not exist "node_modules" call npm install
call npm run build
popd

python -m server %*
pause
