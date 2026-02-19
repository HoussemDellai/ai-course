resource "azurerm_storage_account" "storage_functions" {
  name                          = "storage4functionapps${var.prefix}"
  resource_group_name           = azurerm_resource_group.rg.name
  location                      = azurerm_resource_group.rg.location
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  shared_access_key_enabled     = true
  public_network_access_enabled = true

  tags = {
    SecurityControl = "Ignore"
  }
}

resource "azurerm_storage_container" "container_functions" {
  name                  = "app-packages-functions"
  storage_account_id    = azurerm_storage_account.storage_functions.id
  container_access_type = "private"
}
