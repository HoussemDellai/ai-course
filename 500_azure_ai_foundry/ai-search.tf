resource "azurerm_search_service" "search-service" {
  name                          = "search-service-${random_string.random.result}-${var.prefix}"
  resource_group_name           = azurerm_resource_group.rg.name
  location                      = azurerm_resource_group.rg.location
  sku                           = "basic" # basic, free, standard, standard2, standard3, storage_optimized_l1 and storage_optimized_l2
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }
}