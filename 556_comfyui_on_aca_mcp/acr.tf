resource "azurerm_container_registry" "mcp" {
  name                = "acrcomfymcp${var.prefix}${substr(sha1(var.subscription_id), 0, 6)}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_user_assigned_identity" "mcp" {
  name                = "id-comfy-mcp"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_role_assignment" "mcp_pull" {
  scope                = azurerm_container_registry.mcp.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.mcp.principal_id
  principal_type       = "ServicePrincipal"
}
