resource "azurerm_container_registry" "acr" {
  name                = "acr${random_string.random.result}${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Standard"
  admin_enabled       = true
}