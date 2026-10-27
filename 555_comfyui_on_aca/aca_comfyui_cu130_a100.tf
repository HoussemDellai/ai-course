resource "azurerm_container_app" "aca_comfyui_cu130_a100" {
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  name                         = "comfyui-cu130-a100"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "GPU-NC24-A100"

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8188
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      # Linux amd64 manifest for yanwk/comfyui-boot:cu130-slim.
      # image   = "yanwk/comfyui-boot@sha256:94ddc8f1b14d1b6b25b0db18ec2faf6ab5ba9acbc5bd943291caf43981a81605"
      image   = "yanwk/comfyui-boot:cu130-slim"
      name    = "comfyui"
      cpu     = 8
      memory  = "56Gi"
      args    = []
      command = []

      env {
        name  = "CLI_ARGS"
        value = "--disable-xformers"
      }

      volume_mounts {
        name = "models-readonly"
        path = "/mnt/model-source"
      }
    }

    volume {
      name         = "models-readonly"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs_readonly.name
      storage_type = "NfsAzureFile"
    }
  }

  depends_on = [terraform_data.add_serverless_gpu_profile_GPU-NC24-A100]
}

output "aca_comfyui_cu130_a100_fqdn" {
  value = azurerm_container_app.aca_comfyui_cu130_a100.ingress.0.fqdn
}
