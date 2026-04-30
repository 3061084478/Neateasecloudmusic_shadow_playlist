param(
    [string]$ZipPath = "C:\Users\ASUS\Desktop\网易云\Shadow-V5-Share.zip",
    [string]$WorkRoot = "C:\Users\ASUS\Desktop\网易云\_vacuum_qr_test",
    [int]$ApiWaitSeconds = 25,
    [int]$ScanTimeoutSeconds = 300,
    [bool]$KeepAppOpen = $true,
    [bool]$StopApiOnExit = $false,
    [switch]$KillPort3000Owner
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$text) {
    Write-Host "==> $text" -ForegroundColor Cyan
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

function Get-HttpCode([string]$url, [int]$timeoutSec = 3) {
    try {
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec $timeoutSec -UseBasicParsing
        return [int]$resp.StatusCode
    } catch {
        return -1
    }
}

if (!(Test-Path -LiteralPath $ZipPath)) {
    throw "ZIP 不存在: $ZipPath"
}

Write-Step "准备真空目录并解压"
if (Test-Path -LiteralPath $WorkRoot) {
    Remove-Item -Recurse -Force -LiteralPath $WorkRoot
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

$extractDir = Join-Path $WorkRoot "Shadow-V5-Share"
Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractDir -Force

$appDir = $extractDir
$exePath = Join-Path $appDir "Shadow.exe"
$configPath = Join-Path $appDir "config.json"
$apiRuntimeDir = Join-Path $appDir "_internal\runtime\NeteaseCloudMusicApi"
$apiStartBat = Join-Path $apiRuntimeDir "start_api.bat"

if (!(Test-Path -LiteralPath $exePath)) { throw "未找到 Shadow.exe: $exePath" }
if (!(Test-Path -LiteralPath $apiStartBat)) { throw "未找到内置 API 启动脚本: $apiStartBat" }

Write-Step "记录当前 node 进程基线"
$beforeNode = @{}
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $beforeNode[$_.ProcessId] = $_.CommandLine
}

$portOwnerBefore = Get-PortOwnerPid -port 3000
if ($portOwnerBefore -and $KillPort3000Owner) {
    Write-Step "检测到 3000 端口占用，尝试结束 PID=$portOwnerBefore"
    try { Stop-Process -Id $portOwnerBefore -Force -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Seconds 1
    $portOwnerBefore = Get-PortOwnerPid -port 3000
}

if ($portOwnerBefore) {
    throw "3000 端口被 PID=$portOwnerBefore 占用。请先释放端口，或加参数 -KillPort3000Owner 后重试。"
}

Write-Step "启动内置 API 并等待就绪"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$apiStartBat`"" -WorkingDirectory $apiRuntimeDir | Out-Null
$deadlineApi = (Get-Date).AddSeconds($ApiWaitSeconds)
$apiReady = $false
do {
    $statusCode = Get-HttpCode -url "http://127.0.0.1:3000/login/status?timestamp=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())" -timeoutSec 2
    if ($statusCode -eq 200) {
        $apiReady = $true
        break
    }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadlineApi)

if (-not $apiReady) {
    throw "内置 API 未在 $ApiWaitSeconds 秒内就绪，请检查 runtime 包。"
}

Write-Step "启动 Shadow 主程序"
$appProcess = Start-Process -FilePath $exePath -WorkingDirectory $appDir -PassThru

Write-Host ""
Write-Host "请现在在应用里完成二维码扫码登录（超时 $ScanTimeoutSeconds 秒）..." -ForegroundColor Yellow

$cookieCaptured = $false
$cookieLen = 0
$cookieValue = ""
$deadlineScan = (Get-Date).AddSeconds($ScanTimeoutSeconds)
do {
    if (Test-Path -LiteralPath $configPath) {
        try {
            $cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
            $cookieValue = [string]$cfg.cookie
            if (-not [string]::IsNullOrWhiteSpace($cookieValue)) {
                $cookieCaptured = $true
                $cookieLen = $cookieValue.Length
                break
            }
        } catch {}
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadlineScan)

$loginValidated = $false
$loginNickname = ""
$loginUid = ""
$loginProbeError = $null

if ($cookieCaptured) {
    try {
        $url = "http://127.0.0.1:3000/login/status?timestamp=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())&cookie=$([uri]::EscapeDataString($cookieValue))"
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
        $json = $resp.Content | ConvertFrom-Json
        $apiCode = [int]($json.code)
        $dataCode = [int]($json.data.code)
        $profile = $json.data.profile
        $account = $json.data.account
        $loginValidated = (($apiCode -eq 200 -or $dataCode -eq 200) -and $null -ne $profile -and -not [bool]$account.anonimousUser)
        if ($null -ne $profile) {
            $loginNickname = [string]$profile.nickname
            $loginUid = [string]$profile.userId
        }
    } catch {
        $loginProbeError = $_.Exception.Message
    }
}

$result = [PSCustomObject]@{
    ZipPath                  = $ZipPath
    ExtractDir               = $extractDir
    ConfigPath               = $configPath
    CookieCaptured           = $cookieCaptured
    CookieLength             = $cookieLen
    LoginValidated           = $loginValidated
    LoginNickname            = $loginNickname
    LoginUid                 = $loginUid
    LoginProbeError          = $loginProbeError
    AppRunning               = [bool](Get-Process -Id $appProcess.Id -ErrorAction SilentlyContinue)
    Port3000OwnerPidAfter    = (Get-PortOwnerPid -port 3000)
}

Write-Host ""
Write-Host "========== Vacuum QR Manual Test Result ==========" -ForegroundColor Yellow
$result | Format-List

$pass = ($cookieCaptured -and $loginValidated)
if ($pass) {
    Write-Host "PASS: 扫码登录链路可用，已拿到 cookie 并验证登录有效。" -ForegroundColor Green
} else {
    Write-Host "FAIL: 未在时限内完成扫码或 cookie/登录状态校验未通过。" -ForegroundColor Red
}

if (-not $KeepAppOpen) {
    if (Get-Process -Id $appProcess.Id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $appProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

if ($StopApiOnExit) {
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | Where-Object {
        -not $beforeNode.ContainsKey($_.ProcessId) -and $_.CommandLine -like "*_vacuum_qr_test*"
    } | ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }
}

if ($pass) { exit 0 } else { exit 1 }
