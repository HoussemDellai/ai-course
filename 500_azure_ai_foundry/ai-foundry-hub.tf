resource "azurerm_ai_foundry" "ai-foundry-hub" {
  name                         = "ai-foundry-hub"
  location                     = azurerm_ai_services.ai-services.location
  resource_group_name          = azurerm_ai_services.ai-services.resource_group_name
  storage_account_id           = azurerm_storage_account.storage.id
  key_vault_id                 = azurerm_key_vault.keyvault.id
  high_business_impact_enabled = false
  public_network_access        = "Enabled"
  application_insights_id      = azurerm_application_insights.app-insights.id
  container_registry_id        = azurerm_container_registry.acr.id
  # primary_user_assigned_identity - 

  identity {
    type = "SystemAssigned"
    # identity_ids = [azurerm_user_assigned_identity.ua.id]
  }

  managed_network {
    isolation_mode = "Disabled" # AllowOnlyApprovedOutbound, and AllowInternetOutbound
  }
}

# resource "azapi_resource" "hub" {
#   type      = "Microsoft.MachineLearningServices/workspaces@2024-07-01-preview"
#   name      = "ai-hub"
#   location  = azurerm_resource_group.rg.location
#   parent_id = azurerm_resource_group.rg.id

#   identity {
#     type = "SystemAssigned"
#   }

#   body = {
#     kind = "Hub"
#     properties = {
#       description         = "This is my Azure AI hub"
#       friendlyName        = "My Hub"
#       publicNetworkAccess = "Enabled"
#       storageAccount      = azurerm_storage_account.storage.id
#       keyVault            = azurerm_key_vault.keyvault.id
#       applicationInsights = azurerm_application_insights.app-insights.id
#       containerRegistry   = azurerm_container_registry.acr.id
#       # managedNetwork = {
#       #   isolationMode = "Disabled"
#       # }
#     }
#   }

#   response_export_values = ["id", "name", "location", "identity", "properties"]
# }
