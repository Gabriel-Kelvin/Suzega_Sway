param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $vitePath)) {
    throw 'Install dependencies first. See README.md.'
}
$runtimeDir = Join-Path $projectRoot 'work'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$records = @()
$pidFile = Join-Path $runtimeDir 'servers.json'
if (Test-Path -LiteralPath $pidFile) {
    $records = @(Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)
}
$services = @(
    @{ Name='api'; Port=8000; File=$pythonPath; Args=@('-m','uvicorn','app.main:app','--app-dir',('"' + (Join-Path $projectRoot 'backend') + '"'),'--host','127.0.0.1','--port','8000'); Directory=$projectRoot },
    @{ Name='web'; Port=5173; File=(Get-Command node.exe).Source; Args=@(('"' + $vitePath + '"'),'--host','127.0.0.1','--port','5173','--strictPort'); Directory=(Join-Path $projectRoot 'frontend') }
)
foreach ($service in $services) {
    $listener = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener[0].OwningProcess)"
        if (!$owner.CommandLine -or !$owner.CommandLine.Contains($projectRoot)) {
            throw "Port $($service.Port) is already occupied by another process. Stop it or choose another port in the configuration."
        }
        Write-Host "$($service.Name) already running on port $($service.Port)."
        continue
    }
    $process = Start-Process -FilePath $service.File -ArgumentList $service.Args -WorkingDirectory $service.Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$($service.Name).log") -RedirectStandardError (Join-Path $runtimeDir "$($service.Name).error.log")
    $records = @($records | Where-Object { $_.name -ne $service.Name }) + @{name=$service.Name;pid=$process.Id}
    ConvertTo-Json -InputObject @($records) | Set-Content -LiteralPath $pidFile
}
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $web = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
        if ($health.status -eq 'ok' -and $web.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (!$ready) { throw 'Startup timed out. Inspect work/api.error.log and work/web.error.log.' }
Write-Host 'Sway is ready at http://127.0.0.1:5173'
Write-Host 'Data stays in data/sway.db. Run ./stop.ps1 to stop the local services.'
if (!$NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
