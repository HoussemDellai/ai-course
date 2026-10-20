param(
    [string]$Tag = (Get-Date -Format "yyyyMMddHHmmss")
)
$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot)
try {
    $subscription = terraform output -raw subscription_id
    if ($LASTEXITCODE -ne 0) { throw "Cannot read Terraform subscription output" }
    $registry = terraform output -raw acr_name
    if ($LASTEXITCODE -ne 0) { throw "Cannot read Terraform registry output" }
    $server = terraform output -raw acr_login_server
    if ($LASTEXITCODE -ne 0) { throw "Cannot read Terraform registry server output" }
    az acr build --subscription $subscription --registry $registry --image "comfy-mcp:$Tag" --platform linux/amd64 .\mcp --no-logs
    if ($LASTEXITCODE -ne 0) { throw "ACR image build failed" }
    $digest = az acr repository show --subscription $subscription --name $registry --image "comfy-mcp:$Tag" --query digest -o tsv
    if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^sha256:[a-f0-9]{64}$') {
        throw "Cannot resolve the built image digest"
    }
    Write-Output "$server/comfy-mcp@$digest"
} finally {
    Pop-Location
}
