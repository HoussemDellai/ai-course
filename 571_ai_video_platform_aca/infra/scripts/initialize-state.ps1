$ErrorActionPreference = "Stop"
$infra = Split-Path -Parent $PSScriptRoot
$copiedState = Join-Path $infra "terraform.tfstate"
if (Test-Path -LiteralPath $copiedState) {
    $archive = Join-Path $infra "inherited-state"
    $destination = Join-Path $archive "copied-terraform.tfstate"
    if (Test-Path -LiteralPath $destination) { throw "State archive already exists; inspect both state files before continuing." }
    New-Item -ItemType Directory -Path $archive -Force | Out-Null
    Move-Item -LiteralPath $copiedState -Destination $destination
    Write-Host "Preserved copied state in inherited-state; it will not be migrated."
}
& terraform "-chdir=$infra" init -reconfigure -input=false -lockfile=readonly
if ($LASTEXITCODE -ne 0) { throw "Terraform backend initialization failed." }
