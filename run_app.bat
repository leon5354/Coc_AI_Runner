@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Setting up virtual environment for the first time...
    python -m venv .venv
    call .venv\Scripts\activate
    echo Installing dependencies...
    pip install -q -r requirements.txt
) else (
    call .venv\Scripts\activate
)

echo Starting AI TTRPG Runner...
python -m streamlit run interface/app.py

pause
