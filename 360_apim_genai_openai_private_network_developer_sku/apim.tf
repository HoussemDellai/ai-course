resource "azurerm_api_management" "apim" {
  name                          = "apim-genai-dev-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  publisher_name                = "My Company"
  publisher_email               = "noreply@microsoft.com"
  sku_name                      = "Developer_1" # "Developer_1"
  virtual_network_type          = "External"    # None, External, Internal
  public_network_access_enabled = true          # false applies only when using private endpoint as the exclusive access method
  public_ip_address_id          = azurerm_public_ip.pip-apim.id

  identity {
    type = "SystemAssigned"
  }

  virtual_network_configuration {
    subnet_id = azurerm_subnet.snet-apim.id
  }

  depends_on = [azurerm_subnet_network_security_group_association.nsg-association]
}

resource "azurerm_role_assignment" "Cognitive-Services-OpenAI-User" {
  scope                = azurerm_ai_services.ai-services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_api_management.apim.identity.0.principal_id
}
