@echo off
cd /d "%~dp0"
python -m uvicorn --app-dir "%~dp0." src.main:app --host 0.0.0.0 --port 8000
