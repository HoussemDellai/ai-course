resource "azurerm_cognitive_account" "account" {
  name                               = "account-${var.prefix}"
  location                           = azurerm_resource_group.rg.location
  resource_group_name                = azurerm_resource_group.rg.name
  kind                               = "AIServices"
  sku_name                           = "S0"
  project_management_enabled         = true
  custom_subdomain_name              = "account-${var.prefix}"
  local_auth_enabled                 = true
  public_network_access_enabled      = true
  outbound_network_access_restricted = false

  identity {
    type = "SystemAssigned"
  }

  tags = {
    SecurityControl = "Ignore"
  }
}

resource "azurerm_cognitive_account_project" "project" {
  name                 = "project-${var.prefix}"
  cognitive_account_id = azurerm_cognitive_account.account.id
  location             = azurerm_resource_group.rg.location
  description          = "Example cognitive services project"
  display_name         = "Example Project"

  identity {
    type = "SystemAssigned"
  }
}

output "cognitive_account_endpoint" {
  value = azurerm_cognitive_account.account.endpoint
}

output "cognitive_account_primary_access_key" {
  value     = azurerm_cognitive_account.account.primary_access_key
  sensitive = true
}
