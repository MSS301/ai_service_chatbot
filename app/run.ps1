# PowerShell script to run the FastAPI application on Windows

$ErrorActionPreference = "Stop"

# Set PYTHONPATH
$env:PYTHONPATH = Get-Location

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
}

# Run the server
Write-Host "Starting server on http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

