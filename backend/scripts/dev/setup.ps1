$ErrorActionPreference = "Stop"

# Always run from the repository root, wherever the script is called from.
Set-Location (Resolve-Path "$PSScriptRoot\..\..\..")

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e "backend[dev]"

Write-Host "Setup complete. Run: .\\backend\\scripts\\dev\\start.ps1"
