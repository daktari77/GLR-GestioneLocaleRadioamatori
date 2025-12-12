param(
    [string]$Source = "D:\",
    [string]$Destination = "G:\Il mio Drive\AriBg",
    [string]$LogFile = "G:\Il mio Drive\AriBg\robocopy_clone.log"
)

if (-not (Test-Path $Source)) {
    Write-Error "Source path '$Source' does not exist."
    exit 1
}

if (-not (Test-Path $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

$logDirectory = Split-Path -Path $LogFile -Parent
if (-not (Test-Path $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

$robocopyArgs = @(
    $Source,
    $Destination,
    '/MIR',
    '/R:2',
    '/W:5'
    '/XD', '$RECYCLE.BIN', 'System Volume Information', '$Recycle.Bin', 'Michele*', 'PortableApps*', 'BackupPersonali*', '*.ts',
    '/XF', 'thumbs.db', 'desktop.ini', 'pagefile.sys', 'hiberfil.sys', '*.pbd'
    #("/LOG+:" + '"' + $LogFile + '"')
)

Write-Host "[clone_drive_to_g] Running robocopy..." -ForegroundColor Cyan
& robocopy.exe @robocopyArgs
$exitCode = $LASTEXITCODE

if ($exitCode -le 3) {
    Write-Host "[clone_drive_to_g] Completed with exit code $exitCode." -ForegroundColor Green
    exit 0
} else {
    Write-Warning "[clone_drive_to_g] Robocopy exited with code $exitCode. Check the log for details."
    exit $exitCode
}
