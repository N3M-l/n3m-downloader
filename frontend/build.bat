@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set NEXT_TELEMETRY_DISABLED=1
rem Build the production bundle for https://n3m.fun/downloader/.
rem Explicit values win over .env.local, which is for local development.
if "%NEXT_PUBLIC_ENGINE_URL%"=="" set "NEXT_PUBLIC_ENGINE_URL=https://n3m-downloader-engine.onrender.com"
if "%NEXT_PUBLIC_BASE_PATH%"=="" set "NEXT_PUBLIC_BASE_PATH=/downloader"
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
echo Done. Deploy with: npx wrangler deploy
pause
