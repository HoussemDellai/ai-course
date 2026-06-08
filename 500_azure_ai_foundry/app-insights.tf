resource "azurerm_application_insights" "app-insights" {
  name                          = "appinsights-${random_string.random.result}-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  application_type              = "web"
  workspace_id                  = azurerm_log_analytics_workspace.log-analytics.id
  sampling_percentage           = null
  retention_in_days             = 30
  local_authentication_disabled = false
}

resource "azurerm_log_analytics_workspace" "log-analytics" {
  name                = "log-analytics-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}