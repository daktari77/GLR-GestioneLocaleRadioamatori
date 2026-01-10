<#
Deploy the latest TEST portable build to the production portable folder.

Standard paths (as agreed):
  - Sviluppo (repo):       G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2
  - Test (dist portable):  G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2\artifacts\dist_portable
  - Produzione (portable): E:\PortableApps\GestioneSoci

Behavior:
- Reads the latest build folder name from artifacts\last_portable_build.txt
- Creates a timestamped backup under E:\PortableApps\GestioneSoci\backup\deploy_backup_<timestamp>\
  (backs up production EXE + soci.db + optional WAL/SHM sidecars)
- Copies ONLY the EXE from the test build into production.
  (Does NOT overwrite production data folder, to avoid data loss.)

Usage (PowerShell):
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
  .\scripts\deploy_to_production.ps1

Optional:
  .\scripts\deploy_to_production.ps1 -DryRun
#>

param(
    [string]$ProductionRoot = "E:\PortableApps\GestioneSoci",
    [string]$ExeName = "GestioneSociPortable.exe",
    [switch]$DryRun
)

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$lastBuildFile = Join-Path $repoRoot "artifacts\last_portable_build.txt"
$distRoot = Join-Path $repoRoot "artifacts\dist_portable"

if (-not (Test-Path $lastBuildFile)) {
    Write-Err "Missing file: $lastBuildFile"
    exit 1
}

$buildName = (Get-Content -Path $lastBuildFile | Where-Object { $_ -and $_.Trim() -ne '' } | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($buildName)) {
    Write-Err "Cannot determine last build name from: $lastBuildFile"
    exit 1
}

$sourceDir = Join-Path $distRoot $buildName
$sourceExe = Join-Path $sourceDir $ExeName

if (-not (Test-Path $sourceExe)) {
    Write-Err "Source EXE not found: $sourceExe"
    exit 1
}

if (-not (Test-Path $ProductionRoot)) {
    Write-Err "Production root not found: $ProductionRoot"
    exit 1
}

$prodExe = Join-Path $ProductionRoot $ExeName
$prodDb = Join-Path $ProductionRoot "data\soci.db"

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupDir = Join-Path $ProductionRoot ("backup\deploy_backup_$ts")

Write-Info "Repo root: $repoRoot"
Write-Info "Test build: $buildName"
Write-Info "Source EXE: $sourceExe"
Write-Info "Production: $ProductionRoot"
Write-Info "Backup dir: $backupDir"

if ($DryRun) {
    Write-Warn "DryRun enabled: no files will be modified."
}

# Create backup dir
if (-not $DryRun) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

# Backup production EXE (if present)
if (Test-Path $prodExe) {
    $dst = Join-Path $backupDir $ExeName
    Write-Info "Backing up production EXE -> $dst"
    if (-not $DryRun) {
        Copy-Item -Path $prodExe -Destination $dst -Force
    }
} else {
    Write-Warn "Production EXE not found (first deploy?): $prodExe"
}

# Backup soci.db (and WAL/SHM if present)
if (Test-Path $prodDb) {
    $dstDb = Join-Path $backupDir "soci.db"
    Write-Info "Backing up production DB -> $dstDb"
    if (-not $DryRun) {
        Copy-Item -Path $prodDb -Destination $dstDb -Force
    }

    foreach ($suffix in @('-wal','-shm')) {
        $p = "$prodDb$suffix"
        if (Test-Path $p) {
            $dstSide = "$dstDb$suffix"
            Write-Info "Backing up DB sidecar -> $dstSide"
            if (-not $DryRun) {
                Copy-Item -Path $p -Destination $dstSide -Force
            }
        }
    }
} else {
    Write-Warn "Production DB not found: $prodDb"
}

# Deploy EXE only (do not touch production data)
Write-Info "Deploying EXE to production -> $prodExe"
if (-not $DryRun) {
    $maxRetries = 5
    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            Copy-Item -Path $sourceExe -Destination $prodExe -Force -ErrorAction Stop
            break
        } catch {
            if ($i -lt $maxRetries) {
                Write-Warn "Failed to copy EXE (attempt $i/$maxRetries): $($_.Exception.Message)"
                Start-Sleep -Seconds 1
                continue
            }
            Write-Err "Failed to deploy EXE (file may be in use). Close the app and re-run. Details: $($_.Exception.Message)"
            exit 1
        }
    }
}

Write-Info "Deploy completed."
Write-Info "You can roll back by restoring EXE/DB from: $backupDir"

exit 0
