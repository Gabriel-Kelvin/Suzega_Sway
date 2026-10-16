$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pidFile = Join-Path $projectRoot 'work\servers.json'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Host 'No recorded Sway services.'; exit }
$records = @(Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)
foreach ($record in $records) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($record.pid)" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($projectRoot) -and ($process.CommandLine.Contains('uvicorn') -or $process.CommandLine.Contains('vite'))) {
        Stop-Process -Id $record.pid
        Write-Host "Stopped Sway $($record.name)."
    }
}
Write-Host 'Saved experiments are preserved.'
