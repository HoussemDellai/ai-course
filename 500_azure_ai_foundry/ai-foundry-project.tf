resource "azurerm_ai_foundry_project" "ai-foundry-project" {
  name                         = "ai-foundry-project"
  location                     = azurerm_ai_foundry.ai-foundry-hub.location
  ai_services_hub_id           = azurerm_ai_foundry.ai-foundry-hub.id
  high_business_impact_enabled = false

  identity {
    type = "SystemAssigned"
    # identity_ids = [azurerm_user_assigned_identity.ua.id]
  }
}

# resource "azapi_resource" "project" {
#   type      = "Microsoft.MachineLearningServices/workspaces@2024-10-01"
#   name      = "ai-project"
#   location  = azurerm_resource_group.rg.location
#   parent_id = azurerm_resource_group.rg.id

#   identity {
#     type = "SystemAssigned"
#   }

#   body = {
#     properties = {
#       description         = "This is my Azure AI PROJECT"
#       friendlyName        = "My Project"
#       hubResourceId       = azapi_resource.hub.id
#       publicNetworkAccess = "Enabled"
#       # ipAllowlist         = []
#     }
#     kind = "Project"
#   }

#   response_export_values = ["id", "name", "location", "identity", "properties"]
# }
