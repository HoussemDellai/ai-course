resource "azurerm_container_app" "nginx" {
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  name                         = "nginx"
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  ingress {
    allow_insecure_connections = true
    client_certificate_mode    = "ignore"
    external_enabled           = true
    target_port                = 80
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                     = 0
    max_replicas                     = 10
    polling_interval_in_seconds      = 30
    cooldown_period_in_seconds       = 300
    termination_grace_period_seconds = 30

    container {
      image  = "nginx:latest"
      name   = "nginx"
      cpu    = 0.5
      memory = "1Gi"
    }

    http_scale_rule {
      name                = "http-scale"
      concurrent_requests = 2
    }
  }
}

output "aca_nginx_fqdn" {
  value = azurerm_container_app.nginx.ingress.0.fqdn
}
