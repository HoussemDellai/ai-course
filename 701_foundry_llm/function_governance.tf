locals {
  governance_suffix     = substr(sha256(azurerm_resource_group.rg.id), 0, 8)
  rdp_resource_group_id = "/subscriptions/2524a5e1-00d7-43c2-a7cf-a87b79df2415/resourceGroups/rg-vm-copilot"
  rdp_nsg_ids = {
    vm     = "${local.rdp_resource_group_id}/providers/Microsoft.Network/networkSecurityGroups/vm-copilot-nsg"
    subnet = "${local.rdp_resource_group_id}/providers/Microsoft.Network/networkSecurityGroups/vnet-francecentral-1-snet-francecentral-1-nsg-francecentral"
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
  scope       = local.rdp_resource_group_id
  description = "Read designated NSGs and manage their child security rules without replacing NSGs."

  permissions {
    actions = [
      "Microsoft.Network/networkSecurityGroups/read",
      "Microsoft.Network/networkSecurityGroups/securityRules/read",
      "Microsoft.Network/networkSecurityGroups/securityRules/write",
    ]
  }

  assignable_scopes = [local.rdp_resource_group_id]
}

resource "azurerm_role_assignment" "governance_rdp" {
  for_each           = local.rdp_nsg_ids
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
    "RDP_TIMER_SCHEDULE"               = "0 */5 * * * *"
    "RDP_NSG_IDS"                      = jsonencode(values(local.rdp_nsg_ids))
  }

  depends_on = [
    azurerm_role_assignment.governance_storage,
    azurerm_role_assignment.governance_foundry,
    azurerm_role_assignment.governance_rdp,
  ]
}

output "governance_function_app_name" {
  value = azurerm_function_app_flex_consumption.governance.name
}
