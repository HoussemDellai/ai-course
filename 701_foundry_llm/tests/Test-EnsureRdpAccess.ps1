$ErrorActionPreference = 'Stop'
$prefix = '/subscriptions/2524a5e1-00d7-43c2-a7cf-a87b79df2415/resourceGroups/rg-vm-copilot/providers/Microsoft.Network/networkSecurityGroups/'
$ids = @("${prefix}vm-copilot-nsg", "${prefix}vnet-francecentral-1-snet-francecentral-1-nsg-francecentral")
$script:testRules = @{}
$script:writes = 0
$script:reads = @()
$script:connections = 0
$script:denyTarget = ''
$script:invalidRead = $false
$script:badVerification = $false

function Connect-AzAccount {
    param([switch]$Identity, $AccountId, $Subscription, $ErrorAction)
    if (-not $Identity -or $AccountId -ne 'test-identity' -or
        $Subscription -ne '2524a5e1-00d7-43c2-a7cf-a87b79df2415') {
        throw 'Unexpected identity or subscription.'
    }
    $script:connections++
    [pscustomobject]@{ Context = 'test-context' }
}

function Invoke-AzRestMethod {
    param($DefaultProfile, $ErrorAction, $Method, $Path, $Payload, [switch]$WaitForCompletion)
    if ($DefaultProfile -ne 'test-context' -or $Path -notmatch '\?api-version=2024-05-01$') {
        throw 'Unexpected REST context or API version.'
    }
    $resourcePath = ($Path -split '\?')[0]
    $nsgId = ($resourcePath -split '/securityRules/')[0]
    if ($nsgId -notin $ids) { throw 'Unexpected NSG target.' }
    if ($Method -eq 'GET') {
        $script:reads += $nsgId
        if ($script:invalidRead) {
            return [pscustomobject]@{ StatusCode = 403; Content = '{"error":"Read denied"}' }
        }
        if ($resourcePath -match '/securityRules/') {
            $rule = $script:testRules[$nsgId] | Where-Object name -EQ 'Allow-RDP-Any'
            if ($script:badVerification) { $rule.properties.provisioningState = 'Failed' }
            return [pscustomobject]@{ StatusCode = 200; Content = ($rule | ConvertTo-Json -Depth 8) }
        }
        return [pscustomobject]@{
            StatusCode = 200
            Content = (@{properties = @{securityRules = @($script:testRules[$nsgId])}} | ConvertTo-Json -Depth 8)
        }
    }
    if ($Method -ne 'PUT' -or -not $WaitForCompletion -or
        $resourcePath -ne "$nsgId/securityRules/Allow-RDP-Any") {
        throw 'Must write only the designated child rule and await completion.'
    }
    if ($nsgId -eq $script:denyTarget) {
        return [pscustomobject]@{ StatusCode = 403; Content = '{"error":"RequestDisallowedByPolicy"}' }
    }
    $rule = $Payload | ConvertFrom-Json
    $p = $rule.properties
    if ($p.protocol -ne 'Tcp' -or $p.sourceAddressPrefix -ne '*' -or
        $p.destinationAddressPrefix -ne '*' -or $p.sourcePortRange -ne '*' -or
        $p.destinationPortRange -ne '3389' -or $p.access -ne 'Allow' -or
        $p.direction -ne 'Inbound' -or $p.priority -ne 100) {
        throw 'Unexpected rule payload.'
    }
    $rule | Add-Member -NotePropertyName name -NotePropertyValue 'Allow-RDP-Any'
    $p | Add-Member -NotePropertyName provisioningState -NotePropertyValue 'Succeeded'
    $script:testRules[$nsgId] = @($script:testRules[$nsgId]) + @($rule)
    $script:writes++
    [pscustomobject]@{ StatusCode = 201; Content = '{}' }
}

function Assert-Throws {
    param([scriptblock]$Action, [string]$Message)
    try { & $Action }
    catch {
        if ($_.Exception.Message -notlike $Message) { throw }
        return
    }
    throw "Expected error: $Message"
}

$originalIdentity = $env:AZURE_CLIENT_ID
$originalIds = $env:RDP_NSG_IDS
$run = Join-Path $PSScriptRoot '..\functions\foundry-local-auth\EnsureRdpAccess\run.ps1'
$timer = [pscustomobject]@{ IsPastDue = $false }
try {
    $env:AZURE_CLIENT_ID = 'test-identity'
    $env:RDP_NSG_IDS = ConvertTo-Json -InputObject $ids -Compress
    foreach ($id in $ids) { $script:testRules[$id] = @() }

    . $run -Timer $timer
    if ($script:writes -ne 2) { throw 'Must create a rule in each NSG.' }
    . $run -Timer $timer
    if ($script:writes -ne 2) { throw 'Existing rules must cause zero writes.' }

    $script:testRules[$ids[0]][0].name = 'Existing-RDP'
    . $run -Timer $timer
    if ($script:writes -ne 2) { throw 'Equivalent differently named rule must be a no-op.' }

    $script:testRules[$ids[0]][0].name = 'Allow-RDP-Any'
    $script:testRules[$ids[0]][0].properties.access = 'Deny'
    Assert-Throws { . $run -Timer $timer 2>$null } '*conflicting settings*'
    if ($script:writes -ne 2) { throw 'Conflicting named rule must not be overwritten.' }

    $script:testRules[$ids[0]][0].name = 'Existing-Deny'
    Assert-Throws { . $run -Timer $timer 2>$null } '*priority 100 is occupied*'
    if ($script:writes -ne 2) { throw 'Conflicting inbound priority must not be changed.' }

    $script:testRules[$ids[0]][0].properties.direction = 'Outbound'
    . $run -Timer $timer
    if ($script:writes -ne 3 -or $script:testRules[$ids[0]].Count -ne 2) {
        throw 'Must preserve unrelated outbound rules, including the same priority.'
    }

    foreach ($id in $ids) { $script:testRules[$id] = @() }
    $script:denyTarget = $ids[0]
    $script:reads = @()
    Assert-Throws { . $run -Timer $timer 2>$null } '*RequestDisallowedByPolicy*'
    if ($script:writes -ne 4 -or $ids[1] -notin $script:reads) {
        throw 'Second NSG must be processed even if the first is denied.'
    }

    $script:denyTarget = ''
    $script:badVerification = $true
    Assert-Throws { . $run -Timer $timer 2>$null } '*could not be verified*'
    $script:badVerification = $false
    $script:invalidRead = $true
    Assert-Throws { . $run -Timer $timer 2>$null } '*NSG read failed*'
    $script:invalidRead = $false

    $connections = $script:connections
    $env:RDP_NSG_IDS = ConvertTo-Json -InputObject @($ids[0], $ids[0]) -Compress
    Assert-Throws { . $run -Timer $timer } '*two distinct*'
    $env:RDP_NSG_IDS = ConvertTo-Json -InputObject @($ids[0], "${prefix}unapproved") -Compress
    Assert-Throws { . $run -Timer $timer } '*Unapproved NSG*'
    $env:RDP_NSG_IDS = ''
    Assert-Throws { . $run -Timer $timer } '*RDP_NSG_IDS*missing*'
    if ($script:connections -ne $connections) { throw 'Invalid targets must fail before connecting.' }

    $binding = Get-Content (Join-Path (Split-Path $run) 'function.json') -Raw | ConvertFrom-Json
    if ($binding.bindings[0].schedule -ne '%RDP_TIMER_SCHEDULE%' -or
        $binding.bindings[0].runOnStartup -or -not $binding.bindings[0].useMonitor) {
        throw 'Invalid RDP timer binding.'
    }
    $terraform = Get-Content (Join-Path $PSScriptRoot '..\function_governance.tf') -Raw
    if ($terraform -notmatch '"RDP_TIMER_SCHEDULE"\s*=\s*"0 \*/5 \* \* \* \*"') {
        throw 'RDP schedule must run every five minutes.'
    }
    Write-Host 'PASS: create both, no-op, equivalent rule, conflicts, preservation, partial failure, verification, read failure, target validation, and timer.'
}
finally {
    $env:AZURE_CLIENT_ID = $originalIdentity
    $env:RDP_NSG_IDS = $originalIds
}
