$ErrorActionPreference = "Stop"
$Root = "C:\Users\1\mc-hosting"
Set-Location "$Root\backend"
$env:PYTHONPATH = "$Root\backend"
& "$Root\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
