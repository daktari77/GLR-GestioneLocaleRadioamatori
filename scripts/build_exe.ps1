<#
Build a portable executable for GestioneSoci (Windows) using PyInstaller.

Standard paths (as agreed):
    - Sviluppo (repo):      G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2
    - Test (dist portable): G:\Il mio Drive\GestioneSoci\GestioneSoci_Current\GestioneSoci_v0.4.2\artifacts\dist_portable
    - Produzione (portable):E:\PortableApps\GestioneSoci

Usage (PowerShell):
  cd <repo-root>\src
  ..\scripts\build_exe.ps1

Notes:
- This script tries to use an existing PyInstaller installation. If not found
  it will prompt to install it into the active Python environment (requires
  Internet). The packaging step can be long.
- The script uses --onefile to produce a single EXE; the bundled application
  will contain the Python interpreter and modules. External data (DB file)
  is not modified: runtime will still look for `data\soci.db` relative to
  the executable — copy your DB alongside the EXE if you want a portable DB.
#>

param(
    [string]$EntryScript = "main.py",
    [string]$ExeName = "GestioneSociPortable",
    [switch]$Windowed,
    [string]$SeedDataDir = "data_seed_portable",
    [string]$DistFolderName = "",
    [string]$IconPath = "",
    [switch]$PruneOldTestBuilds,
    [int]$KeepTestBuilds = 3
)

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

function Resolve-PythonExe([string]$repoRootPath) {
    $venv = Join-Path $repoRootPath '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        # Avoid the WindowsApps stub that redirects to the Microsoft Store
        if ($cmd.Source -like '*\\WindowsApps\\python.exe') { }
        else { return $cmd.Source }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return 'py -3' }

    return $null
}

# Work from the repository root; assume 'src' directory contains the entrypoint
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$src = Join-Path $repoRoot 'src'
Push-Location -ErrorAction Stop $src
Write-Info "Building from: $src"

$pythonExe = Resolve-PythonExe -repoRootPath $repoRoot
if (-not $pythonExe) {
    Write-Err "Python not found in PATH and no repo .venv detected. Create/activate a venv under $repoRoot\.venv or add Python to PATH."
    Pop-Location
    exit 1
}
Write-Info "Python executable: $pythonExe"

if (-not (Test-Path $EntryScript)) {
    Write-Err "Entry script '$EntryScript' not found in $src. Aborting."
    Pop-Location
    exit 1
}

# Check PyInstaller availability in the selected Python environment
$pyinstallerVersion = $null
try {
    if ($pythonExe -eq 'py -3') {
        $pyinstallerVersion = & py -3 -m PyInstaller --version 2>$null
    } else {
        $pyinstallerVersion = & $pythonExe -m PyInstaller --version 2>$null
    }
    if ($LASTEXITCODE -ne 0) { throw "notfound" }
    Write-Info "PyInstaller found (module): $pyinstallerVersion"
} catch {
    Write-Warn "PyInstaller not available in the selected Python environment. Attempting to install it (requires Internet)."
    if ($pythonExe -eq 'py -3') {
        & py -3 -m pip install --upgrade pip setuptools wheel
        & py -3 -m pip install pyinstaller
        $pyinstallerVersion = & py -3 -m PyInstaller --version 2>$null
    } else {
        & $pythonExe -m pip install --upgrade pip setuptools wheel
        & $pythonExe -m pip install pyinstaller
        $pyinstallerVersion = & $pythonExe -m PyInstaller --version 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to install PyInstaller. Install it manually and re-run this script."
        Pop-Location
        exit 1
    }
    Write-Info "PyInstaller installed: $pyinstallerVersion"
}

# Prepare output directory
$ts = Get-Date -Format yyyyMMdd_HHmmss
$distRoot = Join-Path $repoRoot "artifacts\dist_portable"
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$distBase = if ([string]::IsNullOrWhiteSpace($DistFolderName)) {
    Join-Path $distRoot "dist_portable_$ts"
} else {
    Join-Path $distRoot $DistFolderName
}
# Let PyInstaller create the dist folder; this avoids leaving empty folders around when the build fails early.

# Build arguments
# Keep PyInstaller output less verbose (it often logs to stderr and can be noisy in PowerShell hosts)
$buildArgs = @('--noconfirm','--onefile','--name', $ExeName, '--log-level=WARN')
if ($Windowed) { $buildArgs += '--windowed' }

function Invoke-PythonArgs([string[]]$pyArgs) {
    if ($pythonExe -eq 'py -3') {
        & py -3 @pyArgs
    } else {
        & $pythonExe @pyArgs
    }
    return $LASTEXITCODE
}

function Resolve-IconIco([string]$repoRootPath) {
    # Priority:
    # 1) Explicit -IconPath
    # 2) assets/gestionale.ico
    # 3) Generate assets/gestionale.ico from assets/gestionale.png (requires Pillow)

    if (-not [string]::IsNullOrWhiteSpace($IconPath)) {
        $p = Resolve-Path -LiteralPath $IconPath -ErrorAction SilentlyContinue
        if ($p) { return $p.Path }
        Write-Warn "IconPath not found: $IconPath"
        return $null
    }

    $assetsDir = Join-Path $repoRootPath 'assets'
    $ico = Join-Path $assetsDir 'gestionale.ico'
    $png = Join-Path $assetsDir 'gestionale.png'

    if (Test-Path $ico) {
        return (Resolve-Path -LiteralPath $ico).Path
    }

    if (Test-Path $png) {
        try {
            $script = Join-Path $repoRootPath 'scripts\make_icon_ico.py'
            if (Test-Path $script) {
                Write-Info "Generating ICO from PNG: $png -> $ico"
                $exitCode = Invoke-PythonArgs @($script, $png, $ico)
                if ($exitCode -eq 0 -and (Test-Path $ico)) {
                    return (Resolve-Path -LiteralPath $ico).Path
                }
                Write-Warn "Icon generation failed (exit $exitCode). Install Pillow or provide assets/gestionale.ico."
            } else {
                Write-Warn "Missing converter script: $script"
            }
        } catch {
            Write-Warn "Icon generation error: $($_.Exception.Message)"
        }
    }

    return $null
}

$iconIcoResolved = Resolve-IconIco -repoRootPath $repoRoot
if ($iconIcoResolved) {
    Write-Info "Using icon: $iconIcoResolved"
    $buildArgs += @('--icon', $iconIcoResolved)
} else {
    Write-Warn "No icon configured. To set it, provide assets/gestionale.ico (or assets/gestionale.png + Pillow)."
}

function Copy-SeedData([string]$seedDirName, [string]$destDir) {
    $seedPath = Join-Path $src $seedDirName
    if (-not (Test-Path $seedPath)) {
        Write-Warn "Seed data folder '$seedDirName' not found in $src. Skipping seed data copy."
        return
    }
    $destData = Join-Path $destDir 'data'
    if (Test-Path $destData) {
        Remove-Item -Recurse -Force $destData
    }
    New-Item -ItemType Directory -Path $destData -Force | Out-Null
    Copy-Item -Path (Join-Path $seedPath '*') -Destination $destData -Recurse -Force
    Write-Info "Seed data copied to: $destData"
}

# Output to a temporary build dir to avoid polluting src/
$workpath = Join-Path $repoRoot 'artifacts\build_pyinstaller'
if (Test-Path $workpath) { Remove-Item $workpath -Recurse -Force }

Write-Info "Running PyInstaller... this may take a while"
# Always run PyInstaller via the selected Python environment to avoid PATH issues
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    if ($pythonExe -eq 'py -3') {
        # PyInstaller often logs INFO to stderr; stringify to avoid misleading NativeCommandError records.
        & py -3 -m PyInstaller @buildArgs --distpath $distBase --workpath $workpath $EntryScript 2>&1 | ForEach-Object { $_.ToString() }
    } else {
        & $pythonExe -m PyInstaller @buildArgs --distpath $distBase --workpath $workpath $EntryScript 2>&1 | ForEach-Object { $_.ToString() }
    }
    $exit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $oldEap
}

if ($exit -ne 0) {
    Write-Err "PyInstaller failed (exit code $exit). Check the log above."
    if (Test-Path $distBase) {
        try { Remove-Item -Recurse -Force $distBase -ErrorAction SilentlyContinue } catch { }
    }
    Pop-Location
    exit 1
}

$exePath = Join-Path $distBase ("$ExeName.exe")
if (-not (Test-Path $exePath)) {
    Write-Err "Build did not produce expected EXE: $exePath"
    if (Test-Path $distBase) {
        try { Remove-Item -Recurse -Force $distBase -ErrorAction SilentlyContinue } catch { }
    }
    Pop-Location
    exit 1
}

Copy-SeedData $SeedDataDir $distBase

# Copy betatest guide into the portable folder (used by the first-run intro in 0.4.5*)
try {
    $guideSrc = Join-Path $repoRoot 'docs\BETATEST_GUIDE.md'
    if (Test-Path $guideSrc) {
        $docsDestDir = Join-Path $distBase 'docs'
        New-Item -ItemType Directory -Path $docsDestDir -Force | Out-Null
        Copy-Item -Path $guideSrc -Destination (Join-Path $docsDestDir 'BETATEST_GUIDE.md') -Force
        Write-Info "Betatest guide copied to: $docsDestDir"
    } else {
        Write-Warn "Betatest guide not found at: $guideSrc (skipping copy)"
    }
} catch {
    Write-Warn "Failed to copy betatest guide: $($_.Exception.Message)"
}

Write-Info "Build complete. Dist directory: $distBase"
Write-Info "Portable folder contains EXE + seeded 'data' (no soci.db) for a clean first-run test."

# Record last portable build folder name for deploy scripts
try {
    $lastBuildFile = Join-Path $repoRoot "artifacts\last_portable_build.txt"
    $distLeaf = Split-Path -Leaf $distBase
    if (-not [string]::IsNullOrWhiteSpace($distLeaf)) {
        Set-Content -Path $lastBuildFile -Value $distLeaf -Encoding UTF8
        Write-Info "Updated last portable build marker: $lastBuildFile -> $distLeaf"
    } else {
        Write-Warn "Could not determine dist folder name to update last_portable_build.txt"
    }
} catch {
    Write-Warn "Failed to update last_portable_build.txt: $($_.Exception.Message)"
}

function Remove-OldTestBuilds([string]$distRootPath, [string]$currentDistPath, [int]$keep) {
    if ([string]::IsNullOrWhiteSpace($distRootPath) -or -not (Test-Path $distRootPath)) { return }
    if ($keep -lt 1) { $keep = 1 }

    $currentName = Split-Path -Leaf $currentDistPath
    $candidates = Get-ChildItem -Path $distRootPath -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like 'dist_portable_test_*' -and
            $_.Name -ne 'dist_portable_test_marker' -and
            $_.Name -ne $currentName
        } |
        Sort-Object LastWriteTime -Descending

    # Keep the newest ($keep-1) besides the current folder
    $keepOthers = [Math]::Max(0, $keep - 1)
    $toRemove = @()
    if ($candidates.Count -gt $keepOthers) {
        $toRemove = $candidates | Select-Object -Skip $keepOthers
    }

    foreach ($dir in $toRemove) {
        try {
            Remove-Item -Recurse -Force $dir.FullName -ErrorAction Stop
            Write-Info "Pruned old test build: $($dir.Name)"
        } catch {
            Write-Warn "Failed to prune old test build '$($dir.Name)': $($_.Exception.Message)"
        }
    }
}

# Auto-prune old test builds when building a dist_portable_test_* folder
$distLeaf = Split-Path -Leaf $distBase
if ($PruneOldTestBuilds -or ($distLeaf -like 'dist_portable_test_*')) {
    Remove-OldTestBuilds -distRootPath $distRoot -currentDistPath $distBase -keep $KeepTestBuilds
}

Pop-Location
Write-Host "Done." -ForegroundColor Green
