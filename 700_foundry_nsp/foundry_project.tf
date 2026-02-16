
resource "azurerm_cognitive_account_project" "project" {
  name                 = "project-${var.prefix}"
  cognitive_account_id = azurerm_cognitive_account.foundry.id
  location             = azurerm_cognitive_account.foundry.location
  description          = "Example cognitive services project"
  display_name         = "Example Project"

  identity {
    type = "SystemAssigned"
  }
}

# give your project's managed identity access to pull from the container registry that houses your image.
resource "azurerm_role_assignment" "foundry_project_acrpull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_cognitive_account_project.project.identity.0.principal_id
}

resource "azurerm_role_assignment" "role_azure_ai_user_foundry_project" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Azure AI User"
  principal_id         = azurerm_cognitive_account_project.project.identity.0.principal_id
}

output "foundry_project_name" {
  value = azurerm_cognitive_account_project.project.name
}

output "foundry_project_endpoint" {
  value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
}
