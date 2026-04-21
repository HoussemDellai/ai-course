# resource "azurerm_container_app" "aca_gemma4_31b_it_a100_dockerhub" {
#   container_app_environment_id = azurerm_container_app_environment.aca_environment.id
#   name                         = "gemma-4-31b-it-a100-dockerhub"
#   resource_group_name          = azurerm_resource_group.rg.name
#   revision_mode                = "Single"
#   workload_profile_name        = "GPU-NC24-A100" # "GPU-NC8as-T4"

#   ingress {
#     allow_insecure_connections = true
#     client_certificate_mode    = "ignore"
#     external_enabled           = true
#     target_port                = 8000
#     transport                  = "auto"

#     traffic_weight {
#       latest_revision = true
#       percentage      = 100
#     }
#   }

#   template {
#     min_replicas                     = 1
#     max_replicas                     = 10
#     polling_interval_in_seconds      = 30
#     cooldown_period_in_seconds       = 300
#     termination_grace_period_seconds = 0
#     revision_suffix                  = ""

#     container {
#       image  = "ai/gemma4:31B"
#       name   = "gemma4-31b"
#       cpu    = 1     # 12      # 24      # 8
#       memory = "8Gi" # "100Gi" # "220Gi" # "56Gi"
#       # args    = []
#       # command = []

#       # The image entrypoint stays as-is; these are the args you passed after the image name.
#       # args = [
#       #   "--model", "google/gemma-4-31B-it",
#       #   "--tensor-parallel-size", "1",
#       #   "--max-model-len", "8736",
#       #   "--gpu-memory-utilization", "0.85",
#       #   "--limit-mm-per-prompt", jsonencode({ "images" : 4, "videos" : 1, "audios" : 1 }),
#       #   "--enable-auto-tool-choice",
#       #   "--tool-call-parser", "gemma4",
#       #   "--reasoning-parser", "gemma4",
#       #   "--chat-template", "examples/tool_chat_template_gemma4.jinja",
#       #   "--host", "0.0.0.0",
#       #   "--port", "8000"
#       # ]

#       # # Optional: HF token if needed for gated models
#       # dynamic "env" {
#       #   for_each = var.hf_token != "" ? [1] : []
#       #   content {
#       #     name  = "HF_TOKEN"
#       #     value = var.hf_token
#       #   }
#       # }


#       # vllm serve google/gemma-4-31B-it \
#       #   --tensor-parallel-size 1 \
#       #   --max-model-len 8736 \
#       #   --gpu-memory-utilization 0.85 \
#       #   --host 0.0.0.0 \
#       #   --port 8000

#       # env {
#       #   name  = "CLI_ARGS"
#       #   value = "--disable-xformers"
#       # }

#       # volume_mounts {
#       #   name = "storage-comfyui"
#       #   path = "/root/ComfyUI/"
#       # }
#     }

#     # volume {
#     #   name         = "storage-comfyui"
#     #   storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name # azurerm_container_app_environment_storage.storage_aca_comfyui.name
#     #   storage_type = "NfsAzureFile" # "AzureFile" # AzureFile (SMB) or NfsAzureFile (NFS) # Volume with Nfs Azure File storage is only supported for container app on managed environment with custom VNet.
#     # }
#   }

#   depends_on = [terraform_data.add_serverless_gpu_profile_GPU-NC24-A100]
# }

# output "aca_gemma4_31b_it_a100_dockerhub_fqdn" {
#   value = azurerm_container_app.aca_gemma4_31b_it_a100_dockerhub.ingress.0.fqdn
# }
