$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
& "$PSScriptRoot\start_db.ps1"

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $root "backend"
Push-Location (Join-Path $root "backend")
try {
    & $py -m alembic upgrade head
    & $py -m app.cli seed
    & $py -m app.cli ingest --all
    & $py -m app.cli audit-summary
} finally {
    Pop-Location
}
