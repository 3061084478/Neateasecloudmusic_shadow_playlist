param(
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'package_portable.ps1') -Rebuild:$Rebuild
