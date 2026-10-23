@echo off
cd /d "%~dp0..\sin_content_api"
"C:\tools\python-embed\python.exe" -m uvicorn src.main:app --host 0.0.0.0 --port 8000
