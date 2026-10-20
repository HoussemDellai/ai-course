$ErrorActionPreference = 'Stop'
$script:updates = 0
$script:disabled = $false
$script:denyUpdate = $false
$script:ignoreUpdate = $false
$script:invalidResponse = $false
$script:connections = 0

function Connect-AzAccount {
    param([switch]$Identity, $AccountId, $Subscription, $ErrorAction)
    $script:connections++
    [pscustomobject]@{ Context = 'test-context' }
}

function Get-AzCognitiveServicesAccount {
    param($ResourceGroupName, $Name, $DefaultProfile, $ErrorAction)
    if ($Name -ne 'foundry-701' -or $ResourceGroupName -ne 'rg-foundry-701' -or $DefaultProfile -ne 'test-context') {
        throw 'Unexpected target or Azure context.'
    }
    if ($script:invalidResponse) {
        return [pscustomobject]@{}
    }
    [pscustomobject]@{ DisableLocalAuth = $script:disabled }
}

function Set-AzCognitiveServicesAccount {
    param($ResourceGroupName, $Name, $DefaultProfile, [bool]$DisableLocalAuth, $ErrorAction)
    if ($script:denyUpdate) {
        throw 'RequestDisallowedByPolicy'
    }
    if ($DisableLocalAuth -or $Name -ne 'foundry-701' -or $DefaultProfile -ne 'test-context') {
        throw 'Unexpected update.'
    }
    $script:updates++
    if (-not $script:ignoreUpdate) {
        $script:disabled = $DisableLocalAuth
    }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$Message)
    try {
        & $Action
    }
    catch {
        if ($_.Exception.Message -notlike $Message) { throw }
        return
    }
    throw "Expected error: $Message"
}

$settings = @{
    AZURE_CLIENT_ID = 'test-identity'
    FOUNDRY_SUBSCRIPTION_ID = 'test-subscription'
    FOUNDRY_RESOURCE_GROUP = 'rg-foundry-701'
    FOUNDRY_ACCOUNT_NAME = 'foundry-701'
}
$original = @{}
$run = Join-Path $PSScriptRoot '..\functions\foundry-local-auth\EnableLocalAuth\run.ps1'
$timer = [pscustomobject]@{ IsPastDue = $false }

try {
    foreach ($name in $settings.Keys) {
        $original[$name] = [Environment]::GetEnvironmentVariable($name)
        [Environment]::SetEnvironmentVariable($name, $settings[$name])
    }

    . $run -Timer $timer
    if ($script:updates -ne 0) { throw 'Enabled account must not be updated.' }

    $script:disabled = $true
    . $run -Timer $timer
    if ($script:updates -ne 1 -or $script:disabled) { throw 'Disabled account must be enabled exactly once.' }

    $script:disabled = $true
    $script:denyUpdate = $true
    Assert-Throws { . $run -Timer $timer } '*RequestDisallowedByPolicy*'

    $script:denyUpdate = $false
    $script:ignoreUpdate = $true
    Assert-Throws { . $run -Timer $timer } '*could not be verified*'

    $script:invalidResponse = $true
    Assert-Throws { . $run -Timer $timer } '*valid DisableLocalAuth*'

    [Environment]::SetEnvironmentVariable('FOUNDRY_ACCOUNT_NAME', '')
    $connections = $script:connections
    Assert-Throws { . $run -Timer $timer } "*FOUNDRY_ACCOUNT_NAME*missing*"
    if ($script:connections -ne $connections) { throw 'Missing configuration must fail before connecting.' }

    $binding = Get-Content (Join-Path (Split-Path $run) 'function.json') -Raw | ConvertFrom-Json
    if ($binding.bindings[0].schedule -ne '%TIMER_SCHEDULE%' -or
        $binding.bindings[0].runOnStartup -or -not $binding.bindings[0].useMonitor) {
        throw 'Invalid timer configuration.'
    }
    $terraform = Get-Content (Join-Path $PSScriptRoot '..\function_governance.tf') -Raw
    if ($terraform -notmatch '"TIMER_SCHEDULE"\s*=\s*"0 \*/5 \* \* \* \*"') {
        throw 'Schedule must run every five minutes.'
    }
    Write-Host 'PASS: no-op, enable, policy failure, verification failure, invalid response, missing configuration, and five-minute timer.'
}
finally {
    foreach ($name in $original.Keys) {
        [Environment]::SetEnvironmentVariable($name, $original[$name])
    }
}
