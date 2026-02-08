resource "azurerm_container_app_job" "aca_job_download_models" {
  name                         = "aca-job-download-models"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 600
  replica_retry_limit          = 10

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "download-models"
      image   = "ubuntu:24.04" # "nginx:latest"
      cpu     = 0.5
      memory  = "1Gi"
      command = ["/bin/bash"]

      args    = ["-c", "apt-get update && apt-get install -y wget && wget "]
    #   args    = ["-c", "apt-get update && apt-get install -y wget && wget -O /root/ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors > /root/ComfyUI/job2.txt"]
    #   args    = ["-c", "echo Downloading models... > /root/ComfyUI/job.txt && sleep 30 && echo Models downloaded!"]

      volume_mounts {
        name = "storage-comfyui"
        path = "/root/ComfyUI/"
        # path = "/mnt/app-azure-file"
      }
    }

    volume {
      name         = "storage-comfyui"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui.name
      storage_type = "AzureFile" # "EmptyDir"
    }
  }
}
