resource "azurerm_api_management" "apim" {
  name                          = "apim-genai-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  publisher_name                = "My Company"
  publisher_email               = "noreply@microsoft.com"
  sku_name                      = "StandardV2_1" # "Consumption_0" # "Developer_1"
  virtual_network_type          = "None"         # None, External, Internal
  public_network_access_enabled = true           # false applies only when using private endpoint as the exclusive access method

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "Cognitive-Services-OpenAI-User" {
  scope                = azurerm_ai_services.ai-services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_api_management.apim.identity.0.principal_id
}

resource "azurerm_role_assignment" "Monitoring-Metrics-Publisher" {
  scope                = azurerm_application_insights.app-insights.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_api_management.apim.identity.0.principal_id
}
