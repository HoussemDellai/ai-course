resource "azurerm_container_app" "mcp" {
  count                        = var.enable_mcp ? 1 : 0
  name                         = "comfy-mcp"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.mcp.id]
  }

  registry {
    server   = azurerm_container_registry.mcp.login_server
    identity = azurerm_user_assigned_identity.mcp.id
  }

  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8000
    transport                  = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "mcp"
      image  = var.mcp_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "COMFY_BACKEND_URL"
        value = "https://${azurerm_container_app.aca_comfyui_cu130_a100.ingress[0].fqdn}"
      }

      startup_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/healthz"
        interval_seconds        = 5
        failure_count_threshold = 30
      }
      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/healthz"
        interval_seconds        = 10
        failure_count_threshold = 3
      }
      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/healthz"
        interval_seconds        = 30
        failure_count_threshold = 3
      }
    }
  }

  lifecycle {
    precondition {
      condition     = startswith(var.mcp_image, "${azurerm_container_registry.mcp.login_server}/")
      error_message = "Build and supply an image from this scenario's ACR before enabling MCP."
    }
  }
  depends_on = [azurerm_role_assignment.mcp_pull]
}
