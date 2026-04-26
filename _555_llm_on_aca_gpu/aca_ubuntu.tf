resource "azurerm_container_app" "ubuntu" {
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  name                         = "ubuntu"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    min_replicas                     = 1
    max_replicas                     = 1
    polling_interval_in_seconds      = 30
    cooldown_period_in_seconds       = 300
    termination_grace_period_seconds = 30

    container {
      image  = "ubuntu:24.04"
      name   = "ubuntu"
      cpu    = 1
      memory = "2Gi"
      command = ["/bin/bash", "-c", "--"]
      args    = ["while true; do sleep 30; done;"]

      volume_mounts {
        name = "storage-llm"
        path = "/root/.cache/" # "/root/.cache/huggingface/"
      }
    }

    volume {
      name         = "storage-llm"
      storage_name = azurerm_container_app_environment_storage.storage_aca_llm_nfs.name # azurerm_container_app_environment_storage.storage_aca_llm.name
      storage_type = "NfsAzureFile"                                                     # "AzureFile" # AzureFile (SMB) or NfsAzureFile (NFS) # Volume with Nfs Azure File storage is only supported for container app on managed environment with custom VNet.
    }
  }
}
