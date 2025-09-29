resource "azurerm_storage_account" "storage" {
  name                            = "storage${random_string.random.result}${var.prefix}"
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true
  # public_network_access_enabled   = true
}
