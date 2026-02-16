data "azurerm_monitor_diagnostic_categories" "categories-foundry-project" {
  resource_id = azurerm_cognitive_account_project.project.id # azapi_resource.networkSecurityPerimeter.id
}

resource "azurerm_monitor_diagnostic_setting" "diagnostics_foundry_project" {
  name                           = "diagnostic-settings-foundry-project-${var.prefix}"
  target_resource_id             = azurerm_cognitive_account_project.project.id
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.workspace.id
  log_analytics_destination_type = "Dedicated" # "AzureDiagnostics"


  dynamic "enabled_log" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-foundry-project.log_category_types

    content {
      category = enabled_log.key
    }
  }

  dynamic "enabled_metric" {
    for_each = data.azurerm_monitor_diagnostic_categories.categories-foundry-project.metrics

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
