locals {
  voice_clone_version = trimspace(file("${path.module}/../voice_clone_server/VERSION"))
  voice_clone_tag     = "voice-clone:${local.voice_clone_version}"
  voice_clone_image   = "${azurerm_container_registry.acr.login_server}/${local.voice_clone_tag}"
  voice_clone_url     = var.voice_clone_enabled ? "https://${azurerm_container_app.voice_clone[0].ingress[0].fqdn}" : ""
}

resource "random_password" "voice_clone_key" {
  count   = var.voice_clone_enabled ? 1 : 0
  length  = 32
  special = false
}

# Builds the voice-clone GPU image in ACR when its version tag is missing: bump voice_clone_server/VERSION to ship changes.
resource "terraform_data" "build_voice_clone_image" {
  count            = var.voice_clone_enabled ? 1 : 0
  triggers_replace = [azurerm_container_registry.acr.id, local.voice_clone_image]

  provisioner "local-exec" {
    working_dir = "${path.module}/../voice_clone_server"
    interpreter = ["pwsh", "-NoProfile", "-File"]
    command     = "${abspath(path.module)}/scripts/build-app-image.ps1"
    environment = {
      SUBSCRIPTION_ID = var.subscription_id
      ACR_NAME        = azurerm_container_registry.acr.name
      APP_IMAGE_TAG   = local.voice_clone_tag
      APP_DOCKERFILE  = "Dockerfile"
    }
  }
}

# Zero-shot voice cloning engines (Qwen3-TTS, Chatterbox, OpenVoice v2, Fish Audio S2 Pro) on a serverless GPU.
# Private to the environment, and scaled to zero when no job clones a voice. Model weights are cached on the NFS share.
resource "azurerm_container_app" "voice_clone" {
  count                        = var.voice_clone_enabled ? 1 : 0
  name                         = "voice-clone-${var.prefix}"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  revision_mode                = "Single"
  workload_profile_name        = var.voice_clone_workload_profile

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

    container {
      name   = "voice-clone"
      image  = local.voice_clone_image
      cpu    = var.voice_clone_cpu
      memory = "${var.voice_clone_memory_gib}Gi"

      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }
      env {
        name  = "VOICE_CLONE_FP16"
        value = strcontains(var.voice_clone_workload_profile, "T4") ? "1" : "0"
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
