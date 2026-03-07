resource "azurerm_container_app_job" "aca_job_download_models" {
  name                         = "aca-job-download-models"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 1800 # 30 minutes
  replica_retry_limit          = 10

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "download-models"
      image   = "ubuntu:24.04"
      cpu     = 1
      memory  = "2Gi"
      command = ["/bin/bash"]
      args    = ["-c", "apt-get update && apt-get install -y wget && wget https://raw.githubusercontent.com/HoussemDellai/ai-course/refs/heads/main/555_comfyui_on_aca/download-models-comfyui.sh && chmod +x /download-models-comfyui.sh && /download-models-comfyui.sh"]

      volume_mounts {
        name = "storage-comfyui"
        path = "/root/ComfyUI/"
      }
    }

    volume {
      name         = "storage-comfyui"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name
      storage_type = "NfsAzureFile" # "EmptyDir"
    }
  }
}

# trigger the job to start downloading models to the storage
resource "azapi_resource_action" "start_job" {
  type        = "Microsoft.App/jobs@2025-07-01"
  resource_id = azurerm_container_app_job.aca_job_download_models.id
  action      = "start"
  method      = "POST"
}
