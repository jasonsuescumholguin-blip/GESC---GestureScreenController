$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

if (Test-Path -LiteralPath ".venv312\Scripts\python.exe") {
    $python = ".\.venv312\Scripts\python.exe"
} elseif (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} else {
    $python = "python"
}

& $python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
}

if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}

if (Test-Path -LiteralPath "dist\ScreenController") {
    Remove-Item -LiteralPath "dist\ScreenController" -Recurse -Force
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name ScreenController `
    --paths ".\src" `
    --collect-all mediapipe `
    ".\src\screen_controller\__main__.py"

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Copy-Item -LiteralPath ".\config.json" -Destination ".\dist\ScreenController\config.json" -Force
Copy-Item -LiteralPath ".\README.md" -Destination ".\dist\ScreenController\README.md" -Force
Copy-Item -LiteralPath ".\models" -Destination ".\dist\ScreenController\models" -Recurse -Force

Write-Host "Build OK: $root\dist\ScreenController\ScreenController.exe"
