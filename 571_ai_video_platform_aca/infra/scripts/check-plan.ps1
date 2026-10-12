param(
    [Parameter(Mandatory)][string]$Plan,
    [string]$Prefix = "aivideo571",
    [string]$SubscriptionId = "25a98a18-5e94-4b21-9d17-e8cf45bfd81f"
)
$ErrorActionPreference = "Stop"
$infra = Split-Path -Parent $PSScriptRoot
$planPath = (Resolve-Path -LiteralPath $Plan).Path
$json = & terraform "-chdir=$infra" show -json $planPath
if ($LASTEXITCODE -ne 0) { throw "Cannot read saved Terraform plan." }
$data = $json | ConvertFrom-Json
$changes = @($data.resource_changes | Where-Object { $_.mode -eq "managed" })
foreach ($change in $changes) {
    $beforeId = $change.change.before.id
    if ($beforeId -and ($beforeId -match "/resourceGroups/rg-aivideo570/" -or $beforeId -match "Microsoft.Compute/virtualMachines")) {
        throw "Plan touches an inherited deployment: $($change.address)"
    }
    if ($change.type -match "virtual_machine|public_ip|network_security") { throw "Unexpected VM-related resource: $($change.address)" }
    if ("delete" -in $change.change.actions) { throw "Destructive change requires separate approval: $($change.address)" }
    $after = $change.change.after
    if ($after.resource_group_name -and $after.resource_group_name -ne "rg-$Prefix") { throw "Wrong resource group on $($change.address)" }
    foreach ($id in @($beforeId, $after.id)) {
        if ($id -match "^/subscriptions/([^/]+)/" -and $Matches[1] -ne $SubscriptionId) { throw "Wrong subscription on $($change.address)" }
    }
}
$rg = $changes | Where-Object { $_.type -eq "azurerm_resource_group" }
if (-not $rg -or $rg.change.after.name -ne "rg-$Prefix") { throw "Plan must contain the independent rg-$Prefix resource group." }
Write-Host "Plan passed 571 scope checks. Review all changes and costs before applying."
