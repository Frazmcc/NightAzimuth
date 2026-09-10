$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host "Building NightAzimuth.exe..."
& .\.venv\Scripts\python.exe -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --windowed `
    --name NightAzimuth `
    --collect-data skyfield `
    nightazimuth_gui_launcher.py

Write-Host ""
Write-Host "Build complete: $repoRoot\dist\NightAzimuth.exe"
