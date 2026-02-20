data "azurerm_monitor_diagnostic_categories" "categories-bing-search-custom" {
  resource_id = azapi_resource.bing_search_custom.id
}

resource "azurerm_monitor_diagnostic_setting" "diagnostics_bing_search_custom" {
  name                           = "diagnostic-settings-bing-search-custom-${var.prefix}"
  target_resource_id             = azapi_resource.bing_search_custom.id
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  log_analytics_destination_type = "Dedicated" # "AzureDiagnostics"


  dynamic "enabled_log" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-bing-search-custom.log_category_types

    content {
      category = enabled_log.key
    }
  }

  dynamic "enabled_metric" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-bing-search-custom.metrics

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
