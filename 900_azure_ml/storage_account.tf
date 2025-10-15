resource "azurerm_storage_account" "storage" {
  name                      = "saaml${var.prefix}"
  location                  = azurerm_resource_group.rg.location
  resource_group_name       = azurerm_resource_group.rg.name
  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = true

  tags = {
    CostControl     = "Ignore"
    SecurityControl = "Ignore"
  }
}