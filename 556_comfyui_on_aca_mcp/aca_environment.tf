resource "azurerm_container_app_environment" "aca_environment" {
  name                           = "aca-env-comfyui-mcp-${var.prefix}"
  location                       = azurerm_resource_group.rg.location
  resource_group_name            = azurerm_resource_group.rg.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  logs_destination               = "log-analytics"
  infrastructure_subnet_id       = azurerm_subnet.snet_aca.id
  public_network_access          = "Enabled"
  internal_load_balancer_enabled = false

  identity {
    type = "SystemAssigned"
  }

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  # AzureRM cannot manage serverless GPU profiles; the CLI owns that list.
  lifecycle {
    ignore_changes = [workload_profile]
  }
}

resource "terraform_data" "add_a100_profile" {
  triggers_replace = [azurerm_container_app_environment.aca_environment.id]
  provisioner "local-exec" {
    command = "az containerapp env workload-profile add --subscription ${var.subscription_id} --name ${azurerm_container_app_environment.aca_environment.name} --resource-group ${azurerm_resource_group.rg.name} --workload-profile-type Consumption-GPU-NC24-A100 --workload-profile-name GPU-NC24-A100 --only-show-errors"
  }
}

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui_nfs" {
  name                         = "storage-aca-comfyui-nfs"
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  share_name                   = "/${azurerm_storage_account.storage_comfyui.name}/${azurerm_storage_share.fileshare_comfyui.name}" # azurerm_storage_share.fileshare_comfyui.name
  nfs_server_url               = "${azurerm_storage_account.storage_comfyui.name}.file.core.windows.net"
  access_mode                  = "ReadWrite" # "ReadOnly"
}

# role assignment to allow ACA environment to access the storage account File Share
resource "azurerm_role_assignment" "aca_env_storage_blob_data_contributor" {
  scope                = azurerm_storage_share.fileshare_comfyui.id # azurerm_storage_account.storage_comfyui.id
  role_definition_name = "Storage File Data Privileged Contributor"
  principal_id         = azurerm_container_app_environment.aca_environment.identity.0.principal_id
}
