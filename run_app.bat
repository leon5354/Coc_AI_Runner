@echo off

echo Activating virtual environment...
call .venv\Scripts\activate

echo Starting Streamlit app...
python -m streamlit run interface/app.py

pause