resource "azurerm_key_vault" "keyvault" {
  name                        = "keyvault4foundry${var.prefix}"
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  enabled_for_disk_encryption = true
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false
  sku_name                    = "standard"
  rbac_authorization_enabled  = true
}

resource "azurerm_key_vault_secret" "secret" {
  name         = "secret-password-${var.prefix}"
  value        = "@Aa123456789"
  key_vault_id = azurerm_key_vault.keyvault.id

  depends_on = [ azurerm_role_assignment.key-vault-secrets-administrator ]
}

# role assignment for the Key Vault
resource "azurerm_role_assignment" "key-vault-secrets-administrator" {
  scope                = azurerm_key_vault.keyvault.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

data "azurerm_client_config" "current" {}

output "keyvault_uri" {
  value = azurerm_key_vault.keyvault.vault_uri
}

output "keyvault_secret_name" {
  value = azurerm_key_vault_secret.secret.name
}