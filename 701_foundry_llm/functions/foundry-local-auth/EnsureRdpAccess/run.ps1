param($Timer)

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

if ($Timer.IsPastDue) {
    Write-Warning 'The RDP maintenance timer is past due.'
}

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

function Get-NsgIds {
    param([string]$ResourceGroup)

    $discovered = @()
    $path = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Network/networkSecurityGroups?api-version=$apiVersion"
    while ($path) {
        $response = Invoke-AzRestMethod @restParameters -Method GET -Path $path
        if ($response.StatusCode -ne 200) {
            throw "NSG list failed (HTTP $($response.StatusCode)): $($response.Content)"
        }
        $page = $response.Content | ConvertFrom-Json -ErrorAction Stop
        $discovered += @($page.value | ForEach-Object { $_.id })
        $path = $null
        if ($page.nextLink) {
            $path = ([uri]$page.nextLink).PathAndQuery
        }
    }
    return $discovered
}

$failures = @()
$nsgIds = @()
foreach ($resourceGroup in $resourceGroups) {
    try {
        $found = @(Get-NsgIds $resourceGroup)
        if ($found.Count -eq 0) {
            Write-Warning "No NSGs found in resource group '$resourceGroup'."
        }
        $nsgIds += $found
    }
    catch {
        $failures += "${resourceGroup}: $($_.Exception.Message)"
        Write-Error "NSG discovery failed for resource group '${resourceGroup}': $($_.Exception.Message)" -ErrorAction Continue
    }
}

foreach ($nsgId in $nsgIds) {
    try {
        $response = Invoke-AzRestMethod @restParameters -Method GET -Path "${nsgId}?api-version=$apiVersion"
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
            throw "Existing '$ruleName' has conflicting settings; it was not overwritten."
        }
        $matchingRules = @($rules | Where-Object { Test-RdpRule $_.properties })
        if ($matchingRules.Count -gt 0) {
            Write-Host "RDP from Any IP is already allowed by '$($matchingRules[0].name)' on '$nsgId'; no changes."
            continue
        }
        if ($rules | Where-Object { $_.properties.direction -eq 'Inbound' -and $_.properties.priority -eq 100 }) {
            throw "Inbound priority 100 is occupied on '$nsgId'; existing rules were not changed."
        }

        $payload = @{
            properties = @{
                description = 'Allow RDP from Any IP; maintained by EnsureRdpAccess every five minutes.'
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
    }
    catch {
        $failures += "${nsgId}: $($_.Exception.Message)"
        Write-Error "RDP rule maintenance failed for '${nsgId}': $($_.Exception.Message)" -ErrorAction Continue
    }
}
if ($failures.Count -gt 0) {
    throw "RDP maintenance failed for $($failures.Count) target(s): $($failures -join '; ')"
}
