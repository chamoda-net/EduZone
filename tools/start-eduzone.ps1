# Starts the local EduZone system, each part in its own window, then opens the sites in Chrome.
#   database (tools/dev-db) -> migrations -> API (8000) -> web app (3000) + admin app (3001) -> Chrome
# A part that is already running (its port answers) is left alone, so running this twice is safe.
# Double-click start-eduzone.bat in the repo root to run it; stop-eduzone.bat closes the windows it opened.

param([switch]$NoBrowser)   # -NoBrowser: start everything but don't open the browser

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$DevDb = Join-Path $Root "tools\dev-db"

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { return $client.ConnectAsync("127.0.0.1", $Port).Wait(400) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}

function Wait-Port([int]$Port, [string]$Name, [int]$Seconds) {
    Write-Host -NoNewline "  waiting for $Name (port $Port)"
    $deadline = (Get-Date).AddSeconds($Seconds)
    while (-not (Test-Port $Port)) {
        if ((Get-Date) -gt $deadline) { Write-Host " ...not up yet, check its window." -ForegroundColor Yellow; return $false }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 1
    }
    Write-Host " ready" -ForegroundColor Green
    return $true
}

# Each part runs in a window titled "EduZone <name>", so stop-eduzone.bat can find and close them.
function Start-Part([string]$Name, [string]$Folder, [string]$Command) {
    Start-Process cmd.exe -WorkingDirectory $Folder -ArgumentList "/k", "title EduZone $Name && $Command"
}

# The database port comes from DATABASE_URL in .env (54393 by default).
$DbPort = 54393
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^DATABASE_URL=.*:(\d+)/' | Select-Object -First 1
    if ($line) { $DbPort = [int]$line.Matches[0].Groups[1].Value }
}

Write-Host ""
Write-Host "EduZone: starting the local system" -ForegroundColor Cyan
Write-Host ""

# 1. Database
if (Test-Port $DbPort) {
    Write-Host "Database: already running on port $DbPort"
} else {
    # A crash or a closed window can leave postmaster.pid behind, which stops PostgreSQL from starting.
    $pidFile = Join-Path $DevDb "data\postmaster.pid"
    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile -TotalCount 1
        if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
            Remove-Item $pidFile -Force
            Write-Host "Database: removed a stale lock file from the last run"
        }
    }
    Write-Host "Database: starting"
    Start-Part "Database" $DevDb "npm start"
    if (-not (Wait-Port $DbPort "the database" 90)) { exit 1 }
}

# 2. Migrations (quick when there is nothing new)
Write-Host "Migrations: bringing the database up to date"
Push-Location $Backend
try {
    # Through cmd: Alembic logs to stderr, which Windows PowerShell 5.1 would treat as an error.
    $out = cmd.exe /c ".venv\Scripts\alembic.exe upgrade head 2>&1"
    $out | Select-String -Pattern "Running upgrade|ERROR|Error" | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) { Write-Host "  Migrations failed; see the message above." -ForegroundColor Red; exit 1 }
}
finally { Pop-Location }

# 3. API (SMS codes and emails print in its window)
if (Test-Port 8000) { Write-Host "API: already running on port 8000" }
else {
    Write-Host "API: starting"
    Start-Part "API" $Backend ".venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"
}

# 4. Web app and admin app
if (Test-Port 3000) { Write-Host "Web app: already running on port 3000" }
else { Write-Host "Web app: starting"; Start-Part "Web" $Frontend "npm run dev:web" }
if (Test-Port 3001) { Write-Host "Admin app: already running on port 3001" }
else { Write-Host "Admin app: starting"; Start-Part "Admin" $Frontend "npm run dev:admin" }

Write-Host ""
$apiUp = Wait-Port 8000 "the API" 60
$webUp = Wait-Port 3000 "the web app" 120
$adminUp = Wait-Port 3001 "the admin app" 120

# 5. Open the sites (Chrome if it is installed, else the default browser)
$urls = @()
if ($webUp) { $urls += "http://localhost:3000" }
if ($adminUp) { $urls += "http://localhost:3001" }
if ($urls.Count -gt 0 -and -not $NoBrowser) {
    $chrome = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chrome) { Start-Process $chrome -ArgumentList $urls }
    else { $urls | ForEach-Object { Start-Process $_ } }
}

Write-Host ""
Write-Host "EduZone is running." -ForegroundColor Green
Write-Host "  Website:    http://localhost:3000"
Write-Host "  Admin app:  http://localhost:3001"
Write-Host "  API:        http://localhost:8000/docs"
Write-Host "SMS codes and emails appear in the 'EduZone API' window. Run stop-eduzone.bat to stop everything."
Write-Host ""
