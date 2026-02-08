
resource "azurerm_storage_account" "storage_comfyui" {
  name                      = "storage4comfyuiaca"
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = azurerm_resource_group.rg.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = true

  tags = {
    SecurityControl = "Ignore"
    CostControl     = "Ignore"
  }
}

resource "azurerm_storage_share" "fileshare_comfyui" {
  name               = "fileshare-comfyui"
  storage_account_id = azurerm_storage_account.storage_comfyui.id
  quota              = 100 # GB
}

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui" {
  name                         = "storage-aca-comfyui"
  container_app_environment_id = azurerm_container_app_environment.env.id
  account_name                 = azurerm_storage_account.storage_comfyui.name
  share_name                   = azurerm_storage_share.fileshare_comfyui.name
  access_key                   = azurerm_storage_account.storage_comfyui.primary_access_key
  access_mode                  = "ReadWrite" # "ReadOnly"
}
