resource "azurerm_private_dns_zone" "privatelink-cognitiveservices-azure-com" {
  name                = "privatelink.cognitiveservices.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone" "privatelink-openai-azure-com" {
  name                = "privatelink.openai.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone" "privatelink-services-ai-azure-com" {
  name                = "privatelink.services.ai.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "privatelink-cognitiveservices-azure-com" {
  name                  = "privatelink-cognitiveservices-azure-com"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.privatelink-cognitiveservices-azure-com.name
  virtual_network_id    = azurerm_virtual_network.vnet-spoke.id
}

resource "azurerm_private_dns_zone_virtual_network_link" "privatelink-openai-azure-com" {
  name                  = "privatelink-openai-azure-com"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.privatelink-openai-azure-com.name
  virtual_network_id    = azurerm_virtual_network.vnet-spoke.id
}

resource "azurerm_private_dns_zone_virtual_network_link" "privatelink-services-ai-azure-com" {
  name                  = "privatelink-services-ai-azure-com"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.privatelink-services-ai-azure-com.name
  virtual_network_id    = azurerm_virtual_network.vnet-spoke.id
}