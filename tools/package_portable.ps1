param(
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$distAppRoot = Join-Path $projectRoot 'dist\Shadow'
$releaseRoot = Join-Path $projectRoot 'release'
$stageRoot = Join-Path $releaseRoot 'Shadow-V5-Portable'
$zipPath = Join-Path $releaseRoot 'Shadow-V5-Portable.zip'

function Remove-IfExists {
    param([string]$LiteralPath)
    if (Test-Path -LiteralPath $LiteralPath) {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force
    }
}

if ($Rebuild) {
    & (Join-Path $PSScriptRoot 'build_windows_release.ps1') -Clean
}

if (!(Test-Path (Join-Path $distAppRoot 'Shadow.exe'))) {
    throw 'Missing dist\Shadow\Shadow.exe. Run build_windows_release.ps1 first.'
}

Remove-IfExists $stageRoot
Remove-IfExists $zipPath
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

# Copy packaged app bundle directly to the archive root so users can double-click Shadow.exe.
Copy-Item -Recurse -Force (Join-Path $distAppRoot '*') $stageRoot

# Remove any accidental private runtime files from the release copy.
$privateCandidates = @(
    (Join-Path $stageRoot 'config.json'),
    (Join-Path $stageRoot 'data'),
    (Join-Path $stageRoot 'logs'),
    (Join-Path $stageRoot 'tmp'),
    (Join-Path $stageRoot 'tmp_frames')
)
foreach ($item in $privateCandidates) {
    Remove-IfExists $item
}

$bundledWebIndex = Join-Path $stageRoot '_internal\web\dist\index.html'
if (!(Test-Path $bundledWebIndex)) {
    throw 'Portable bundle is missing _internal\web\dist\index.html. Rebuild the desktop app first.'
}

$bundledApiRoot = Join-Path $stageRoot '_internal\runtime\NeteaseCloudMusicApi'
$bundledApiNode = Join-Path $bundledApiRoot 'node.exe'
$bundledApiServer = Join-Path $bundledApiRoot 'server.js'
if (!(Test-Path $bundledApiRoot) -or !(Test-Path $bundledApiNode) -or !(Test-Path $bundledApiServer)) {
    throw 'Portable bundle is missing the controlled runtime\NeteaseCloudMusicApi package or node.exe.'
}

# Strip bundled runtime traces that should not ship to end users.
foreach ($item in @(
    (Join-Path $bundledApiRoot 'data'),
    (Join-Path $bundledApiRoot 'logs'),
    (Join-Path $bundledApiRoot 'tmp'),
    (Join-Path $bundledApiRoot 'tmp_frames')
)) {
    Remove-IfExists $item
}

$readmePath = Join-Path $stageRoot '使用说明.txt'
$readmeContent = @"
Shadow V5 便携版
================
1. 解压后，直接双击同目录下的 Shadow.exe。
2. 程序首次运行会在当前解压目录生成 config.json。
3. 配置、缓存、归档、报告、二维码登录数据都会写入当前解压目录下的 data 文件夹。
4. 删除整个解压文件夹，即可彻底清理本程序产生的全部内容。
5. 发布包不包含发布者本地 Cookie、历史报告、聊天数据库、缓存或日志。
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8

Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host 'Portable package generated:' -ForegroundColor Green
Write-Host $stageRoot
Write-Host $zipPath
