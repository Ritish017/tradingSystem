@echo off
set PYTHONPATH=C:\Trading\trading-platform\backend
cd /d C:\Trading\trading-platform
C:\Trading\trading-platform\.venv312\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
