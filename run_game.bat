@echo off
cd /d "%~dp0"
echo Installing Flask (first time only)...
python -m pip install flask
echo.
echo Starting Treasure Hunt... open http://127.0.0.1:5000 in your browser
start "" http://127.0.0.1:5000
python app.py
pause
