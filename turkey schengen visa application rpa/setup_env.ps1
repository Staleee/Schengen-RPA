# Turkey Schengen PDF RPA - virtual environment
# Run from this folder: .\setup_env.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Turkey Schengen PDF RPA - setup ===" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Run: .\.venv\Scripts\python api_server.py  (default port 8092)" -ForegroundColor Green

