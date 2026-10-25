$ErrorActionPreference = "Stop"

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

if (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} else {
    $python = "python"
}

& $python -c @'
from pathlib import Path

root = Path("src")
for path in sorted(root.rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    print(f"OK {path}")
print("Sintaxis OK.")
'@

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
