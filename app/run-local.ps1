# PowerShell script to run the FastAPI application from app/ directory

$ErrorActionPreference = "Stop"

# Set PYTHONPATH to parent directory so 'app' module can be found
$env:PYTHONPATH = ".."

Write-Host "Starting server on http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

