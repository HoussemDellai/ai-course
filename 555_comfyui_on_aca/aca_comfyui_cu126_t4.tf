resource "azurerm_container_app" "aca_comfyui_cu126_t4" {
  container_app_environment_id = azurerm_container_app_environment.env.id
  name                         = "comfyui-cu126-t4"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "GPU-NC8as-T4" # "GPU-NC24-A100"

  ingress {
    allow_insecure_connections = true
    client_certificate_mode    = "ignore"
    external_enabled           = true
    target_port                = 8188
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 0
    max_replicas                     = 10
    polling_interval_in_seconds      = 30
    cooldown_period_in_seconds       = 300
    termination_grace_period_seconds = 0
    revision_suffix                  = ""

    container {
      image   = "yanwk/comfyui-boot:cu126-slim"
      name    = "comfyui"
      cpu     = 8      # 8
      memory  = "56Gi" # "56Gi"
      args    = []
      command = []

      env {
        name  = "CLI_ARGS"
        value = "--disable-xformers"
      }
    }
  }
}

output "aca_comfyui_cu126_t4_fqdn" {
  value = azurerm_container_app.aca_comfyui_cu126_t4.ingress.0.fqdn
}