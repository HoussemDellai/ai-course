resource "azurerm_key_vault" "keyvault" {
  name                     = "kv-aml-${var.prefix}"
  location                 = azurerm_resource_group.rg.location
  resource_group_name      = azurerm_resource_group.rg.name
  tenant_id                = data.azurerm_client_config.current.tenant_id
  sku_name                 = "standard"
  purge_protection_enabled = true
}

data "azurerm_client_config" "current" {}
