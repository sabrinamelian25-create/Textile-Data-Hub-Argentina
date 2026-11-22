$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pgBin = Join-Path $root ".tools\pgsql\pgsql\bin"
$pgData = Join-Path $root ".tools\pgdata"

if (Test-Path "$pgBin\pg_ctl.exe") {
    & "$pgBin\pg_ctl.exe" -D $pgData status 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Stopping PostgreSQL 16..."
        & "$pgBin\pg_ctl.exe" -D $pgData stop -m fast
    } else {
        Write-Output "PostgreSQL 16 is not running."
    }
}
