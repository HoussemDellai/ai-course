resource "azurerm_api_management" "apim" {
  name                          = "apim-genai-${random_string.random.result}-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  publisher_name                = "My Company"
  publisher_email               = "noreply@microsoft.com"
  sku_name                      = "StandardV2_1" # Consumption, Developer, Basic, BasicV2, Standard, StandardV2, Premium and PremiumV2
  public_network_access_enabled = true           # false applies only when using private endpoint as the exclusive access method
  virtual_network_type          = "External"     # None, External, Internal

  virtual_network_configuration {
    subnet_id = azurerm_subnet.snet-apim.id
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "Cognitive-Services-OpenAI-User" {
  scope                = azurerm_ai_services.ai-services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_api_management.apim.identity.0.principal_id
}
