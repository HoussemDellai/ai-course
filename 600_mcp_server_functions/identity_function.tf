# user assigned identity for the function app
resource "azurerm_user_assigned_identity" "identity_function_app" {
  name                = "identity-function-app-${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

# --- Storage Blob Data Owner --- Managed Identity
resource "azurerm_role_assignment" "storage_blob_mi" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
}

# --- Storage Blob Data Owner --- User Identity                                                                           
resource "azurerm_role_assignment" "storage_blob_user" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

# # Storage Queue Data Contributor
# resource "azurerm_role_assignment" "storage_queue_mi" {
#   scope                = azurerm_storage_account.storage_functions.id
#   role_definition_name = "Storage Queue Data Contributor"
#   principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
# }

# # Storage Table Data Contributor
# resource "azurerm_role_assignment" "storage_table_mi" {
#   scope                = azurerm_storage_account.storage_functions.id
#   role_definition_name = "Storage Table Data Contributor"
#   principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
# }

data "azurerm_client_config" "current" {}
