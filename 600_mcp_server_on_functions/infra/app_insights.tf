resource "azurerm_application_insights" "app_insights" {
  name                          = "app-insights-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  workspace_id                  = azurerm_log_analytics_workspace.workspace.id
  application_type              = "web"
  daily_data_cap_in_gb          = 100
  retention_in_days             = 30
  internet_ingestion_enabled    = true
  internet_query_enabled        = true
  local_authentication_disabled = true
}