resource "azurerm_storage_account" "storage_comfyui" {
  name                       = "storage4comfyuiaca"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = azurerm_resource_group.rg.location
  account_tier               = "Premium"     # For BlockBlobStorage and FileStorage accounts only Premium is valid.
  account_kind               = "FileStorage" # StorageV2 (general purpose v2) is the default and recommended storage account type for most scenarios. It supports all the latest features, including Azure Data Lake Storage Gen2, and offers the best performance and cost-effectiveness for a wide range of workloads.
  account_replication_type   = "LRS"
  shared_access_key_enabled  = true
  https_traffic_only_enabled = false
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
  quota              = 1024  # GB
}

resource "azurerm_private_dns_zone" "dns_zone_storage_account" {
  name                = "privatelink.file.core.windows.net"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "dns_zone_link_storage_account" {
  name                  = "dns-zone-link-storage-account"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.dns_zone_storage_account.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "pe_storage_account" {
  name                          = "pe-storage-account"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  subnet_id                     = azurerm_subnet.snet_pe.id
  custom_network_interface_name = "nic-pe-storage-account"

  private_dns_zone_group {
    name                 = "group"
    private_dns_zone_ids = [azurerm_private_dns_zone.dns_zone_storage_account.id]
  }

  private_service_connection {
    name                           = "connection"
    private_connection_resource_id = azurerm_storage_account.storage_comfyui.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }
}
