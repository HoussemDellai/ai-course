resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "azurerm_container_app" "app" {
  name                         = "video-platform"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

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
    value = random_password.api_key.result
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Video jobs run for hours as background tasks: keep exactly one always-on replica.
    min_replicas = 1
    max_replicas = 1

    dynamic "container" {
      for_each = var.education_drawio_image == "" ? [] : [var.education_drawio_image]
      content {
        name   = "drawio-mcp"
        image  = container.value
        cpu    = 0.5
        memory = "1Gi"

        env {
          name  = "LISTEN"
          value = "0.0.0.0"
        }
        env {
          name  = "PORT"
          value = "3001"
        }
        env {
          name  = "ALLOWED_HOSTS"
          value = "localhost,127.0.0.1"
        }
        env {
          name  = "DRAWIO_ICON_SERVICE_URL"
          value = "off"
        }

        liveness_probe {
          transport = "HTTP"
          port      = 3001
          path      = "/health"
        }
      }
    }

    container {
      name   = "video-platform"
      image  = local.app_image
      cpu    = var.education_drawio_image == "" ? 4 : 3.5
      memory = var.education_drawio_image == "" ? "8Gi" : "7Gi"

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }
      env {
        name  = "FOUNDRY_PROJECT_ENDPOINT"
        value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
      }
      env {
        name  = "FOUNDRY_MODEL_DEPLOYMENT_NAME"
        value = azurerm_cognitive_deployment.llm.name
      }
      env {
        name  = "SPEECH_ENDPOINT"
        value = azurerm_cognitive_account.foundry.endpoint
      }
      env {
        name  = "TTS_VOICE"
        value = var.tts_voice
      }
      env {
        name  = "COMFYUI_URLS"
        value = join(",", local.comfyui_urls)
      }
      env {
        name  = "GPU_STATS_URLS"
        value = join(",", local.comfyui_urls)
      }
      env {
        name  = "DEFAULT_VIDEO_MODEL"
        value = var.default_video_model
      }
      env {
        name  = "STORAGE_ACCOUNT_URL"
        value = azurerm_storage_account.storage.primary_blob_endpoint
      }
      env {
        name  = "STORAGE_CONTAINER"
        value = azurerm_storage_container.videos.name
      }
      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }

      dynamic "env" {
        for_each = var.education_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }
    }
  }

  depends_on = [
    terraform_data.build_app_image,
    time_sleep.rbac_propagation,
  ]
}
