param($eventGridEvent)

$ErrorActionPreference = 'Stop'

foreach ($setting in 'AZURE_CLIENT_ID', 'RDP_RESOURCE_GROUPS') {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($setting))) {
        throw "Required app setting '$setting' is missing."
    }
}

$subscriptionId = '2524a5e1-00d7-43c2-a7cf-a87b79df2415'
$resourceGroups = @($env:RDP_RESOURCE_GROUPS | ConvertFrom-Json -ErrorAction Stop)
if ($resourceGroups.Count -eq 0) {
    throw 'RDP_RESOURCE_GROUPS must contain at least one resource group name.'
}
foreach ($resourceGroup in $resourceGroups) {
    if ($resourceGroup -isnot [string] -or $resourceGroup -notmatch '^[-\w\.\(\)]{1,90}$') {
        throw "Invalid resource group name in RDP_RESOURCE_GROUPS: '$resourceGroup'."
    }
}
if (@($resourceGroups | Select-Object -Unique).Count -ne $resourceGroups.Count) {
    throw 'RDP_RESOURCE_GROUPS must not contain duplicate resource group names.'
}

$subject = [string]$eventGridEvent.subject
$eventType = [string]$eventGridEvent.eventType
if ($eventType -notin @('Microsoft.Resources.ResourceWriteSuccess', 'Microsoft.Resources.ResourceDeleteSuccess')) {
    Write-Warning "Ignoring unsupported event type '$eventType'."
    return
}
$subjectPattern = '^/subscriptions/(?<sub>[^/]+)/resourceGroups/(?<rg>[^/]+)/providers/Microsoft\.Network/networkSecurityGroups/(?<nsg>[^/]+)(/securityRules/[^/]+)?$'
if ($subject -notmatch $subjectPattern -or $Matches.sub -ne $subscriptionId) {
    Write-Warning "Ignoring event for unrelated resource '$subject'."
    return
}
$resourceGroup = @($resourceGroups | Where-Object { $_ -eq $Matches.rg }) | Select-Object -First 1
if (-not $resourceGroup) {
    Write-Warning "Ignoring event for resource group '$($Matches.rg)', which is not in RDP_RESOURCE_GROUPS."
    return
}
$nsgId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Network/networkSecurityGroups/$($Matches.nsg)"

$context = (Connect-AzAccount -Identity -AccountId $env:AZURE_CLIENT_ID `
    -Subscription $subscriptionId -ErrorAction Stop).Context
$restParameters = @{
    DefaultProfile = $context
    ErrorAction = 'Stop'
}
$ruleName = 'Allow-RDP-Any'
$apiVersion = '2024-05-01'

function Test-RdpRule {
    param($Properties)

    $sources = @($Properties.sourceAddressPrefix) + @($Properties.sourceAddressPrefixes)
    $destinations = @($Properties.destinationAddressPrefix) + @($Properties.destinationAddressPrefixes)
    $sourcePorts = @($Properties.sourcePortRange) + @($Properties.sourcePortRanges)
    $destinationPorts = @($Properties.destinationPortRange) + @($Properties.destinationPortRanges)
    return ($Properties.direction -eq 'Inbound' -and $Properties.access -eq 'Allow' -and
        $Properties.protocol -in @('Tcp', '*') -and
        @($sources | Where-Object { $_ -in @('*', '0.0.0.0/0') }).Count -gt 0 -and
        '*' -in $destinations -and '*' -in $sourcePorts -and
        @($destinationPorts | Where-Object { $_ -in @('3389', '*') }).Count -gt 0 -and
        @($Properties.sourceApplicationSecurityGroups | Where-Object { $null -ne $_ }).Count -eq 0 -and
        @($Properties.destinationApplicationSecurityGroups | Where-Object { $null -ne $_ }).Count -eq 0)
}

Write-Host "Processing '$eventType' event for '$subject'."
$response = Invoke-AzRestMethod @restParameters -Method GET -Path "${nsgId}?api-version=$apiVersion"
if ($response.StatusCode -eq 404) {
    Write-Warning "NSG '$nsgId' no longer exists; nothing to maintain."
    return
}
if ($response.StatusCode -ne 200) {
    throw "NSG read failed (HTTP $($response.StatusCode)): $($response.Content)"
}
$nsg = $response.Content | ConvertFrom-Json -ErrorAction Stop
if ($null -eq $nsg.properties -or $null -eq $nsg.properties.securityRules) {
    throw 'NSG response did not contain a securityRules collection.'
}
$rules = @($nsg.properties.securityRules)
$namedRule = $rules | Where-Object name -EQ $ruleName
if ($namedRule -and -not (Test-RdpRule $namedRule.properties)) {
    throw "Existing '$ruleName' has conflicting settings on '$nsgId'; it was not overwritten."
}
$matchingRules = @($rules | Where-Object { Test-RdpRule $_.properties })
if ($matchingRules.Count -gt 0) {
    Write-Host "RDP from Any IP is already allowed by '$($matchingRules[0].name)' on '$nsgId'; no changes."
    return
}
if ($rules | Where-Object { $_.properties.direction -eq 'Inbound' -and $_.properties.priority -eq 100 }) {
    throw "Inbound priority 100 is occupied on '$nsgId'; existing rules were not changed."
}

$payload = @{
    properties = @{
        description = 'Allow RDP from Any IP; maintained by EnsureRdpAccess when NSG rules change.'
        protocol = 'Tcp'
        sourcePortRange = '*'
        destinationPortRange = '3389'
        sourceAddressPrefix = '*'
        destinationAddressPrefix = '*'
        access = 'Allow'
        priority = 100
        direction = 'Inbound'
    }
} | ConvertTo-Json -Depth 4
$rulePath = "$nsgId/securityRules/${ruleName}?api-version=$apiVersion"
$response = Invoke-AzRestMethod @restParameters -Method PUT -Path $rulePath `
    -Payload $payload -WaitForCompletion
if ($response.StatusCode -notin @(200, 201)) {
    throw "Rule creation failed (HTTP $($response.StatusCode)): $($response.Content)"
}
$response = Invoke-AzRestMethod @restParameters -Method GET -Path $rulePath
if ($response.StatusCode -ne 200) {
    throw "Rule verification read failed (HTTP $($response.StatusCode)): $($response.Content)"
}
$rule = $response.Content | ConvertFrom-Json -ErrorAction Stop
if (-not (Test-RdpRule $rule.properties) -or $rule.properties.priority -ne 100 -or
    $rule.properties.provisioningState -ne 'Succeeded') {
    throw "Rule creation could not be verified on '$nsgId'."
}
Write-Host "Created and verified '$ruleName' on '$nsgId'."
