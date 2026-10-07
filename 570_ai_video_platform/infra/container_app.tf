resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "env" {
  name                       = "aca-env-${var.prefix}"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = "italynorth" # "swedencentral" # azurerm_resource_group.rg.location
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  infrastructure_subnet_id   = azurerm_subnet.snet_aca.id

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "azurerm_container_app" "app" {
  name                         = "video-platform"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.env.id
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

    container {
      name   = "video-platform"
      image  = local.app_image
      cpu    = 4
      memory = "8Gi"

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
        value = local.comfyui_url
      }
      env {
        name  = "GPU_STATS_URLS"
        value = local.gpu_stats_url
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
