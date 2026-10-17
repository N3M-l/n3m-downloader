@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ============================================
echo   N3M Downloader - local engine (port 8765)
echo ============================================

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto have_env

where python >nul 2>nul
if errorlevel 1 goto no_python
python --version >nul 2>nul
if errorlevel 1 goto no_python

echo Creating the Python environment...
python -m venv .venv
if errorlevel 1 goto no_python

:have_env
"%VENV_PY%" -c "import fastapi, uvicorn, yt_dlp, gallery_dl" >nul 2>nul
if errorlevel 1 (
    echo Installing backend dependencies...
    "%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

"%VENV_PY%" bootstrap.py
if errorlevel 1 (
    echo [ERROR] Could not prepare backend\.env
    pause
    exit /b 1
)

echo.
echo Starting http://127.0.0.1:8765 ...
"%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
pause
exit /b 0

:no_python
echo.
echo [ERROR] Python 3.12+ was not found on PATH.
echo.
echo Install it from https://www.python.org/downloads/ and enable "Add python.exe to PATH",
echo then run this file again. Alternatively use the Docker image in this folder.
echo.
pause
exit /b 1
