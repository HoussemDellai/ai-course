resource "azurerm_container_app_environment" "env" {
  name                       = "aca-environment-ai"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = null
  public_network_access      = "Enabled"
  # internal_load_balancer_enabled = false
  # zone_redundancy_enabled        = false
  # infrastructure_subnet_id       = null

  # identity {
  #   type = "SystemAssigned"
  # }

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  workload_profile {
    name                  = "profile-D4"
    workload_profile_type = "D4" # D4, D8, D16, D32, E4, E8, E16 and E32.
    minimum_count         = 0
    maximum_count         = 1
  }

  # workload_profile {
  #   name                  = "GPU-NC8as-T4"
  #   workload_profile_type = "Consumption-GPU-NC8as-T4" # D4, D8, D16, D32, E4, E8, E16 and E32.
  #   # minimum_count         = 0
  #   # maximum_count         = 1
  # }
}

resource "azurerm_user_assigned_identity" "identity_aca" {
  name                = "identity-aca"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_role_assignment" "role_acrpull_aca" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.identity_aca.principal_id
}

resource "azurerm_role_assignment" "role_azure_ai_user_aca" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Azure AI User"
  principal_id         = azurerm_user_assigned_identity.identity_aca.principal_id
}

resource "azurerm_container_app" "aca_agent" {
  name                         = "aca-agent"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity_aca.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.identity_aca.id
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "aca-agent"
      image  = "${azurerm_container_registry.acr.login_server}/${var.hosted_agent_name}:${var.hosted_agent_version}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "AZURE_AI_PROJECT_ENDPOINT"
        value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
      }
      env {
        name  = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
        value = azurerm_cognitive_deployment.gpt_52.name
      }
      env {
        name  = "BING_CUSTOM_CONNECTION_NAME"
        value = azapi_resource.connection_bing_search_custom.name
      }
      env {
        name  = "BING_CONFIGURATION_NAME"
        value = azapi_resource.configuration_bing_search_custom.name
      }
      env {
        name  = "AZURE_CLIENT_ID" # Needed for authentication with User Assigned Identity and DefaultAzureCredential()
        value = azurerm_user_assigned_identity.identity_aca.client_id
      }
    }
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8088
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [azurerm_role_assignment.role_acrpull_aca]
}

resource "azurerm_container_app" "aca_agent_monitoring" {
  name                         = "aca-agent-monitoring"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity_aca.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.identity_aca.id
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "aca-agent"
      image  = "${azurerm_container_registry.acr.login_server}/${var.hosted_agent_name}:${var.hosted_agent_version}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "APP_INSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.app_insights.connection_string
      }
      env {
        name  = "ENABLE_INSTRUMENTATION"
        value = "true"
      }
      env {
        name  = "ENABLE_CONSOLE_EXPORTERS"
        value = "true"
      }
      env {
        name  = "AZURE_AI_PROJECT_ENDPOINT"
        value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
      }
      env {
        name  = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
        value = azurerm_cognitive_deployment.gpt_4o_mini.name
      }
      env {
        name  = "BING_CUSTOM_CONNECTION_NAME"
        value = azapi_resource.connection_bing_search_custom.name
      }
      env {
        name  = "BING_CONFIGURATION_NAME"
        value = azapi_resource.configuration_bing_search_custom.name
      }
      # env {
      #   name  = "BING_CUSTOM_INSTANCE_NAME"
      #   value = azapi_resource.configuration_bing_search_custom.name
      # }
      # env {
      #   name  = "BING_CUSTOM_SEARCH_INSTANCE_NAME"
      #   value = azapi_resource.bing_search_custom.name
      # }
      # env {
      #   name  = "BING_CUSTOM_SEARCH_PROJECT_CONNECTION_NAME"
      #   value = azapi_resource.connection_bing_search_custom.name
      # }
      # env {
      #   name  = "BING_CUSTOM_CONNECTION_ID"
      #   value = azapi_resource.connection_bing_search_custom.id
      # }
      # env {
      #   name  = "BING_CUSTOM_SEARCH_PROJECT_CONNECTION_ID"
      #   value = azapi_resource.connection_bing_search_custom.id
      # }
      env {
        name  = "AZURE_CLIENT_ID" # Needed for authentication with User Assigned Identity and DefaultAzureCredential()
        value = azurerm_user_assigned_identity.identity_aca.client_id
      }
    }
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8088
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [azurerm_role_assignment.role_acrpull_aca]
}

resource "azurerm_container_app" "aca_inspector_gadget" {
  name                         = "inspector-gadget"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  template {
    min_replicas = 1
    max_replicas = 3
    container {
      name   = "inspector-gadget"
      image  = "jelledruyts/inspectorgadget"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 80
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

output "aca_agent_endpoint" {
  value = azurerm_container_app.aca_agent.ingress.0.fqdn
}

output "aca_inspector_gadget_endpoint" {
  value = azurerm_container_app.aca_inspector_gadget.ingress.0.fqdn
}
