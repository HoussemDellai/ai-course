# https://learn.microsoft.com/en-us/azure/api-management/visualize-using-managed-grafana-dashboard

resource "azurerm_dashboard_grafana" "grafana" {
  name                              = "grafana-${var.prefix}"
  resource_group_name               = azurerm_resource_group.rg.name
  location                          = azurerm_resource_group.rg.location
  grafana_major_version             = 11
  api_key_enabled                   = true
  deterministic_outbound_ip_enabled = true
  public_network_access_enabled     = true
  sku                               = "Standard"
  zone_redundancy_enabled           = false

  identity {
    type = "SystemAssigned"
  }
}

data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "role_grafana_admin" {
  scope                = azurerm_dashboard_grafana.grafana.id
  role_definition_name = "Grafana Admin"
  principal_id         = data.azurerm_client_config.current.object_id
}

data "azurerm_subscription" "current" {}

resource "azurerm_role_assignment" "role_monitoring_reader" {
  scope                = azurerm_resource_group.rg.id # data.azurerm_subscription.current.id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_dashboard_grafana.grafana.identity.0.principal_id
}

# resource "terraform_data" "import-grafana-dashboard-apim" {
#   triggers_replace = [ azurerm_dashboard_grafana.grafana.id ]

#   provisioner "local-exec" {
#     command = "az grafana dashboard import -n ${azurerm_dashboard_grafana.grafana.name} --definition 16604"
#   }
# }