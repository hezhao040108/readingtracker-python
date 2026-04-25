@echo off
cd /d %~dp0
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe reading_app_v3.py
) else (
    python reading_app_v3.py
)
pause
