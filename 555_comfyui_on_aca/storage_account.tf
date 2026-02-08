resource "azurerm_storage_account" "storage_comfyui" {
  name                      = "storage4comfyuiaca"
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = azurerm_resource_group.rg.location
  account_tier              = "Premium"     # For BlockBlobStorage and FileStorage accounts only Premium is valid.
  account_kind              = "FileStorage" # StorageV2 (general purpose v2) is the default and recommended storage account type for most scenarios. It supports all the latest features, including Azure Data Lake Storage Gen2, and offers the best performance and cost-effectiveness for a wide range of workloads.
  account_replication_type  = "LRS"
  shared_access_key_enabled = true
#   is_hns_enabled            = true
#   nfsv3_enabled             = true

  tags = {
    SecurityControl = "Ignore"
    CostControl     = "Ignore"
  }
}

resource "azurerm_storage_share" "fileshare_comfyui" {
  name               = "fileshare-comfyui"
  storage_account_id = azurerm_storage_account.storage_comfyui.id
  enabled_protocol   = "NFS" # "SMB" or "NFS". Defaults to SMB
  quota              = 100   # GB
}
