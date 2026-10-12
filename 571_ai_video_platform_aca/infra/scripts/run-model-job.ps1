$ErrorActionPreference = "Stop"

function Invoke-AzureJson {
    param([string[]]$Arguments)
    $result = & az @Arguments --subscription $env:SUBSCRIPTION_ID --output json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed: $($Arguments[0..1] -join ' ')" }
    return ($result | ConvertFrom-Json)
}

$apps = @(Invoke-AzureJson @("containerapp", "list", "--resource-group", $env:RESOURCE_GROUP))
$existing = $apps | Where-Object { $_.name -eq $env:COMFY_APP_NAME }
if ($existing) {
    $fqdn = $existing.properties.configuration.ingress.fqdn
    if (-not $fqdn) { throw "Existing ComfyUI app has no reachable ingress; inspect it before provisioning." }
    $queue = Invoke-RestMethod -Uri "https://$fqdn/queue" -TimeoutSec 30
    if ($null -eq $queue.queue_running -or $null -eq $queue.queue_pending) {
        throw "Cannot verify the existing ComfyUI queue."
    }
    if (@($queue.queue_running).Count -or @($queue.queue_pending).Count) {
        throw "ComfyUI has active or queued renders. Run provisioning between jobs only."
    }
}

$execution = Invoke-AzureJson @("containerapp", "job", "start", "--name", $env:JOB_NAME, "--resource-group", $env:RESOURCE_GROUP)
if (-not $execution.name) { throw "Job start did not return an execution name." }
$deadline = [DateTime]::UtcNow.AddSeconds([int]$env:TIMEOUT_SECONDS)
do {
    $result = Invoke-AzureJson @("containerapp", "job", "execution", "show", "--name", $env:JOB_NAME, "--resource-group", $env:RESOURCE_GROUP, "--job-execution-name", $execution.name)
    $status = $result.properties.status
    if ($status -eq "Succeeded") {
        Write-Host "Model provisioning execution $($execution.name) succeeded."
        exit 0
    }
    if ($status -in @("Failed", "Stopped", "Degraded", "Canceled")) {
        throw "Model provisioning execution $($execution.name) ended with status $status. Inspect job logs."
    }
    if ($status -notin @("Running", "Processing", "Pending", "Unknown")) {
        throw "Unexpected model execution status '$status'; refusing to report success."
    }
    Start-Sleep -Seconds 15
} while ([DateTime]::UtcNow -lt $deadline)
throw "Timed out waiting for model execution $($execution.name). Inspect or stop that execution before retrying."
