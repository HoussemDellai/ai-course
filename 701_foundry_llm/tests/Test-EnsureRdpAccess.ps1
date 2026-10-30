$ErrorActionPreference = 'Stop'
$subscription = '2524a5e1-00d7-43c2-a7cf-a87b79df2415'
$nsgNames = @{
    'rg-vm-copilot' = @('vm-copilot-nsg', 'subnet-copilot-nsg')
    'rg-vm-emulator' = @('vm-emulator-nsg', 'subnet-emulator-nsg')
}
$resourceGroups = @('rg-vm-copilot', 'rg-vm-emulator')
$ids = @(foreach ($rg in $resourceGroups) {
    foreach ($name in $nsgNames[$rg]) {
        "/subscriptions/$subscription/resourceGroups/$rg/providers/Microsoft.Network/networkSecurityGroups/$name"
    }
})
$script:testRules = @{}
$script:writes = 0
$script:reads = @()
$script:connections = 0
$script:denyTarget = ''
$script:invalidRead = $false
$script:badVerification = $false
$script:missingNsg = ''

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
    if ($DefaultProfile -ne 'test-context' -or $Path -notmatch '\?api-version=2024-05-01') {
        throw 'Unexpected REST context or API version.'
    }
    $resourcePath = ($Path -split '\?')[0]
    $nsgId = ($resourcePath -split '/securityRules/')[0]
    if ($nsgId -notin $ids) { throw 'Unexpected NSG target.' }
    if ($Method -eq 'GET') {
        $script:reads += $nsgId
        if ($nsgId -eq $script:missingNsg) {
            return [pscustomobject]@{ StatusCode = 404; Content = '{"error":"NotFound"}' }
        }
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
$originalGroups = $env:RDP_RESOURCE_GROUPS
$run = Join-Path $PSScriptRoot '..\functions\foundry-local-auth\EnsureRdpAccess\run.ps1'
function New-NsgEvent {
    param([string]$Subject, [string]$Type = 'Microsoft.Resources.ResourceWriteSuccess')
    @{ subject = $Subject; eventType = $Type; data = @{} }
}
function Invoke-Run {
    param($EventData)
    . $run -eventGridEvent $EventData
}

try {
    $env:AZURE_CLIENT_ID = 'test-identity'
    $env:RDP_RESOURCE_GROUPS = ConvertTo-Json -InputObject $resourceGroups -Compress
    foreach ($id in $ids) { $script:testRules[$id] = @() }
    $nsgEvent = New-NsgEvent $ids[0]

    Invoke-Run $nsgEvent
    if ($script:writes -ne 1 -or $script:reads.Count -lt 1 -or $script:reads.Where({ $_ -ne $ids[0] }).Count -ne 0) {
        throw 'Must create the rule only in the NSG named by the event.'
    }
    if ($script:testRules[$ids[1]].Count -ne 0) { throw 'Other NSGs must not be touched.' }
    Invoke-Run $nsgEvent
    if ($script:writes -ne 1) { throw 'Existing rules must cause zero writes.' }

    # Rule-level events and a differently cased resource group resolve to the parent NSG.
    $ruleEvent = New-NsgEvent "$($ids[2].Replace('/resourceGroups/', '/resourcegroups/'))/securityRules/Allow-RDP-Any"
    Invoke-Run $ruleEvent
    if ($script:writes -ne 2 -or $script:testRules[$ids[2]].Count -ne 1) {
        throw 'A security rule event must maintain the parent NSG.'
    }

    # Deleting the managed rule recreates it.
    $script:testRules[$ids[2]] = @()
    Invoke-Run (New-NsgEvent "$($ids[2])/securityRules/Allow-RDP-Any" 'Microsoft.Resources.ResourceDeleteSuccess')
    if ($script:writes -ne 3 -or $script:testRules[$ids[2]].Count -ne 1) {
        throw 'A rule delete event must recreate the rule.'
    }

    $script:testRules[$ids[0]][0].name = 'Existing-RDP'
    Invoke-Run $nsgEvent
    if ($script:writes -ne 3) { throw 'Equivalent differently named rule must be a no-op.' }

    $script:testRules[$ids[0]][0].name = 'Allow-RDP-Any'
    $script:testRules[$ids[0]][0].properties.access = 'Deny'
    Assert-Throws { Invoke-Run $nsgEvent } '*conflicting settings*'
    if ($script:writes -ne 3) { throw 'Conflicting named rule must not be overwritten.' }

    $script:testRules[$ids[0]][0].name = 'Existing-Deny'
    Assert-Throws { Invoke-Run $nsgEvent } '*priority 100 is occupied*'
    if ($script:writes -ne 3) { throw 'Conflicting inbound priority must not be changed.' }

    $script:testRules[$ids[0]][0].properties.direction = 'Outbound'
    Invoke-Run $nsgEvent
    if ($script:writes -ne 4 -or $script:testRules[$ids[0]].Count -ne 2) {
        throw 'Must preserve unrelated outbound rules, including the same priority.'
    }

    $script:testRules[$ids[1]] = @()
    $script:denyTarget = $ids[1]
    Assert-Throws { Invoke-Run (New-NsgEvent $ids[1]) } '*RequestDisallowedByPolicy*'
    $script:denyTarget = ''

    $script:testRules[$ids[3]] = @()
    $script:badVerification = $true
    Assert-Throws { Invoke-Run (New-NsgEvent $ids[3]) } '*could not be verified*'
    $script:badVerification = $false
    $script:invalidRead = $true
    Assert-Throws { Invoke-Run $nsgEvent } '*NSG read failed*'
    $script:invalidRead = $false

    $before = $script:writes
    $script:missingNsg = $ids[0]
    Invoke-Run (New-NsgEvent $ids[0] 'Microsoft.Resources.ResourceDeleteSuccess') 3>$null
    $script:missingNsg = ''
    if ($script:writes -ne $before) { throw 'A deleted NSG must be skipped without error.' }

    # Events that must be ignored before any authentication or API call.
    $connectionsBefore = $script:connections
    $readsBefore = $script:reads.Count
    $ignored = @(
        (New-NsgEvent "/subscriptions/$subscription/resourceGroups/rg-other/providers/Microsoft.Network/networkSecurityGroups/x"),
        (New-NsgEvent "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-vm-copilot/providers/Microsoft.Network/networkSecurityGroups/x"),
        (New-NsgEvent "/subscriptions/$subscription/resourceGroups/rg-vm-copilot/providers/Microsoft.Compute/virtualMachines/vm"),
        (New-NsgEvent "/subscriptions/$subscription/resourceGroups/rg-vm-copilot/providers/Microsoft.Network/networkSecurityGroups/x/securityRules/a/b"),
        (New-NsgEvent $ids[0] 'Microsoft.Resources.ResourceActionSuccess'),
        @{ eventType = 'Microsoft.Resources.ResourceWriteSuccess' }
    )
    foreach ($ignoredEvent in $ignored) { Invoke-Run $ignoredEvent 3>$null }
    if ($script:connections -ne $connectionsBefore -or $script:reads.Count -ne $readsBefore -or $script:writes -ne $before) {
        throw 'Unrelated events must be ignored without connecting or calling the API.'
    }

    $env:RDP_RESOURCE_GROUPS = '["rg-vm-copilot","rg-vm-copilot"]'
    Assert-Throws { Invoke-Run $nsgEvent } '*duplicate*'
    $env:RDP_RESOURCE_GROUPS = '["rg-vm-copilot","../other"]'
    Assert-Throws { Invoke-Run $nsgEvent } '*Invalid resource group*'
    $env:RDP_RESOURCE_GROUPS = '[]'
    Assert-Throws { Invoke-Run $nsgEvent } '*at least one*'
    $env:RDP_RESOURCE_GROUPS = ''
    Assert-Throws { Invoke-Run $nsgEvent } '*RDP_RESOURCE_GROUPS*missing*'
    if ($script:connections -ne $connectionsBefore) { throw 'Invalid targets must fail before connecting.' }

    $config = Get-Content (Join-Path $PSScriptRoot '..\rdp-resource-groups.json') -Raw | ConvertFrom-Json
    if ('rg-vm-copilot' -notin $config.resourceGroups -or 'rg-vm-emulator' -notin $config.resourceGroups) {
        throw 'rdp-resource-groups.json must list rg-vm-copilot and rg-vm-emulator.'
    }
    $binding = Get-Content (Join-Path (Split-Path $run) 'function.json') -Raw | ConvertFrom-Json
    if ($binding.bindings.Count -ne 1 -or $binding.bindings[0].type -ne 'eventGridTrigger' -or
        $binding.bindings[0].name -ne 'eventGridEvent' -or $binding.bindings[0].direction -ne 'in') {
        throw 'Invalid RDP Event Grid trigger binding.'
    }
    $terraform = Get-Content (Join-Path $PSScriptRoot '..\function_governance.tf') -Raw
    if ($terraform -match 'RDP_TIMER_SCHEDULE') { throw 'The RDP timer schedule must be removed.' }
    foreach ($pattern in @(
            'topic_type\s*=\s*"Microsoft\.Resources\.Subscriptions"',
            '/functions/EnsureRdpAccess',
            'Microsoft\.Resources\.ResourceWriteSuccess',
            'Microsoft\.Resources\.ResourceDeleteSuccess',
            'networkSecurityGroups/"',
            'depends_on\s*=\s*\[terraform_data\.governance_package_deploy\]')) {
        if ($terraform -notmatch $pattern) { throw "function_governance.tf is missing the Event Grid wiring: $pattern" }
    }
    Write-Host 'PASS: single-NSG processing, rule events, delete recreation, no-op, equivalent rule, conflicts, preservation, failures, verification, read failure, deleted NSG, ignored events, input validation, config file, and Event Grid wiring.'
}
finally {
    $env:AZURE_CLIENT_ID = $originalIdentity
    $env:RDP_RESOURCE_GROUPS = $originalGroups
}
