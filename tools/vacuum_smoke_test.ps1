param(
    [string]$ZipPath = "C:\Users\ASUS\Desktop\网易云\Shadow-V5-Share.zip",
    [string]$WorkRoot = "C:\Users\ASUS\Desktop\网易云\_vacuum_user_test",
    [int]$WaitSeconds = 12,
    [switch]$AutoStartBundledApi = $true,
    [int]$ApiWaitSeconds = 20,
    [switch]$KillPort3000Owner = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$text) {
    Write-Host "==> $text" -ForegroundColor Cyan
}

function Stop-ProcessSafe([string]$name) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
}

function Get-HttpCode([string]$url, [int]$timeoutSec = 3) {
    try {
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec $timeoutSec -UseBasicParsing
        return [int]$resp.StatusCode
    } catch {
        return -1
    }
}

function Get-PortOwnerPid([int]$port) {
    try {
        $line = netstat -ano -p tcp | Select-String ":$port\s+.*LISTENING\s+(\d+)" | Select-Object -First 1
        if ($line) {
            $m = [regex]::Match($line.Line, "(\d+)\s*$")
            if ($m.Success) { return [int]$m.Groups[1].Value }
        }
    } catch {}
    return $null
}

if (!(Test-Path -LiteralPath $ZipPath)) {
    throw "ZIP 不存在: $ZipPath"
}

Write-Step "准备真空测试目录"
if (Test-Path -LiteralPath $WorkRoot) {
    Remove-Item -Recurse -Force -LiteralPath $WorkRoot
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

$extractDir = Join-Path $WorkRoot "Shadow-V5-Share"
Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractDir -Force

$appDir = $extractDir
$exePath = Join-Path $appDir "Shadow.exe"
$batPath = Join-Path $appDir "00_双击启动_Shadow.bat"
$configPath = Join-Path $appDir "config.json"

if (!(Test-Path -LiteralPath $exePath)) {
    throw "未找到 Shadow.exe: $exePath"
}
if (!(Test-Path -LiteralPath $batPath)) {
    throw "未找到启动脚本: $batPath"
}

Write-Step "确认初始状态（config.json 不存在）"
$initialConfigExists = Test-Path -LiteralPath $configPath

Write-Step "记录启动前进程基线"
$beforeNode = @{}
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $beforeNode[$_.ProcessId] = $_.CommandLine
}
$port3000Before = Get-PortOwnerPid -port 3000
if ($port3000Before -and $KillPort3000Owner) {
    Write-Step "检测到 3000 端口占用，尝试释放 PID=$port3000Before"
    try { Stop-Process -Id $port3000Before -Force -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Seconds 1
    $port3000Before = Get-PortOwnerPid -port 3000
}

Write-Step "启动应用并等待 $WaitSeconds 秒"
$appProcess = Start-Process -FilePath $exePath -WorkingDirectory $appDir -PassThru
Start-Sleep -Seconds $WaitSeconds

Write-Step "检查配置文件是否在解压目录生成"
$configExists = Test-Path -LiteralPath $configPath
$configContent = $null
$configCookieEmpty = $false
if ($configExists) {
    try {
        $configContent = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        $configCookieEmpty = [string]::IsNullOrWhiteSpace([string]$configContent.cookie)
    } catch {
        $configCookieEmpty = $false
    }
}

if ($AutoStartBundledApi) {
    Write-Step "自动启动内置 API（模拟用户点“启动本地 API”）"
    $apiRuntimeDir = Join-Path $appDir "_internal\runtime\NeteaseCloudMusicApi"
    $apiStartBat = Join-Path $apiRuntimeDir "start_api.bat"
    if (Test-Path -LiteralPath $apiStartBat) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$apiStartBat`"" -WorkingDirectory $apiRuntimeDir | Out-Null
        $deadline = (Get-Date).AddSeconds($ApiWaitSeconds)
        do {
            $code = Get-HttpCode -url "http://127.0.0.1:3000/login/status?timestamp=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())" -timeoutSec 2
            if ($code -eq 200) { break }
            Start-Sleep -Milliseconds 500
        } while ((Get-Date) -lt $deadline)
    }
}

Write-Step "探测 API 接口连通性"
$apiLoginStatusCode = -1
$apiQrKeyCode = -1
$apiError = $null
$port3000After = Get-PortOwnerPid -port 3000
try {
    $statusResp = Invoke-WebRequest -Uri "http://127.0.0.1:3000/login/status?timestamp=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())" -TimeoutSec 4 -UseBasicParsing
    $apiLoginStatusCode = [int]$statusResp.StatusCode
    $qrResp = Invoke-WebRequest -Uri "http://127.0.0.1:3000/login/qr/key?timestamp=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())" -TimeoutSec 4 -UseBasicParsing
    $apiQrKeyCode = [int]$qrResp.StatusCode
} catch {
    $apiError = $_.Exception.Message
}

Write-Step "清理测试进程"
if ($appProcess -and (Get-Process -Id $appProcess.Id -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $appProcess.Id -Force -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | Where-Object {
    -not $beforeNode.ContainsKey($_.ProcessId) -and $_.CommandLine -like "*_vacuum_user_test*"
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
}

Write-Host ""
Write-Host "========== Vacuum Smoke Test Result ==========" -ForegroundColor Yellow
$result = [PSCustomObject]@{
    ZipPath                      = $ZipPath
    ExtractDir                   = $extractDir
    InitialConfigExists          = $initialConfigExists
    ConfigExistsAfterRun         = $configExists
    ConfigCookieEmpty            = $configCookieEmpty
    ApiLoginStatusHttpCode       = $apiLoginStatusCode
    ApiQrKeyHttpCode             = $apiQrKeyCode
    ApiProbeError                = $apiError
    AutoStartBundledApi          = [bool]$AutoStartBundledApi
    Port3000OwnerPidBefore       = $port3000Before
    Port3000OwnerPidAfter        = $port3000After
}
$result | Format-List

$passed = (
    (-not $initialConfigExists) -and
    $configExists -and
    $configCookieEmpty -and
    ($apiLoginStatusCode -eq 200) -and
    ($apiQrKeyCode -eq 200)
)

if ($passed) {
    Write-Host "PASS: 无环境冒烟测试通过。" -ForegroundColor Green
    exit 0
}

Write-Host "FAIL: 无环境冒烟测试未通过，请根据上面字段定位问题。" -ForegroundColor Red
if ($port3000After) {
    Write-Host "提示: 3000 端口当前被 PID=$port3000After 占用，请先释放后重试。" -ForegroundColor Yellow
}
exit 1
