$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = ".\src"

if (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
    & ".\.venv\Scripts\python.exe" -m screen_controller
} else {
    python -m screen_controller
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
