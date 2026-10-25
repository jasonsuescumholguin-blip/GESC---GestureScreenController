param([string]$Python = "python")

$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

function Invoke-Checked {
    $executable = $args[0]
    $commandArguments = @($args | Select-Object -Skip 1)
    & $executable @commandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (${LASTEXITCODE}): $executable $commandArguments"
    }
}

$interpreter = $Python
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    $interpreter = '.\.venv\Scripts\python.exe'
}
Invoke-Checked $interpreter -c 'import sys; print(sys.version); sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) and sys.maxsize > 2**32 else "Use 64-bit Python 3.10-3.14 (3.12 recommended). Recreate .venv if necessary.")'

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    Invoke-Checked $Python -m venv .venv
}

Invoke-Checked ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
Invoke-Checked ".\.venv\Scripts\python.exe" -m pip install -e .
if (-not (Test-Path -LiteralPath 'config.json')) {
    Copy-Item -LiteralPath 'config.example.json' -Destination 'config.json'
}
& ".\scripts\download_model.ps1"
if (-not (Test-Path -LiteralPath 'models\hand_landmarker.task')) {
    throw 'Model download failed.'
}

Write-Host ""
Write-Host 'Setup complete. Run .\scripts\run.ps1'
