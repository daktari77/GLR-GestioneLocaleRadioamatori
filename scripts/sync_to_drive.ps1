param(
    [string]$Source = (Resolve-Path "$PSScriptRoot\.."),
    [string]$Destination = "D:\GestioneSoci_v4.1",
    [string]$LogFile = "D:\GestioneSoci_v4.1\robocopy.log"
)

if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination | Out-Null
}

$robocopyArgs = @(
    $Source,
    $Destination,
    '/MIR',
    '/R:2',
    '/W:5',
    '/XD', '.git', '.venv',
    '/XF', 'thumbs.db', '*.pyc',
    "/LOG+:$LogFile"
)

Write-Host "[sync_to_drive] Running robocopy..." -ForegroundColor Cyan
& robocopy.exe @robocopyArgs
$exitCode = $LASTEXITCODE

if ($exitCode -le 3) {
    Write-Host "[sync_to_drive] Completed with exit code $exitCode." -ForegroundColor Green
    exit 0
} else {
    Write-Warning "[sync_to_drive] Robocopy exited with code $exitCode. Check the log for details."
    exit $exitCode
}
