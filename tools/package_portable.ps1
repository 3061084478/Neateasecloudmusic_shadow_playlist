Param(
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distApp = Join-Path $projectRoot "dist\Shadow"
$releaseRoot = Join-Path $projectRoot "release"
$portableDir = Join-Path $releaseRoot "Shadow-V5-Portable"

if ($Rebuild) {
    & (Join-Path $PSScriptRoot "build_windows_release.ps1") -Clean
}

if (!(Test-Path (Join-Path $distApp "Shadow.exe"))) {
    throw "Missing dist\\Shadow\\Shadow.exe. Run build_windows_release.ps1 first."
}

if (Test-Path $portableDir) {
    Remove-Item -Recurse -Force $portableDir
}
New-Item -ItemType Directory -Force -Path $portableDir | Out-Null
Copy-Item -Recurse -Force $distApp (Join-Path $portableDir "Shadow")

$launcherPath = Join-Path $portableDir "Launch Shadow.bat"
$launcherContent = @"
@echo off
setlocal
cd /d %~dp0
start "" "%~dp0Shadow\Shadow.exe"
endlocal
"@
Set-Content -Path $launcherPath -Value $launcherContent -Encoding Ascii

$readmePath = Join-Path $portableDir "README.txt"
$readmeContent = @"
Shadow V5
==================

1. Double-click "Launch Shadow.bat" to run.
2. On first run, config.json is created in the extracted folder (same level as Shadow.exe).
3. If runtime\NeteaseCloudMusicApi exists, app will try bundled API first.
4. End users do not need to install Python dependencies manually.
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8

Write-Host ""
Write-Host "Portable package generated:" -ForegroundColor Green
Write-Host $portableDir
