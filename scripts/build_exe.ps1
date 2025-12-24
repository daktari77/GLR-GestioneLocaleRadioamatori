<#
Build a portable executable for GestioneSoci (Windows) using PyInstaller.

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
    [switch]$Windowed
)

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

# Work from the repository root; assume 'src' directory contains the entrypoint
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$src = Join-Path $repoRoot 'src'
Push-Location -ErrorAction Stop $src
Write-Info "Building from: $src"

if (-not (Test-Path $EntryScript)) {
    Write-Err "Entry script '$EntryScript' not found in $src. Aborting."
    Pop-Location
    exit 1
}

# Check pyinstaller
try {
    $pyinstallerVersion = & pyinstaller --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw "notfound" }
    Write-Info "PyInstaller found: $pyinstallerVersion"
} catch {
    Write-Warn "PyInstaller not found in PATH. Attempting to install in current Python environment."
    $python = & python -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Python not found in PATH. Install Python 3.8+ and retry."
        Pop-Location
        exit 1
    }
    Write-Info "Installing PyInstaller into current Python environment (requires Internet)..."
    & $python -m pip install --upgrade pip setuptools wheel
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to install PyInstaller. Install it manually and re-run this script."
        Pop-Location
        exit 1
    }
}

# Prepare output directory
$ts = Get-Date -Format yyyyMMdd_HHmmss
$distBase = Join-Path $src "dist_portable_$ts"
New-Item -ItemType Directory -Path $distBase | Out-Null

# Build arguments
$buildArgs = @('--noconfirm','--onefile','--name', $ExeName)
if ($Windowed) { $buildArgs += '--windowed' }

# Include data directory as relative data (source;destination) for PyInstaller
# Note: on Windows use a semicolon to separate source and target inside the single --add-data argument
if (Test-Path (Join-Path $src 'data')) {
    $dataArg = "data;data"
    $buildArgs += "--add-data";
    $buildArgs += $dataArg
    Write-Info "Including 'data' folder in bundle (will be extracted at runtime)."
} else {
    Write-Warn "No 'data' folder found; the executable will not include the DB or data files."
}

# Output to a temporary build dir to avoid polluting workspace
$workpath = Join-Path $src 'build_pyinstaller'
if (Test-Path $workpath) { Remove-Item $workpath -Recurse -Force }

Write-Info "Running PyInstaller... this may take a while"
# Prefer pyinstaller executable, fall back to 'python -m PyInstaller' when pyinstaller not on PATH
if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    & pyinstaller @buildArgs --distpath $distBase --workpath $workpath $EntryScript
    $exit = $LASTEXITCODE
} else {
    Write-Warn "pyinstaller not on PATH; using 'python -m PyInstaller' instead."
    $python = & python -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Python not found to run PyInstaller. Aborting."
        Pop-Location
        exit 1
    }
    & $python -m PyInstaller @buildArgs --distpath $distBase --workpath $workpath $EntryScript
    $exit = $LASTEXITCODE
}

if ($exit -ne 0) {
    Write-Err "PyInstaller failed (exit code $exit). Check the log above."
    Pop-Location
    exit 1
}

Write-Info "Build complete. Dist directory: $distBase"
Write-Info "If you included 'data', copy or keep your 'data\soci.db' next to the EXE to use your DB."

Pop-Location
Write-Host "Done." -ForegroundColor Green
