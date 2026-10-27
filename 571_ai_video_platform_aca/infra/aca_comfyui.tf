locals {
  comfyui_worker_names = {
    primary = "comfyui-${var.prefix}"
    # To restore the second A100, uncomment this entry and set comfyui_worker_count = 2.
    # secondary = "comfyui-${var.prefix}-2"
  }
  comfyui_workers = {
    for key, name in local.comfyui_worker_names : key => name
    if key == "primary" || var.comfyui_worker_count == 2
  }
  comfyui_urls  = [for key in sort(keys(local.comfyui_workers)) : "https://${azurerm_container_app.comfyui[key].ingress[0].fqdn}"]
  comfyui_url   = local.comfyui_urls[0]
  gpu_stats_url = local.comfyui_url
}

moved {
  from = azurerm_container_app.comfyui
  to   = azurerm_container_app.comfyui["primary"]
}

resource "azurerm_container_app" "comfyui" {
  for_each                     = local.comfyui_workers
  name                         = each.value
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  revision_mode                = "Single"
  workload_profile_name        = "GPU-NC24-A100"

  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8188
    transport                  = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 1
    max_replicas                     = 1
    termination_grace_period_seconds = 600

    container {
      name    = "comfyui"
      image   = var.comfyui_image
      cpu     = 2
      memory  = "${var.comfyui_memory_gib}Gi"
      command = ["/bin/bash", "-c"]
      args    = [replace(file("${path.module}/scripts/start-comfyui.sh"), "\r\n", "\n")]

      env {
        name  = "COMFY_BOOTSTRAP_B64"
        value = local.bootstrap_b64
      }
      env {
        name  = "PROVISION_VERSION"
        value = local.provision_version
      }
      env {
        name  = "COMFY_WORKER"
        value = each.key
      }
      volume_mounts {
        name = "storage-comfyui"
        path = "/root/ComfyUI"
      }
      startup_probe {
        transport               = "HTTP"
        port                    = 8188
        path                    = "/system_stats"
        interval_seconds        = 10
        timeout                 = 5
        failure_count_threshold = 240
      }
      readiness_probe {
        transport        = "HTTP"
        port             = 8188
        path             = "/system_stats"
        interval_seconds = 10
        timeout          = 5
      }
      liveness_probe {
        transport               = "HTTP"
        port                    = 8188
        path                    = "/system_stats"
        interval_seconds        = 30
        timeout                 = 10
        failure_count_threshold = 5
      }
    }
    volume {
      name         = "storage-comfyui"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name
      storage_type = "NfsAzureFile"
    }
  }

  depends_on = [terraform_data.provision_models]
}
