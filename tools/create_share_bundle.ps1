param(
    [switch]$Rebuild,
    [switch]$SkipApiBundle
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$distAppRoot = Join-Path $projectRoot 'dist\Shadow'
$releaseRoot = Join-Path $projectRoot 'release'
$stageRoot = Join-Path $releaseRoot 'Shadow-V5-Share'
$zipPath = Join-Path $releaseRoot 'Shadow-V5-Share.zip'

if ($Rebuild) {
    & (Join-Path $PSScriptRoot 'build_windows_release.ps1') -Clean
}

if (!(Test-Path (Join-Path $distAppRoot 'Shadow.exe'))) {
    throw 'Missing dist\Shadow\Shadow.exe. Run build_windows_release.ps1 first.'
}

if (Test-Path $stageRoot) {
    Remove-Item -Recurse -Force $stageRoot
}
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

# 1) Copy executable bundle (exe on top level for visibility)
Copy-Item -Recurse -Force (Join-Path $distAppRoot '*') $stageRoot

# 2) Remove any accidental private runtime files
$privateCandidates = @(
    (Join-Path $stageRoot 'config.json'),
    (Join-Path $stageRoot 'data'),
    (Join-Path $stageRoot 'logs'),
    (Join-Path $stageRoot 'tmp'),
    (Join-Path $stageRoot 'tmp_frames')
)
foreach ($item in $privateCandidates) {
    if (Test-Path $item) {
        Remove-Item -Recurse -Force $item
    }
}

# 3) Add friendly launchers/readme
$launcherBat = Join-Path $stageRoot '00_双击启动_Shadow.bat'
$launcherContent = @"
@echo off
setlocal
cd /d %~dp0
start "" "%~dp0Shadow.exe"
endlocal
"@
Set-Content -Path $launcherBat -Value $launcherContent -Encoding Ascii

$readmePath = Join-Path $stageRoot '给用户_使用说明.txt'
$readmeContent = @"
Shadow V5 使用说明
==================
1. 解压后，直接双击“00_双击启动_Shadow.bat”或“Shadow.exe”。
2. 程序首次运行会在当前解压目录生成 config.json（与 Shadow.exe 同目录）。
3. 分享包不包含发布者本地 Cookie、日志、聊天数据库等隐私数据。
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8

if (-not $SkipApiBundle) {
    # 4) Bundle local cached NeteaseCloudMusicApi + Node runtime into frozen bundle path
    $runtimeRoot = Join-Path $stageRoot '_internal\runtime\NeteaseCloudMusicApi'
    if (Test-Path $runtimeRoot) {
        Remove-Item -Recurse -Force $runtimeRoot
    }
    New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

    $npxRoot = Join-Path $projectRoot 'data\npm_cache\_npx'
    $serverCandidates = @()
    if (Test-Path $npxRoot) {
        $serverCandidates = Get-ChildItem -Path (Join-Path $npxRoot '*\node_modules\NeteaseCloudMusicApi\server.js') -File -ErrorAction SilentlyContinue
    }

    if ($serverCandidates.Count -gt 0) {
        $latestServer = $serverCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $npxHashRoot = $latestServer.Directory.Parent.Parent.FullName
        $nodeModulesSrc = Join-Path $npxHashRoot 'node_modules'
        if (Test-Path $nodeModulesSrc) {
            Copy-Item -Recurse -Force $nodeModulesSrc (Join-Path $runtimeRoot 'node_modules')
        }
    }

    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCmd -and $nodeCmd.Source) {
        $nodeSourceDir = Split-Path -Parent $nodeCmd.Source
        $nodeTargetDir = Join-Path $runtimeRoot 'node'
        New-Item -ItemType Directory -Force -Path $nodeTargetDir | Out-Null
        foreach ($pattern in @('node.exe', 'node.dll', 'icu*.dat', 'lib*.dll')) {
            Get-ChildItem -Path (Join-Path $nodeSourceDir $pattern) -File -ErrorAction SilentlyContinue | ForEach-Object {
                Copy-Item -Force $_.FullName (Join-Path $nodeTargetDir $_.Name)
            }
        }
    }

    $startApiBat = Join-Path $runtimeRoot 'start_api.bat'
$startApiContent = @"
@echo off
setlocal
cd /d %~dp0
set "LOCAL_TMP_DIR=%~dp0..\..\..\data\tmp"
if not exist "%LOCAL_TMP_DIR%" mkdir "%LOCAL_TMP_DIR%"
set "TEMP=%LOCAL_TMP_DIR%"
set "TMP=%LOCAL_TMP_DIR%"
set "TMPDIR=%LOCAL_TMP_DIR%"
set "ANON_TOKEN_FILE=%LOCAL_TMP_DIR%\anonymous_token"
if not exist "%ANON_TOKEN_FILE%" (
    >"%ANON_TOKEN_FILE%" (
        echo anonymous
    )
)
if exist ".\node\node.exe" (
    ".\node\node.exe" -e "require('./node_modules/NeteaseCloudMusicApi/server.js').serveNcmApi({checkVersion:false})"
) else (
    node -e "require('./node_modules/NeteaseCloudMusicApi/server.js').serveNcmApi({checkVersion:false})"
)
endlocal
"@
    Set-Content -Path $startApiBat -Value $startApiContent -Encoding Ascii
}

# 5) Zip output for direct sharing
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host 'Share bundle ready:' -ForegroundColor Green
Write-Host $stageRoot
Write-Host $zipPath
