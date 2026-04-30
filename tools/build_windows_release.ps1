param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mainPy = Join-Path $projectRoot 'main.py'
$buildRoot = Join-Path $projectRoot 'build\pyinstaller'
$distRoot = Join-Path $projectRoot 'dist'
$releaseBuildRoot = Join-Path $projectRoot 'build\release'

if ($Clean) {
    if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
    if (Test-Path $releaseBuildRoot) { Remove-Item -Recurse -Force $releaseBuildRoot }
    if (Test-Path (Join-Path $distRoot 'Shadow')) { Remove-Item -Recurse -Force (Join-Path $distRoot 'Shadow') }
}

python -m pip install --upgrade pip
python -m pip install -r (Join-Path $projectRoot 'requirements.txt')
python -m pip install pyinstaller

$addAssets = '{0};assets' -f (Join-Path $projectRoot 'assets')
$addTemplate = '{0};.' -f (Join-Path $projectRoot 'config.template.json')

$args = @(
    '--noconfirm',
    '--windowed',
    '--name', 'Shadow',
    '--distpath', $distRoot,
    '--workpath', $buildRoot,
    '--specpath', $buildRoot,
    '--add-data', $addAssets,
    '--add-data', $addTemplate,
    '--hidden-import', 'qrcode',
    '--hidden-import', 'PIL',
    $mainPy
)

$runtimeDir = Join-Path $projectRoot 'runtime'
if (Test-Path $runtimeDir) {
    $args += @('--add-data', ('{0};runtime' -f $runtimeDir))
}

$uxSkillDir = Join-Path $projectRoot 'ui-ux-pro-max-skill-main'
if (Test-Path $uxSkillDir) {
    $args += @('--add-data', ('{0};ui-ux-pro-max-skill-main' -f $uxSkillDir))
}

python -m PyInstaller @args

Write-Host ''
Write-Host 'Build completed:' -ForegroundColor Green
Write-Host (Join-Path (Join-Path $distRoot 'Shadow') 'Shadow.exe')
