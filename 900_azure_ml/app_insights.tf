resource "azurerm_application_insights" "app_insights" {
  name                = "app-insights-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
}