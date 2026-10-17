@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Running frontend unit tests...
node "node_modules\vitest\vitest.mjs" run
pause
