$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path "$Root\backend\app\main.py")) {
  $Root = "C:\Users\1\mc-hosting"
}
Set-Location $Root
Write-Host "ROOT=$Root"

New-Item -ItemType Directory -Force -Path "$Root\data\servers", "$Root\runtime", "$Root\data" | Out-Null

$Venv = "$Root\.venv"
if (-not (Test-Path "$Venv\Scripts\python.exe")) {
  python -m venv $Venv
}
& "$Venv\Scripts\python.exe" -m pip install -q --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -q -r "$Root\backend\requirements.txt"
& "$Venv\Scripts\python.exe" "$Root\scripts\download_paper.py"

Set-Location "$Root\web"
if (-not (Test-Path "node_modules")) {
  npm install
}
$env:NUXT_PUBLIC_API_BASE = ""
$env:NUXT_PUBLIC_SITE_URL = "http://192.168.0.148:8000"
npx nuxi generate

Set-Location $Root
Get-NetFirewallRule -DisplayName "SHNENEPEPE-API" -ErrorAction SilentlyContinue | Out-Null
if (-not $?) {
  try {
    New-NetFirewallRule -DisplayName "SHNENEPEPE-API" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -ErrorAction Stop | Out-Null
    New-NetFirewallRule -DisplayName "SHNENEPEPE-MC" -Direction Inbound -Protocol TCP -LocalPort 25565 -Action Allow -ErrorAction Stop | Out-Null
    Write-Host "Firewall rules added"
  } catch {
    Write-Host "Firewall: run PowerShell as Admin to open 8000 and 25565"
  }
}

$env:BETA_MODE = "true"
Write-Host "Starting API on :8000 and mc-router on :25565"
