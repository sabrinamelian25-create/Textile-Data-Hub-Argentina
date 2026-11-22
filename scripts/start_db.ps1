$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$pgBin = Join-Path $root ".tools\pgsql\pgsql\bin"
$pgData = Join-Path $root ".tools\pgdata"
$pgLog = Join-Path $root ".tools\postgres.log"

if (-not (Test-Path "$pgBin\pg_ctl.exe")) {
    Write-Error "Portable PostgreSQL not found at $pgBin"
    exit 1
}

& "$pgBin\pg_ctl.exe" -D $pgData status *> $null
if ($LASTEXITCODE -ne 0) {
    if (Test-Path "$pgData\postgres.log") {
        Remove-Item "$pgData\postgres.log" -Force -ErrorAction SilentlyContinue
    }
    Write-Output "Starting PostgreSQL 16 on port 5432..."
    & "$pgBin\pg_ctl.exe" -D $pgData -l $pgLog -o "-p 5432" -w start
} else {
    Write-Output "PostgreSQL 16 is already running."
}
