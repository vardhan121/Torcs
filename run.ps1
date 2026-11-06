$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Environment not set up. Run .\setup.ps1 first."
}

& $Python (Join-Path $ProjectRoot "main.py") @args
exit $LASTEXITCODE
