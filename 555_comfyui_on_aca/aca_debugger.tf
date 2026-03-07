resource "azurerm_container_app" "aca_debugger" {
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  name                         = "aca-debugger"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption" # "GPU-NC8as-T4"

  ingress {
    allow_insecure_connections = true
    client_certificate_mode    = "ignore"
    external_enabled           = false
    target_port                = 80
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 1
    max_replicas                     = 1
    polling_interval_in_seconds      = 30
    cooldown_period_in_seconds       = 300
    termination_grace_period_seconds = 30
    revision_suffix                  = ""

    container {
      image   = "nginx:latest"
      name    = "nginx"
      cpu     = 1
      memory  = "2Gi"
      command = ["/bin/bash"]
      args    = ["-c", "apt-get update && apt-get install -y wget"]


      volume_mounts {
        name = "storage-comfyui"
        path = "/root/ComfyUI/"
      }
    }

    volume {
      name         = "storage-comfyui"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name # azurerm_container_app_environment_storage.storage_aca_comfyui.name
      storage_type = "NfsAzureFile" # "AzureFile" # AzureFile (SMB) or NfsAzureFile (NFS) # Volume with Nfs Azure File storage is only supported for container app on managed environment with custom VNet.
    }
  }
}

output "aca_debugger_fqdn" {
  value = azurerm_container_app.aca_debugger.ingress.0.fqdn
}
