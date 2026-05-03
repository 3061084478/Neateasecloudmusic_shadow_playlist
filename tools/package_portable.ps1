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
操作说明：
1. 解压后，直接双击同目录下的 Shadow.exe。
2. 程序首次运行会在当前解压目录生成 config.json。
3. 配置、缓存、归档、报告、二维码登录数据都会写入本地当前解压目录下的 data 文件夹。
4. 删除整个解压文件夹，即可彻底清理本程序产生的全部内容。
================
启动页介绍：
1. api启动：
启动NeteaseCloudMusicApi用于连接网易云接口进行获取数据（api启动失败可以再启动一次）。
2.api启动后会检测cookie（你的身份信息）：
如果cookie为空或者失效则会出现网易云二维码让你扫描以更新身份信息来获取正确数据。
3.如果api已启动或cookie有效则会在验证后直接进入。
================
功能区：
1. 歌曲分享：
	在筛选范围内，查询出与选中好友私信记录中内的歌曲记录。
2. 影子歌单
	（1）目标歌单：
		显示当前选中歌单，该歌单用于添加选中的候选歌曲（产出内容会直接覆盖选中歌单）；不想被覆盖或者想换歌单可以选择右边的新建歌单或者切换歌单。
	（2）候选歌曲
		在筛选范围内，查询出与选中好友私信记录中内的歌曲记录，并进行候选歌曲的选择。
	（3）生成状态
		查看歌单内容的生成效果，也可以用于查看选中歌单里面的内容。
3. 聊天记录
	在筛选范围内，查询出与选中好友私信记录中内的聊天信息。
4. 音乐关系
	（1）单好友画像：
		查看与选中好友的数据分析
	（2）我的音乐社交：
		查看与全部好友的数据分析
	（3）报告中心：
		查看产出的ai文段报告
5. 设置
	查看当前设置状态；
	AI文段设置：
	（1）没有填写内容或填写无效内容：音乐关系功能区的ai产出报告用的是固定模版（默认），不需要用到ai
	（2）填写有效内容：音乐关系功能区的ai产出报告用的是你填写的ai进行分析产出报告，会上传数据到指定AI。
=================
解释区域：
1.  筛选条件中的1页指定的是30条聊天信息；
     最近指定是最近90条聊天信息；
     特定页数值的是现在时间点往前推页数*30条信息；
     新增在歌曲分享和影子歌单部分指的是影子歌单生成内容里最新内容的时间点后的内容，在聊天记录部分指的是  查询聊天记录生成内容里最新内容的时间点后的内容。
2.  在录屏、鼠标移动到界面外部或者是拖动界面移动可能会发生黑色闪屏，这是正常的，你只要全屏进行界面操作就不会发生闪屏，如果卡住重新启动即可。（找不出解决方案）
3.  音乐关系界面右上角的全好友归档按钮是读取全好友未被录入的内容即更新内容功能，所以可能会发生卡顿，这是正常现象（逐个好友读取信息进行判断后并更新工作量大）；当我们进行查询歌曲分享或者是聊天记录的时候就会对单好友进行更新内容。
"@
Set-Content -Path $readmePath -Value $readmeContent -Encoding UTF8

Compress-Archive -Path (Join-Path $stageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host ''
Write-Host 'Portable package generated:' -ForegroundColor Green
Write-Host $stageRoot
Write-Host $zipPath
