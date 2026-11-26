@echo off
cd /d "%~dp0"
where uv >nul 2>&1
if %errorlevel%==0 (
    uv run --extra gui --extra ai --extra tls python run_gui.py
) else (
    python run_gui.py
)
if %errorlevel% neq 0 pause
