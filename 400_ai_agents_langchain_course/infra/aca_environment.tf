resource "azurerm_container_app_environment" "aca_environment" {
  name                           = "aca-environment"
  location                       = azurerm_resource_group.rg.location
  resource_group_name            = azurerm_resource_group.rg.name
  public_network_access          = "Enabled"
  # internal_load_balancer_enabled = false
  # zone_redundancy_enabled        = false
  # infrastructure_subnet_id       = ""

  identity {
    type = "SystemAssigned"
  }

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}
