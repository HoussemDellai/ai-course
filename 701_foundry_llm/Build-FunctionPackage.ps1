$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot 'functions\foundry-local-auth'
$staging = Join-Path $PSScriptRoot '.terraform\foundry-local-auth-package'
$archive = Join-Path $PSScriptRoot '.terraform\foundry-local-auth.zip'
$requirements = Import-PowerShellDataFile (Join-Path $source 'requirements.psd1')

foreach ($name in $requirements.Keys) {
    if (-not (Get-Module -ListAvailable $name | Where-Object Version -EQ $requirements[$name])) {
        throw "Missing module $name $($requirements[$name]). Install it with: Install-Module $name -RequiredVersion $($requirements[$name]) -Scope CurrentUser"
    }
}

if (Test-Path $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $staging -Recurse
$modules = New-Item -ItemType Directory -Path (Join-Path $staging 'Modules') -Force

foreach ($name in $requirements.Keys) {
    $module = Get-Module -ListAvailable $name |
        Where-Object Version -EQ $requirements[$name] |
        Select-Object -First 1
    $destination = New-Item -ItemType Directory -Path (Join-Path $modules.FullName $name) -Force
    Copy-Item -LiteralPath $module.ModuleBase -Destination $destination.FullName -Recurse
}

if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory($staging, $archive)
Write-Host "Function package: $archive"
