resource "azurerm_container_app" "mcp_server" {
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  name                         = "mcp-server"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  ingress {
    allow_insecure_connections = true
    client_certificate_mode    = "ignore"
    external_enabled           = true
    target_port                = 3000
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 1
    max_replicas                     = 1
    polling_interval_in_seconds      = 30
    cooldown_period_in_seconds       = 300
    termination_grace_period_seconds = 30

    container {
      image  = "ghcr.io/aas-ee/open-web-search:v2.1.6"
      name   = "mcp-server"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "DEFAULT_SEARCH_ENGINE"
        value = "duckduckgo" # bing, duckduckgo, exa, brave, baidu, csdn, juejin, startpage
      }
      env {
        name  = "ALLOWED_SEARCH_ENGINES"
        value = "" #	empty (all available) or comma-separated list of allowed engines from the above list
      }
      env {
        name  = "PORT"
        value = "3000" #	1-65535
      }
    }
  }
}

output "aca_mcp_server_fqdn" {
  value = azurerm_container_app.mcp_server.ingress.0.fqdn
}
