data "azurerm_monitor_diagnostic_categories" "categories_apim" {
  resource_id = azurerm_api_management.apim.id
}

resource "azurerm_monitor_diagnostic_setting" "diagnostics_apim" {
  name                           = "diagnostic-settings-az-apim"
  target_resource_id             = azurerm_api_management.apim.id
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.log-analytics.id
  log_analytics_destination_type = "Dedicated" # "AzureDiagnostics"

  dynamic "enabled_log" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories_apim.log_category_types

    content {
      category = enabled_log.key
    }
  }

  dynamic "enabled_metric" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories_apim.metrics

    content {
      category = enabled_metric.key
    }
  }

  lifecycle {
    ignore_changes = [
      log_analytics_destination_type
    ]
  }
}
