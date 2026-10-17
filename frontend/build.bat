@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set NEXT_TELEMETRY_DISABLED=1
echo Type-checking...
node "node_modules\typescript\bin\tsc" --noEmit
if errorlevel 1 (
    echo [ERROR] Type-check failed.
    pause
    exit /b 1
)
echo Building the static export...
node "node_modules\next\dist\bin\next" build
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)
echo.
echo Done. Static files are in: frontend\out
pause
