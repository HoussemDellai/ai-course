resource "azurerm_user_assigned_identity" "app" {
  name                = "id-video-platform"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_role_assignment" "app_acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_foundry_user" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_speech_user" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Cognitive Services Speech User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Data Contributor includes the permission to create user delegation keys for download SAS URLs.
resource "azurerm_role_assignment" "app_blob_contributor" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Role assignments take a little while to propagate before data-plane calls succeed.
resource "time_sleep" "rbac_propagation" {
  create_duration = "60s"

  depends_on = [
    azurerm_role_assignment.app_acr_pull,
    azurerm_role_assignment.app_foundry_user,
    azurerm_role_assignment.app_speech_user,
    azurerm_role_assignment.app_blob_contributor,
    azurerm_role_assignment.me_foundry_user,
    azurerm_role_assignment.me_speech_user,
    azurerm_role_assignment.me_blob_contributor,
  ]
}
