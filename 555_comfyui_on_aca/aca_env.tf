resource "azurerm_container_app_environment" "env" {
  name                       = "aca-environment"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  public_network_access      = "Enabled"
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.workspace.id
  
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

  workload_profile {
    name                  = "GPU-NC8as-T4"
    workload_profile_type = "Consumption-GPU-NC8as-T4" # D4, D8, D16, D32, E4, E8, E16 and E32.
    # minimum_count         = 0
    # maximum_count         = 1
  }

  workload_profile {
    name                  = "GPU-NC24-A100"
    workload_profile_type = "Consumption-GPU-NC24-A100" # D4, D8, D16, D32, E4, E8, E16 and E32.
    # minimum_count         = 0
    # maximum_count         = 1
  }

  lifecycle {
    ignore_changes = [workload_profile]
  }
}
