# managed identity for ACA to access Azure Storage

resource "azurerm_user_assigned_identity" "aca_identity" {
  name                = "aca-identity"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_role_assignment" "aca_storage_blob_data_contributor" {
  scope                = azurerm_storage_account.storage_comfyui.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.aca_identity.principal_id
}