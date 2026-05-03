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
Shadow V5
================
产品简介：
Shadow V5 是一款围绕网易云私信场景整理音乐社交内容的桌面工具。
它把歌曲分享、聊天记录、影子歌单和音乐关系分析整合到同一套界面里，便于回看和整理你与好友之间的音乐互动。
================
启动方式：
1. 解压后，直接双击同目录下的 Shadow.exe。
2. 便携版已经内置 NeteaseCloudMusicApi 运行时，不需要再单独安装 Node.js、npm 或 NeteaseCloudMusicApi。
3. 程序首次运行会在当前目录生成 config.json，配置、缓存、归档、报告和临时文件都会写入当前目录内部。
4. 删除整个解压文件夹，即可清理程序产生的全部内容。
================
登录说明：
1. 启动程序后会先进入登录页。
2. 点击“启动 API”后，程序会拉起本地 API 并检查当前 Cookie 状态。
3. 如果 Cookie 为空或失效，会在按钮下方出现网易云二维码，扫码后即可更新登录状态。
4. 如果 API 和 Cookie 都有效，程序会完成检测后直接进入主页。
5. “重新检测”只重新检查当前状态，不会清空已有内容。
================
功能说明：
1. 首页：
   用于展示当前账号、当前选中好友以及歌曲分享、影子歌单、聊天记录、音乐关系四个主功能入口。
1. 歌曲分享：
   按筛选范围提取与当前好友私信里的歌曲记录，并返回歌曲名称、歌手和消息时间。
2. 影子歌单：
   分为目标歌单、候选歌曲和生成状态三个工作区，用于把聊天里的候选歌曲整理后写入目标歌单。
3. 聊天记录：
   按范围查看与当前好友的聊天归档内容，支持继续筛选和回看。
4. 音乐关系：
   用于查看单好友画像、我的音乐社交、关系节律时间线以及本地分析文段。
5. 设置：
   用于查看 API 状态、Cookie 状态、二维码登录、目标歌单设置和 AI 文段设置。
 =================
补充说明：
1. 筛选条件中的 1 页对应 30 条聊天消息；最近对应最近一段消息窗口；特定页数会按页数向前回看。
2. 歌曲分享、影子歌单和聊天记录都会围绕当前选中好友工作。
3. 音乐关系页中的全好友归档会逐个好友读取和更新内容，数据量较大时可能需要等待更久。
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8

Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host 'Portable package generated:' -ForegroundColor Green
Write-Host $stageRoot
Write-Host $zipPath
