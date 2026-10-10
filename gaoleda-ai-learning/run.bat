@echo off
rem ============================================================
rem  Study AI with William Gao - one-click launcher (Windows)
rem  Creates a local venv, installs deps, starts the app.
rem ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
python --version >nul 2>nul
if errorlevel 1 (
    echo   Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    echo   Remember to tick "Add Python to PATH".
    pause
    exit /b 1
)
python --version

if not exist ".venv" (
    echo [2/4] Creating virtual environment .venv ...
    python -m venv .venv
) else (
    echo [2/4] Virtual environment already exists.
)

echo [3/4] Installing dependencies...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   Dependency install failed. Check your network or proxy.
    pause
    exit /b 1
)

echo [4/4] Starting app at http://localhost:8501 ...
echo   Press Ctrl+C to stop.
call ".venv\Scripts\python.exe" app.py
pause
