#requires -Version 5.1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location $PSScriptRoot

Write-Host '============================================'
Write-Host '  N3M Downloader - local engine (port 8765)'
Write-Host '============================================'

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    $usable = $false
    if ($systemPython) {
        try {
            & $systemPython.Source --version *> $null
            $usable = $LASTEXITCODE -eq 0
        } catch {
            $usable = $false
        }
    }
    if (-not $usable) {
        Write-Host ''
        Write-Host '[ERROR] Python 3.12+ was not found on PATH.' -ForegroundColor Red
        Write-Host 'Install it from https://www.python.org/downloads/ and enable "Add python.exe to PATH".'
        Write-Host 'Alternatively use the Docker image in this folder.'
        exit 1
    }
    Write-Host 'Creating the Python environment...'
    python -m venv .venv
}

& $venvPython -c 'import fastapi, uvicorn, yt_dlp, gallery_dl' *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing backend dependencies...'
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'Dependency installation failed.'
        exit 1
    }
}

& $venvPython bootstrap.py
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Could not prepare backend\.env'
    exit 1
}

Write-Host ''
Write-Host 'Starting http://127.0.0.1:8765 ...'
& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765
