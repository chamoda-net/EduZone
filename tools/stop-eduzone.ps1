# Stops the local EduZone system: whatever listens on its ports (admin 3001, web 3000, API 8000, the database).
# It finds the server behind each port and ends it with its child processes (Next's workers, Uvicorn's reloader,
# PostgreSQL's processes). Terminal windows stay open; close them yourself or leave them.

param([int]$Port = 0)   # -Port 3000: only what listens there

$Root = Split-Path -Parent $PSScriptRoot

$DbPort = 54393
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^DATABASE_URL=.*:(\d+)/' | Select-Object -First 1
    if ($line) { $DbPort = [int]$line.Matches[0].Groups[1].Value }
}

# Programs that make up a server. Walking up from the listening process stops before shells and terminals.
$ServerNames = @("node.exe", "python.exe", "pythonw.exe", "uvicorn.exe", "postgres.exe", "pg_ctl.exe")

function Get-ServerRoot([int]$ProcessId) {
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if (-not $current) { return $null }
    while ($true) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($current.ParentProcessId)" -ErrorAction SilentlyContinue
        if (-not $parent -or $ServerNames -notcontains $parent.Name.ToLower()) { return $current }
        $current = $parent
    }
}

Write-Host "Stopping EduZone..." -ForegroundColor Cyan
foreach ($entry in @(@(3001, "Admin app"), @(3000, "Web app"), @(8000, "API"), @($DbPort, "Database"))) {
    $entryPort, $name = $entry
    if ($Port -ne 0 -and $entryPort -ne $Port) { continue }
    $listeners = Get-NetTCPConnection -LocalPort $entryPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    if (-not $listeners) { Write-Host "  $name (port $entryPort): not running"; continue }
    foreach ($processId in $listeners) {
        $rootProcess = Get-ServerRoot $processId
        if (-not $rootProcess) { continue }
        & taskkill.exe /PID $rootProcess.ProcessId /T /F 2>&1 | Out-Null
        Write-Host "  $name (port $entryPort): stopped ($($rootProcess.Name))" -ForegroundColor Green
    }
}
Write-Host "Done. The database's data stays in tools\dev-db\data."
