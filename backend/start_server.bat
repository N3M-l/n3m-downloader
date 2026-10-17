@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   N3M Downloader - local engine (port 8765)
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.12+ is required and was not found on PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create .venv
    pause
    exit /b 1
  )
)

".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo Bootstrapping pip for the environment...
  python -m pip --disable-pip-version-check --python ".venv\Scripts\python.exe" install --upgrade pip
)

echo Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Dependency installation failed.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" bootstrap.py

echo.
echo Starting http://127.0.0.1:8765 ...
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
pause
