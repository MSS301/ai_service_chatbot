# PowerShell script to run the FastAPI application on Windows

$ErrorActionPreference = "Stop"

# Get the directory where this script is located and change to parent (project root)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

# Set PYTHONPATH
$env:PYTHONPATH = Get-Location
Write-Host "PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Cyan

# Activate virtual environment if exists (check both locations)
if (Test-Path "app\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment from app\.venv..." -ForegroundColor Green
    & app\.venv\Scripts\Activate.ps1
} elseif (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment from .venv..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
}

# Run the server
Write-Host "Starting server on http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

