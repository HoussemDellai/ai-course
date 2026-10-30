locals {
  governance_suffix = substr(sha256(azurerm_resource_group.rg.id), 0, 8)
  subscription_id   = data.azurerm_client_config.current.subscription_id

  # Resource groups whose NSGs get the RDP rule; edit rdp-resource-groups.json to extend.
  rdp_resource_groups = toset(jsondecode(file("${path.module}/rdp-resource-groups.json")).resourceGroups)
  rdp_resource_group_ids = {
    for name in local.rdp_resource_groups : name => "/subscriptions/${local.subscription_id}/resourceGroups/${name}"
  }
}

resource "azurerm_user_assigned_identity" "governance" {
  name                = "id-foundry-auth-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_storage_account" "governance" {
  name                            = "stauth${local.governance_suffix}"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = true
  public_network_access           = "Enabled"
  allow_nested_items_to_be_public = false

  tags = {
    SecurityControl = "Ignore"
    CostControl     = "Ignore"
  }
}

resource "azapi_resource" "governance_package" {
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01"
  name      = "function-packages"
  parent_id = "${azurerm_storage_account.governance.id}/blobServices/default"
  body = {
    properties = {
      publicAccess = "None"
    }
  }
}

resource "azurerm_role_assignment" "governance_storage" {
  scope                = azurerm_storage_account.governance.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.governance.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_definition" "governance" {
  name        = "Foundry Local Auth Maintenance ${var.prefix}-${local.governance_suffix}"
  scope       = azurerm_resource_group.rg.id
  description = "Read and update the designated Foundry account without access to its keys or role assignments."

  permissions {
    actions = [
      "Microsoft.CognitiveServices/accounts/read",
      "Microsoft.CognitiveServices/accounts/write",
    ]
  }

  assignable_scopes = [azurerm_resource_group.rg.id]
}

resource "azurerm_role_assignment" "governance_foundry" {
  scope              = azurerm_cognitive_account.foundry.id
  role_definition_id = azurerm_role_definition.governance.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.governance.principal_id
  principal_type     = "ServicePrincipal"
}

resource "azurerm_role_definition" "governance_rdp" {
  name        = "NSG RDP Rule Maintenance ${var.prefix}-${local.governance_suffix}"
  scope       = "/subscriptions/${local.subscription_id}"
  description = "Read NSGs in designated resource groups and manage their child security rules without replacing NSGs."

  permissions {
    actions = [
      "Microsoft.Network/networkSecurityGroups/read",
      "Microsoft.Network/networkSecurityGroups/securityRules/read",
      "Microsoft.Network/networkSecurityGroups/securityRules/write",
    ]
  }

  assignable_scopes = values(local.rdp_resource_group_ids)
}

resource "azurerm_role_assignment" "governance_rdp" {
  for_each           = local.rdp_resource_group_ids
  scope              = each.value
  role_definition_id = azurerm_role_definition.governance_rdp.role_definition_resource_id
  principal_id       = azurerm_user_assigned_identity.governance.principal_id
  principal_type     = "ServicePrincipal"
}

resource "azurerm_log_analytics_workspace" "governance" {
  name                = "log-foundry-auth-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "governance" {
  name                = "appi-foundry-auth-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.governance.id
  application_type    = "web"
}

resource "azurerm_service_plan" "governance" {
  name                = "plan-foundry-auth-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "FC1"
}

resource "azurerm_function_app_flex_consumption" "governance" {
  name                                           = "func-foundry-auth-${var.prefix}-${local.governance_suffix}"
  location                                       = azurerm_resource_group.rg.location
  resource_group_name                            = azurerm_resource_group.rg.name
  service_plan_id                                = azurerm_service_plan.governance.id
  storage_container_type                         = "blobContainer"
  storage_container_endpoint                     = "${azurerm_storage_account.governance.primary_blob_endpoint}${azapi_resource.governance_package.name}"
  storage_authentication_type                    = "UserAssignedIdentity"
  storage_user_assigned_identity_id              = azurerm_user_assigned_identity.governance.id
  runtime_name                                   = "powershell"
  runtime_version                                = "7.4"
  maximum_instance_count                         = 40
  instance_memory_in_mb                          = 512
  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.governance.id]
  }

  site_config {
    minimum_tls_version                    = "1.2"
    application_insights_connection_string = azurerm_application_insights.governance.connection_string
  }

  app_settings = {
    # Override the provider-generated empty-key connection string so identity settings take effect.
    "AzureWebJobsStorage"              = ""
    "AzureWebJobsStorage__accountName" = azurerm_storage_account.governance.name
    "AzureWebJobsStorage__credential"  = "managedidentity"
    "AzureWebJobsStorage__clientId"    = azurerm_user_assigned_identity.governance.client_id
    "AZURE_CLIENT_ID"                  = azurerm_user_assigned_identity.governance.client_id
    "FOUNDRY_SUBSCRIPTION_ID"          = data.azurerm_client_config.current.subscription_id
    "FOUNDRY_RESOURCE_GROUP"           = azurerm_resource_group.rg.name
    "FOUNDRY_ACCOUNT_NAME"             = azurerm_cognitive_account.foundry.name
    "TIMER_SCHEDULE"                   = "0 */5 * * * *"
    "RDP_RESOURCE_GROUPS"              = jsonencode(sort(tolist(local.rdp_resource_groups)))
  }

  depends_on = [
    azurerm_role_assignment.governance_storage,
    azurerm_role_assignment.governance_foundry,
    azurerm_role_assignment.governance_rdp,
  ]
}

# Event Grid validates the function endpoint when the subscription is created, so the
# package containing the eventGridTrigger function must be deployed first.
resource "terraform_data" "governance_package_deploy" {
  triggers_replace = [
    azurerm_function_app_flex_consumption.governance.id,
    sha256(join("", [
      for f in sort(tolist(fileset("${path.module}/functions/foundry-local-auth", "**"))) :
      filesha256("${path.module}/functions/foundry-local-auth/${f}")
    ])),
    filesha256("${path.module}/Build-FunctionPackage.ps1"),
  ]

  provisioner "local-exec" {
    interpreter = ["pwsh", "-NoProfile", "-Command"]
    command     = <<-EOT
      $ErrorActionPreference = 'Stop'
      & '${path.module}/Build-FunctionPackage.ps1'
      az functionapp deployment source config-zip --subscription '${local.subscription_id}' --resource-group '${azurerm_resource_group.rg.name}' --name '${azurerm_function_app_flex_consumption.governance.name}' --src '${path.module}/.terraform/foundry-local-auth.zip'
      if ($LASTEXITCODE -ne 0) { throw 'Function package deployment failed.' }
    EOT
  }
}

# Notifies EnsureRdpAccess whenever an NSG or one of its rules is written or deleted in
# the listed resource groups. Only one system topic per subscription can exist.
resource "azurerm_eventgrid_system_topic" "nsg_changes" {
  name                = "evgt-nsg-changes-${var.prefix}"
  location            = "global"
  resource_group_name = azurerm_resource_group.rg.name
  source_resource_id  = "/subscriptions/${local.subscription_id}"
  topic_type          = "Microsoft.Resources.Subscriptions"
}

resource "azurerm_eventgrid_system_topic_event_subscription" "ensure_rdp_access" {
  name                  = "evgs-ensure-rdp-access"
  system_topic          = azurerm_eventgrid_system_topic.nsg_changes.name
  resource_group_name   = azurerm_resource_group.rg.name
  included_event_types  = ["Microsoft.Resources.ResourceWriteSuccess", "Microsoft.Resources.ResourceDeleteSuccess"]
  event_delivery_schema = "EventGridSchema"

  azure_function_endpoint {
    function_id                       = "${azurerm_function_app_flex_consumption.governance.id}/functions/EnsureRdpAccess"
    max_events_per_batch              = 1
    preferred_batch_size_in_kilobytes = 64
  }

  advanced_filter {
    string_begins_with {
      key = "subject"
      values = [
        for name in sort(tolist(local.rdp_resource_groups)) :
        "${local.rdp_resource_group_ids[name]}/providers/Microsoft.Network/networkSecurityGroups/"
      ]
    }
  }

  retry_policy {
    max_delivery_attempts = 10
    event_time_to_live    = 60
  }

  depends_on = [terraform_data.governance_package_deploy]
}

output "governance_function_app_name" {
  value = azurerm_function_app_flex_consumption.governance.name
}
