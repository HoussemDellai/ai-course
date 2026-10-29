resource "azurerm_storage_account" "storage_comfyui" {
  name                       = "st4comfy${var.prefix}"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = var.aca_location
  account_tier               = "Premium"     # For BlockBlobStorage and FileStorage accounts only Premium is valid.
  account_kind               = "FileStorage" # StorageV2 (general purpose v2) is the default and recommended storage account type for most scenarios. It supports all the latest features, including Azure Data Lake Storage Gen2, and offers the best performance and cost-effectiveness for a wide range of workloads.
  account_replication_type   = "LRS"
  shared_access_key_enabled  = false
  https_traffic_only_enabled = false
  public_network_access      = "Disabled"

  network_rules {
    default_action = "Deny"
    bypass         = ["None"]
  }

  # Microsoft Defender for Storage adds its data scanner as a private link access rule; keep it.
  lifecycle {
    ignore_changes = [network_rules[0].private_link_access]
  }
}

resource "azurerm_storage_share" "fileshare_comfyui" {
  name               = "fileshare-comfyui"
  storage_account_id = azurerm_storage_account.storage_comfyui.id
  enabled_protocol   = "NFS"
  quota              = var.model_storage_gib
}
