$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = ".\src"

if (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} else {
    $python = "python"
}

& $python -m screen_controller.doctor
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
