$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

$modelsDir = Join-Path (Get-Location) "models"
$modelPath = Join-Path $modelsDir "hand_landmarker.task"
$modelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

if (-not (Test-Path -LiteralPath $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir | Out-Null
}

if (Test-Path -LiteralPath $modelPath) {
    Write-Host "Modelo ya existe: $modelPath"
    return
}

Write-Host "Descargando modelo MediaPipe Hand Landmarker..."
$temporaryPath = "$modelPath.tmp"
try {
    Invoke-WebRequest -Uri $modelUrl -OutFile $temporaryPath
    if ((Get-Item -LiteralPath $temporaryPath).Length -eq 0) {
        throw "Downloaded model is empty."
    }
    Move-Item -LiteralPath $temporaryPath -Destination $modelPath -Force
} finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}
Write-Host "Modelo descargado: $modelPath"
