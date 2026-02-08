resource "azurerm_container_app_environment" "aca_environment" {
  name                           = "aca-environment-gpu"
  location                       = azurerm_resource_group.rg.location
  resource_group_name            = azurerm_resource_group.rg.name
  public_network_access          = "Enabled"
  logs_destination               = "log-analytics"
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = false
  infrastructure_subnet_id       = azurerm_subnet.snet_aca.id

  identity {
    type = "SystemAssigned"
  }

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  workload_profile {
    name                  = "profile-D4"
    workload_profile_type = "D4" # D4, D8, D16, D32, E4, E8, E16 and E32.
    minimum_count         = 0
    maximum_count         = 1
  }

  # workload_profile {
  #   name                  = "GPU-NC8as-T4"
  #   workload_profile_type = "Consumption-GPU-NC8as-T4" # D4, D8, D16, D32, E4, E8, E16 and E32.
  #   # minimum_count         = 0
  #   # maximum_count         = 1
  # }

  # workload_profile {
  #   name                  = "GPU-NC24-A100"
  #   workload_profile_type = "Consumption-GPU-NC24-A100" # D4, D8, D16, D32, E4, E8, E16 and E32.
  #   # minimum_count         = 0
  #   # maximum_count         = 1
  # }

  lifecycle {
    ignore_changes = [workload_profile]
  }
}

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui_nfs" {
  name                         = "storage-aca-comfyui-nfs"
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  share_name                   = "/${azurerm_storage_account.storage_comfyui.name}/${azurerm_storage_share.fileshare_comfyui.name}" # azurerm_storage_share.fileshare_comfyui.name
  nfs_server_url               = "${azurerm_storage_account.storage_comfyui.name}.file.core.windows.net"
  access_mode                  = "ReadWrite"                                                                                        # "ReadOnly"
}

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui_smb" {
  name                         = "storage-aca-comfyui-smb"
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  account_name                 = azurerm_storage_account.storage_comfyui.name
  share_name                   = azurerm_storage_share.fileshare_comfyui.name
  access_key                   = azurerm_storage_account.storage_comfyui.primary_access_key
  access_mode                  = "ReadWrite" # "ReadOnly"
}

# role assignment to allow ACA environment to access the storage account File Share
resource "azurerm_role_assignment" "aca_env_storage_blob_data_contributor" {
  scope                = azurerm_storage_share.fileshare_comfyui.id # azurerm_storage_account.storage_comfyui.id
  role_definition_name = "Storage File Data Privileged Contributor"
  principal_id         = azurerm_container_app_environment.aca_environment.identity.0.principal_id
}