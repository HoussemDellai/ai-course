# resource "azurerm_container_app" "aca_comfyui_cu130_a100" {
#   container_app_environment_id = azurerm_container_app_environment.aca_environment.id
#   name                         = "comfyui-cu130-a100"
#   resource_group_name          = azurerm_resource_group.rg.name
#   revision_mode                = "Single"
#   workload_profile_name        = "GPU-NC24-A100" # "GPU-NC8as-T4"

#   ingress {
#     allow_insecure_connections = true
#     client_certificate_mode    = "ignore"
#     external_enabled           = true
#     target_port                = 8188
#     transport                  = "auto"

#     traffic_weight {
#       latest_revision = true
#       percentage      = 100
#     }
#   }

#   template {
#     min_replicas                     = 0
#     max_replicas                     = 10
#     polling_interval_in_seconds      = 30
#     cooldown_period_in_seconds       = 300
#     termination_grace_period_seconds = 0
#     revision_suffix                  = ""

#     container {
#       image   = "yanwk/comfyui-boot:cu130-slim"
#       name    = "comfyui"
#       cpu     = 2     # 8 max for NC8as T4, 24 for NC24 A100
#       memory  = "4Gi" # "56Gi" max for NC8as T4, 220Gi for NC24 A100
#       args    = []
#       command = []

#       env {
#         name  = "CLI_ARGS"
#         value = "--disable-xformers"
#       }

#       volume_mounts {
#         name = "storage-comfyui"
#         path = "/root/ComfyUI/"
#       }
#     }

#     volume {
#       name         = "storage-comfyui"
#       storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name # azurerm_container_app_environment_storage.storage_aca_comfyui.name
#       storage_type = "NfsAzureFile"                                                         # "AzureFile" # AzureFile (SMB) or NfsAzureFile (NFS) # Volume with Nfs Azure File storage is only supported for container app on managed environment with custom VNet.
#     }
#   }

#   depends_on = [terraform_data.add_serverless_gpu_profile_GPU-NC24-A100]
# }

# output "aca_comfyui_cu130_a100_fqdn" {
#   value = azurerm_container_app.aca_comfyui_cu130_a100.ingress.0.fqdn
# }
