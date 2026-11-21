# Run all backend quality gates. Stops at the first failure.
# Usage (from backend/, venv active):  .\scripts\check.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Invoke-Gate([string]$Name, [scriptblock]$Command) {
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Gate "ruff check ."          { ruff check . }
Invoke-Gate "ruff format --check ." { ruff format --check . }
Invoke-Gate "mypy app"              { mypy app }
Invoke-Gate "pytest"                { pytest }

Write-Host "All checks passed." -ForegroundColor Green
