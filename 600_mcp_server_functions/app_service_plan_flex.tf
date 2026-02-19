resource "azurerm_service_plan" "app_service_plan_functions" {
  name                = "app-service-plan-functions"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku_name            = "FC1"
  os_type             = "Linux"
}