$ErrorActionPreference = "Stop"

# Always run from the repository root, wherever the script is called from.
Set-Location (Resolve-Path "$PSScriptRoot\..\..\..")

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend --host 127.0.0.1 --port 8000
