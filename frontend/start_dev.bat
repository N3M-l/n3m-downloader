@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   N3M Downloader - web UI (port 3000)
echo ============================================

if not exist "node_modules\next\package.json" (
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Dependencies are missing and npm was not found.
        echo Install Node.js 20+ from https://nodejs.org/ then run this file again.
        pause
        exit /b 1
    )
    echo Installing frontend dependencies with npm...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
)

set NEXT_TELEMETRY_DISABLED=1
set NODE_ENV=development

echo Starting http://localhost:3000 ...
node "node_modules\next\dist\bin\next" dev -p 3000
pause
