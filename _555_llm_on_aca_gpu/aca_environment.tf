resource "azurerm_container_app_environment" "aca_environment" {
  name                           = "aca-env-gpu-nvidia"
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

# There is a bug with adding GPU profiles via terraform, so we need to use local-exec to run the az cli command to add the GPU profiles after the ACA environment is created
resource "terraform_data" "add_serverless_gpu_profile_GPU-NC8as-T4" {
  triggers_replace = [azurerm_container_app_environment.aca_environment.id]

  provisioner "local-exec" {
    command = "az containerapp env workload-profile add --name ${azurerm_container_app_environment.aca_environment.name} --resource-group ${azurerm_container_app_environment.aca_environment.resource_group_name} --workload-profile-type Consumption-GPU-NC8as-T4 --workload-profile-name GPU-NC8as-T4"
  }

  depends_on = [ azurerm_container_app_environment.aca_environment ]
}

# There is a bug with adding GPU profiles via terraform, so we need to use local-exec to run the az cli command to add the GPU profiles after the ACA environment is created
resource "terraform_data" "add_serverless_gpu_profile_GPU-NC24-A100" {
  triggers_replace = [azurerm_container_app_environment.aca_environment.id]

  provisioner "local-exec" {
    command = "az containerapp env workload-profile add --name ${azurerm_container_app_environment.aca_environment.name} --resource-group ${azurerm_container_app_environment.aca_environment.resource_group_name} --workload-profile-type Consumption-GPU-NC24-A100 --workload-profile-name GPU-NC24-A100"
  }

  depends_on = [ azurerm_container_app_environment.aca_environment, terraform_data.add_serverless_gpu_profile_GPU-NC8as-T4 ]
}

# resource "azapi_update_resource" "add_serverless_gpu_profile" {
#   type        = "Microsoft.App/managedEnvironments@2026-01-01"
#   resource_id = azurerm_container_app_environment.aca_environment.id
#   # schema_validation_enabled = false

#   body = {
#     properties = {
#       appInsightsConfiguration = null
#       appLogsConfiguration = {
#         destination = "log-analytics"
#         logAnalyticsConfiguration = {
#           customerId = azurerm_log_analytics_workspace.workspace.customer_id
#           sharedKey  = 
#         }
#       }
#       workloadProfiles = [
#         {
#           enableFips          = false
#           name                = "Consumption"
#           workloadProfileType = "Consumption"
#         },
#         {
#           enableFips          = false
#           maximumCount        = 1
#           minimumCount        = 0
#           name                = "profile-D4"
#           workloadProfileType = "D4"
#         }
#       ]
#       zoneRedundant = false
#     }
#   }
# }

# resource "azapi_resource" "add_serverless_gpu_profile" {
#   type      = "Microsoft.App/managedEnvironments@2026-01-01"
#   parent_id = "/subscriptions/dcef7009-6b94-4382-afdc-17eb160d709a/resourceGroups/rg-aca-gpu-nvidia-comfyui"
#   name      = "aca-env-gpu-nvidia"
#   location  = "Sweden Central"
#   identity {
#     type         = "SystemAssigned"
#     identity_ids = []
#   }
#   body = {
#     properties = {
#       appInsightsConfiguration = null
#       appLogsConfiguration = {
#         destination = "log-analytics"
#         logAnalyticsConfiguration = {
#           customerId = "6aa91d30-144e-434d-ac7e-bbc80deca28e"
#           sharedKey  = null
#         }
#       }
#       customDomainConfiguration = {
#         certificateKeyVaultProperties = null
#         certificatePassword           = null
#         certificateValue              = null
#         dnsSuffix                     = null
#       }
#       daprAIConnectionString      = null
#       daprAIInstrumentationKey    = null
#       daprConfiguration           = {}
#       infrastructureResourceGroup = "ME_aca-env-gpu-nvidia_rg-aca-gpu-nvidia-comfyui_swedencentral"
#       ingressConfiguration        = null
#       kedaConfiguration           = {}
#       openTelemetryConfiguration  = null
#       peerAuthentication = {
#         mtls = {
#           enabled = false
#         }
#       }
#       peerTrafficConfiguration = {
#         encryption = {
#           enabled = false
#         }
#       }
#       publicNetworkAccess = "Enabled"
#       vnetConfiguration = {
#         dockerBridgeCidr       = null
#         infrastructureSubnetId = "/subscriptions/dcef7009-6b94-4382-afdc-17eb160d709a/resourceGroups/rg-aca-gpu-nvidia-comfyui/providers/Microsoft.Network/virtualNetworks/vnet-aca/subnets/snet-aca"
#         internal               = false
#         platformReservedCidr   = null
#         platformReservedDnsIP  = null
#       }
#       workloadProfiles = [{
#         enableFips          = false
#         name                = "Consumption"
#         workloadProfileType = "Consumption"
#         },
#         {
#           enableFips          = false
#           maximumCount        = 1
#           minimumCount        = 0
#           name                = "profile-D4"
#           workloadProfileType = "D4"
#       }]
#       zoneRedundant = false
#     }
#   }
# }

resource "azurerm_container_app_environment_storage" "storage_aca_comfyui_nfs" {
  name                         = "storage-aca-comfyui-nfs"
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  share_name                   = "/${azurerm_storage_account.storage_comfyui.name}/${azurerm_storage_share.fileshare_comfyui.name}" # azurerm_storage_share.fileshare_comfyui.name
  nfs_server_url               = "${azurerm_storage_account.storage_comfyui.name}.file.core.windows.net"
  access_mode                  = "ReadWrite" # "ReadOnly"
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

output "supported_workload_profiles" {
  value = "az containerapp env workload-profile list-supported --location ${azurerm_resource_group.rg.location} -o table"
}