@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   N3M Downloader - start engine + web UI
echo ============================================
echo.
echo Engine window: http://127.0.0.1:8765
echo Web window   : http://localhost:3000
echo.

start "N3M Engine" cmd /k "backend\start_server.bat"
start "N3M Web UI" cmd /k "frontend\start_dev.bat"

echo Waiting for the servers to start...
timeout /t 8 >nul
start "" "http://localhost:3000"

echo.
echo If the page opens before the server is ready, refresh it once.
echo Close both windows to stop the project.
pause
