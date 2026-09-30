$ErrorActionPreference = "Stop"

# LEGACY DESKTOP BUILD
#
# The hosted web application at https://nightazimuth.co.uk is the supported
# NightAzimuth product. This script is retained only to keep the historical
# Tkinter/PyInstaller client reproducible and to detect accidental breakage.
# It is not used by the GitHub release workflow.

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment."
    }
}

# A running NightAzimuth.exe keeps the existing file locked on Windows and
# prevents PyInstaller from replacing it. Stop only NightAzimuth processes.
$runningNightAzimuth = Get-Process -Name "NightAzimuth" -ErrorAction SilentlyContinue
if ($runningNightAzimuth) {
    Write-Host "Stopping running NightAzimuth process before legacy rebuild..."
    $runningNightAzimuth | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

$distPath = Join-Path $repoRoot "dist"
if (Test-Path $distPath) {
    Remove-Item $distPath -Recurse -Force
}
New-Item -ItemType Directory -Path $distPath | Out-Null

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "NightAzimuth dependency installation failed."
}

Write-Host "Building legacy NightAzimuth.exe..."
& .\.venv\Scripts\python.exe -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --windowed `
    --name NightAzimuth `
    --collect-data skyfield `
    nightazimuth_gui_launcher.py

if ($LASTEXITCODE -ne 0) {
    throw "NightAzimuth.exe build failed with exit code $LASTEXITCODE."
}

$exePath = Join-Path $distPath "NightAzimuth.exe"
if (-not (Test-Path $exePath)) {
    throw "Build finished without producing $exePath"
}

$legacyReadmeSource = Join-Path $repoRoot "docs\LEGACY_DESKTOP.md"
$legacyReadmeDestination = Join-Path $distPath "NightAzimuth_Legacy_Desktop.md"
if (-not (Test-Path $legacyReadmeSource)) {
    throw "Legacy desktop notice was not found at $legacyReadmeSource"
}
Copy-Item $legacyReadmeSource $legacyReadmeDestination -Force
if (-not (Test-Path $legacyReadmeDestination)) {
    throw "Build finished without producing $legacyReadmeDestination"
}

# Legacy-output allowlist. Nothing else is permitted in dist.
$expectedFiles = @(
    "NightAzimuth.exe",
    "NightAzimuth_Legacy_Desktop.md"
)
$files = @(Get-ChildItem $distPath -File)
$directories = @(Get-ChildItem $distPath -Directory)
$unexpectedFiles = @($files | Where-Object { $_.Name -notin $expectedFiles })
$missingFiles = @($expectedFiles | Where-Object { -not (Test-Path (Join-Path $distPath $_)) })

if ($directories.Count -gt 0) {
    $names = ($directories.Name -join ", ")
    throw "Unexpected directories found in dist: $names"
}
if ($unexpectedFiles.Count -gt 0) {
    $names = ($unexpectedFiles.Name -join ", ")
    throw "Unexpected files found in dist: $names"
}
if ($missingFiles.Count -gt 0) {
    $names = ($missingFiles -join ", ")
    throw "Expected legacy build files are missing from dist: $names"
}
if ($files.Count -ne $expectedFiles.Count) {
    throw "Legacy build output contains an unexpected number of files."
}

Write-Host ""
Write-Host "Legacy build complete: $exePath"
Write-Host "Legacy notice: $legacyReadmeDestination"
Write-Host "This output is not published by the current GitHub release workflow."
Write-Host "Supported product: https://nightazimuth.co.uk"
