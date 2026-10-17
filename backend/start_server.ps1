#requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host '============================================'
Write-Host '  N3M Downloader - local engine (port 8765)'
Write-Host '============================================'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error 'Python 3.12+ is required on PATH.'
    exit 1
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating the Python environment...'
    python -m venv .venv
}

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

& $venvPython -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Bootstrapping pip for the environment...'
    python -m pip --disable-pip-version-check --python $venvPython install --upgrade pip
}

Write-Host 'Installing backend dependencies...'
& $venvPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Dependency installation failed.'
    exit 1
}

& $venvPython bootstrap.py

Write-Host ''
Write-Host 'Starting http://127.0.0.1:8765 ...'
& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8765
