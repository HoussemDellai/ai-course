resource "azurerm_cognitive_account_project" "project" {
  name                 = "foundry-project-${var.prefix}"
  cognitive_account_id = azurerm_cognitive_account.foundry.id
  location             = azurerm_cognitive_account.foundry.location
  description          = "Azure Foundry services project"
  display_name         = "Foundry Project"

  identity {
    type = "SystemAssigned"
  }
}

# Assign the Foundry User role on your Foundry resource to your project's managed identity.
resource "azurerm_role_assignment" "role_foundry_user" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_cognitive_account_project.project.identity.0.principal_id
}

output "foundry_project_endpoint" {
  value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
}
