param($Timer)

$ErrorActionPreference = 'Stop'

foreach ($setting in 'AZURE_CLIENT_ID', 'FOUNDRY_SUBSCRIPTION_ID', 'FOUNDRY_RESOURCE_GROUP', 'FOUNDRY_ACCOUNT_NAME') {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($setting))) {
        throw "Required app setting '$setting' is missing."
    }
}

if ($Timer.IsPastDue) {
    Write-Warning 'The local authentication maintenance timer is past due.'
}

$context = (Connect-AzAccount -Identity -AccountId $env:AZURE_CLIENT_ID `
    -Subscription $env:FOUNDRY_SUBSCRIPTION_ID -ErrorAction Stop).Context

$accountParameters = @{
    ResourceGroupName = $env:FOUNDRY_RESOURCE_GROUP
    Name = $env:FOUNDRY_ACCOUNT_NAME
    DefaultProfile = $context
    ErrorAction = 'Stop'
}

$account = Get-AzCognitiveServicesAccount @accountParameters
if ($null -eq $account -or $account.DisableLocalAuth -isnot [bool]) {
    throw "Foundry account '$env:FOUNDRY_ACCOUNT_NAME' did not return a valid DisableLocalAuth setting."
}

if (-not $account.DisableLocalAuth) {
    Write-Host "Local authentication is already enabled for '$env:FOUNDRY_ACCOUNT_NAME'."
    return
}

Set-AzCognitiveServicesAccount @accountParameters -DisableLocalAuth $false | Out-Null

$account = Get-AzCognitiveServicesAccount @accountParameters
if ($null -eq $account -or $account.DisableLocalAuth -isnot [bool] -or $account.DisableLocalAuth) {
    throw "Local authentication could not be verified as enabled for '$env:FOUNDRY_ACCOUNT_NAME'. Check Azure Policy and the activity log."
}

Write-Host "Local authentication was re-enabled for '$env:FOUNDRY_ACCOUNT_NAME'."
