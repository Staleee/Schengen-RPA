@echo off
REM Germany Schengen RPA - Create and setup virtual environment
cd /d "%~dp0"

echo.
echo === Germany Schengen RPA - Environment Setup ===
echo.

if not exist ".venv" (
    echo Creating virtual environment (.venv)...
    python -m venv .venv
    echo   Done.
) else (
    echo Virtual environment (.venv) already exists.
)

echo.
echo Installing Python dependencies...
.\.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Installing Playwright Chromium...
.\.venv\Scripts\playwright install chromium
if errorlevel 1 exit /b 1

echo.
echo === Germany environment ready ===
echo.
echo To run:  .venv\Scripts\python -m src.api
echo.
pause
