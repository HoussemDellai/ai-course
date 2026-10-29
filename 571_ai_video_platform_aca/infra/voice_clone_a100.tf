locals {
  voice_clone_a100_enabled = var.voice_clone_enabled && var.voice_clone_a100_enabled
  voice_clone_a100_url     = local.voice_clone_a100_enabled ? "https://${azurerm_container_app.voice_clone_a100[0].ingress[0].fqdn}" : ""
}

# Second deployment of the voice-clone image on a serverless A100, for Fish Audio S2 Pro: the 4.4B-parameter model and its
# KV cache need more than the 16 GiB of the default T4 service. Same image, API key and model cache; the orchestrator sends
# only fish-s2-pro here (VOICE_CLONE_A100_URL). Private, and scaled to zero until a job clones a voice with that engine.
resource "azurerm_container_app" "voice_clone_a100" {
  count                        = local.voice_clone_a100_enabled ? 1 : 0
  name                         = "voice-clone-a100-${var.prefix}"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  revision_mode                = "Single"
  workload_profile_name        = "GPU-NC24-A100"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name  = "api-key"
    value = random_password.voice_clone_key[0].result
  }

  dynamic "secret" {
    for_each = nonsensitive(var.hf_token != "") ? [1] : []
    content {
      name  = "hf-token"
      value = var.hf_token
    }
  }

  ingress {
    external_enabled           = false
    allow_insecure_connections = false
    target_port                = 8000
    transport                  = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 0
    max_replicas                     = 1
    termination_grace_period_seconds = 60

    http_scale_rule {
      name                = "http"
      concurrent_requests = "10"
    }

    container {
      name   = "voice-clone"
      image  = local.voice_clone_image
      cpu    = var.voice_clone_a100_cpu
      memory = "${var.voice_clone_a100_memory_gib}Gi"

      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }
      # The A100 supports bfloat16, so Fish runs without --half.
      env {
        name  = "VOICE_CLONE_FP16"
        value = "0"
      }
      env {
        name  = "MODEL_CACHE"
        value = "/cache/voice-clone"
      }
      env {
        name  = "HF_HOME"
        value = "/cache/voice-clone/hf"
      }
      dynamic "env" {
        for_each = nonsensitive(var.hf_token != "") ? [1] : []
        content {
          name        = "HF_TOKEN"
          secret_name = "hf-token"
        }
      }
      volume_mounts {
        name = "model-cache"
        path = "/cache"
      }
      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/healthz"
        interval_seconds        = 5
        timeout                 = 5
        failure_count_threshold = 60
      }
      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/healthz"
        interval_seconds        = 30
        timeout                 = 10
        failure_count_threshold = 5
      }
    }
    volume {
      name         = "model-cache"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name
      storage_type = "NfsAzureFile"
    }
  }

  depends_on = [
    terraform_data.build_voice_clone_image,
    time_sleep.rbac_propagation,
  ]
}
