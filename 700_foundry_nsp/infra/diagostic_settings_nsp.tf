data "azurerm_monitor_diagnostic_categories" "categories-nsp" {
  resource_id = azurerm_network_security_perimeter.nsp.id # azapi_resource.networkSecurityPerimeter.id
}

resource "azurerm_monitor_diagnostic_setting" "diagnostics_nsp" {
  name                           = "diagnostic-settings-nsp${var.prefix}"
  target_resource_id             = azurerm_network_security_perimeter.nsp.id
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  log_analytics_destination_type = "Dedicated" # "AzureDiagnostics"


  dynamic "enabled_log" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-nsp.log_category_types

    content {
      category = enabled_log.key
    }
  }

  dynamic "enabled_metric" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-nsp.metrics

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
