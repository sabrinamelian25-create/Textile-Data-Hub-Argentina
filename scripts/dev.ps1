$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
& "$PSScriptRoot\start_db.ps1"

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$nodeBin = Join-Path $root ".tools\node\node-v24.22.3-win-x64"
$env:PATH = "$nodeBin;$env:PATH"

$apiJob = Start-Job -ScriptBlock {
    param($r, $p)
    $ErrorActionPreference = "Continue"
    Set-Location "$r\backend"
    $env:PYTHONPATH = "$r\backend"
    & $p -m uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 | ForEach-Object { "$_" }
} -ArgumentList $root, $py

$webJob = Start-Job -ScriptBlock {
    param($r, $nb)
    $ErrorActionPreference = "Continue"
    Set-Location "$r\frontend"
    $env:PATH = "$nb;$env:PATH"
    & "$nb\npm.cmd" run dev 2>&1 | ForEach-Object { "$_" }
} -ArgumentList $root, $nodeBin

Write-Output "API running at http://127.0.0.1:8000 (OpenAPI: /docs)"
Write-Output "Frontend running at http://localhost:3000"
Write-Output "Press Ctrl+C to stop both services."
try {
    while ($true) {
        Start-Sleep -Seconds 2
        Receive-Job $apiJob -ErrorAction Continue
        Receive-Job $webJob -ErrorAction Continue
    }
} finally {
    Stop-Job $apiJob, $webJob -ErrorAction SilentlyContinue
    Remove-Job $apiJob, $webJob -ErrorAction SilentlyContinue
}
