# France Schengen RPA - Create and setup virtual environment
# Run from: "france schengen visa application rpa" folder
# Usage: .\setup_env.ps1

$ErrorActionPreference = "Stop"
$projectDir = $PSScriptRoot
Set-Location $projectDir

Write-Host ""
Write-Host "=== France Schengen RPA - Environment Setup ===" -ForegroundColor Cyan
Write-Host ""

# Create .venv if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "  Done." -ForegroundColor Green
} else {
    Write-Host "Virtual environment (.venv) already exists." -ForegroundColor Green
}

# Activate and install
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& .\.venv\Scripts\pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "  Done." -ForegroundColor Green

Write-Host ""
Write-Host "Installing Playwright Chromium..." -ForegroundColor Yellow
& .\.venv\Scripts\playwright install chromium
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "  Done." -ForegroundColor Green

Write-Host ""
Write-Host "=== France environment ready ===" -ForegroundColor Green
Write-Host ""
Write-Host "To activate and run:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python api_server.py" -ForegroundColor White
Write-Host ""
Write-Host "Or run in one go:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python api_server.py" -ForegroundColor White
Write-Host ""
