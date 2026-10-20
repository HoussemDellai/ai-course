$ErrorActionPreference = "Stop"

function Invoke-AzureJson {
    param([string[]]$Arguments)
    $result = & az @Arguments --subscription $env:SUBSCRIPTION_ID --output json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed: $($Arguments[0..1] -join ' ')" }
    return ($result | ConvertFrom-Json)
}

function Wait-ModelExecution {
    param([string]$Name)
    $deadline = [DateTime]::UtcNow.AddSeconds([int]$env:TIMEOUT_SECONDS)
    do {
        $result = Invoke-AzureJson @("containerapp", "job", "execution", "show", "--name", $env:JOB_NAME, "--resource-group", $env:RESOURCE_GROUP, "--job-execution-name", $Name)
        $status = $result.properties.status
        if ($status -eq "Succeeded") {
            Write-Host "Model provisioning execution $Name succeeded."
            return
        }
        if ($status -in @("Failed", "Stopped", "Degraded", "Canceled")) {
            throw "Model provisioning execution $Name ended with status $status. Inspect job logs."
        }
        if ($status -notin @("Running", "Processing", "Pending", "Unknown")) {
            throw "Unexpected model execution status '$status'; refusing to report success."
        }
        Start-Sleep -Seconds 15
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for model execution $Name. Inspect or stop that execution before retrying."
}

$executions = @(Invoke-AzureJson @("containerapp", "job", "execution", "list", "--name", $env:JOB_NAME, "--resource-group", $env:RESOURCE_GROUP))
foreach ($execution in $executions) {
    if ($execution.properties.status -in @("Succeeded", "Failed", "Stopped", "Degraded", "Canceled")) { continue }
    if (-not $execution.name) { throw "Existing model execution has no name; inspect the job before retrying." }
    Write-Host "Waiting for existing model execution $($execution.name) before provisioning the requested revision."
    Wait-ModelExecution $execution.name
}

$apps = @(Invoke-AzureJson @("containerapp", "list", "--resource-group", $env:RESOURCE_GROUP))
$names = if ($env:COMFY_APP_NAMES) { $env:COMFY_APP_NAMES } else { $env:COMFY_APP_NAME }
if (-not $names) { throw "Configure COMFY_APP_NAMES before provisioning." }
$workerNames = @($names.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if (-not $workerNames.Count) { throw "COMFY_APP_NAMES must contain at least one worker name." }
foreach ($existing in @($apps | Where-Object { $_.name -in $workerNames })) {
    $fqdn = $existing.properties.configuration.ingress.fqdn
    if (-not $fqdn) { throw "Existing ComfyUI app $($existing.name) has no reachable ingress; inspect it before provisioning." }
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
Wait-ModelExecution $execution.name
