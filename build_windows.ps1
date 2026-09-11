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

# Start every release build from an empty dist directory. This prevents stale
# files from an earlier local build from being accidentally shipped.
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

$exePath = Join-Path $distPath "NightAzimuth.exe"
if (-not (Test-Path $exePath)) {
    throw "Build finished without producing $exePath"
}

$userGuideSource = Join-Path $repoRoot "docs\NightAzimuth_User_Guide.md"
$userGuideDestination = Join-Path $distPath "NightAzimuth_User_Guide.md"
if (-not (Test-Path $userGuideSource)) {
    throw "User guide was not found at $userGuideSource"
}
Copy-Item $userGuideSource $userGuideDestination -Force
if (-not (Test-Path $userGuideDestination)) {
    throw "Build finished without producing $userGuideDestination"
}

# Release-output allowlist. Nothing else is permitted in dist.
$expectedReleaseFiles = @(
    "NightAzimuth.exe",
    "NightAzimuth_User_Guide.md"
)
$releaseFiles = @(Get-ChildItem $distPath -File)
$releaseDirectories = @(Get-ChildItem $distPath -Directory)
$unexpectedFiles = @($releaseFiles | Where-Object { $_.Name -notin $expectedReleaseFiles })
$missingFiles = @($expectedReleaseFiles | Where-Object { -not (Test-Path (Join-Path $distPath $_)) })

if ($releaseDirectories.Count -gt 0) {
    $names = ($releaseDirectories.Name -join ", ")
    throw "Unexpected release directories found in dist: $names"
}
if ($unexpectedFiles.Count -gt 0) {
    $names = ($unexpectedFiles.Name -join ", ")
    throw "Unexpected release files found in dist: $names"
}
if ($missingFiles.Count -gt 0) {
    $names = ($missingFiles -join ", ")
    throw "Expected release files are missing from dist: $names"
}
if ($releaseFiles.Count -ne $expectedReleaseFiles.Count) {
    throw "Release output contains an unexpected number of files."
}

Write-Host ""
Write-Host "Build complete: $exePath"
Write-Host "User guide: $userGuideDestination"
Write-Host "Release output validated: only approved files are present in dist."
