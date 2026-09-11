$ErrorActionPreference = "Stop"

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
# prevents PyInstaller from replacing it. Stop only NightAzimuth processes
# before starting the build.
$runningNightAzimuth = Get-Process -Name "NightAzimuth" -ErrorAction SilentlyContinue
if ($runningNightAzimuth) {
    Write-Host "Stopping running NightAzimuth process before rebuild..."
    $runningNightAzimuth | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "NightAzimuth dependency installation failed."
}

Write-Host "Building NightAzimuth.exe..."
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

$exePath = Join-Path $repoRoot "dist\NightAzimuth.exe"
if (-not (Test-Path $exePath)) {
    throw "Build finished without producing $exePath"
}

$userGuideSource = Join-Path $repoRoot "docs\NightAzimuth_User_Guide.md"
$userGuideDestination = Join-Path $repoRoot "dist\NightAzimuth_User_Guide.md"
if (-not (Test-Path $userGuideSource)) {
    throw "User guide was not found at $userGuideSource"
}
Copy-Item $userGuideSource $userGuideDestination -Force
if (-not (Test-Path $userGuideDestination)) {
    throw "Build finished without producing $userGuideDestination"
}

Write-Host ""
Write-Host "Build complete: $exePath"
Write-Host "User guide: $userGuideDestination"
