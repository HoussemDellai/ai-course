resource "azurerm_container_app_environment" "aca_environment" {
  name                           = "aca-env-${var.prefix}"
  location                       = var.aca_location
  resource_group_name            = azurerm_resource_group.rg.name
  public_network_access          = "Enabled"
  logs_destination               = "log-analytics"
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = false
  infrastructure_subnet_id       = azurerm_subnet.snet_aca.id

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  # workload_profile {
  #   name                  = "GPU-NC24-A100"
  #   workload_profile_type = "Consumption-GPU-NC24-A100"
  # }

  lifecycle {
    ignore_changes = [workload_profile]
  }
}


# There is a bug with adding GPU profiles via terraform, so we need to use local-exec to run the az cli command to add the GPU profiles after the ACA environment is created
resource "terraform_data" "add_serverless_gpu_profile_GPU-NC8as-T4" {
  triggers_replace = [azurerm_container_app_environment.aca_environment.id]

  provisioner "local-exec" {
    command = "az containerapp env workload-profile add --name ${azurerm_container_app_environment.aca_environment.name} --resource-group ${azurerm_container_app_environment.aca_environment.resource_group_name} --workload-profile-type Consumption-GPU-NC8as-T4 --workload-profile-name GPU-NC8as-T4"
  }

  depends_on = [azurerm_container_app_environment.aca_environment]
}

# There is a bug with adding GPU profiles via terraform, so we need to use local-exec to run the az cli command to add the GPU profiles after the ACA environment is created
resource "terraform_data" "add_serverless_gpu_profile_GPU-NC24-A100" {
  triggers_replace = [azurerm_container_app_environment.aca_environment.id]

  provisioner "local-exec" {
    command = "az containerapp env workload-profile add --name ${azurerm_container_app_environment.aca_environment.name} --resource-group ${azurerm_container_app_environment.aca_environment.resource_group_name} --workload-profile-type Consumption-GPU-NC24-A100 --workload-profile-name GPU-NC24-A100"
  }

  depends_on = [
    azurerm_container_app_environment.aca_environment,
    terraform_data.add_serverless_gpu_profile_GPU-NC8as-T4
  ]
}

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui_nfs" {
  name                         = "storage-aca-comfyui-nfs"
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  share_name                   = "/${azurerm_storage_account.storage_comfyui.name}/${azurerm_storage_share.fileshare_comfyui.name}"
  nfs_server_url               = "${azurerm_storage_account.storage_comfyui.name}.file.core.windows.net"
  access_mode                  = "ReadWrite"

  depends_on = [
    azurerm_private_endpoint.pe_storage_account,
    azurerm_private_dns_zone_virtual_network_link.dns_zone_link_storage_account,
  ]
}
