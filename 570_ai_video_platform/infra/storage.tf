resource "azurerm_storage_account" "storage" {
  name                            = "st${var.prefix}"
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  shared_access_key_enabled       = false # Entra ID only; downloads use user delegation SAS
  allow_nested_items_to_be_public = false
  public_network_access           = "Enabled"
  tags                            = { "SecurityControl" = "Ignore" }
}

resource "azurerm_storage_container" "videos" {
  name                  = "videos"
  storage_account_id    = azurerm_storage_account.storage.id
  container_access_type = "private"

  depends_on = [time_sleep.rbac_propagation]
}

resource "azurerm_role_assignment" "me_blob_contributor" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
