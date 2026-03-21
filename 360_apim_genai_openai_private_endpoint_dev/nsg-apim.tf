resource "azurerm_network_security_group" "nsg-apim" {
  name                = "nsg-apim"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet_network_security_group_association" "nsg-association" {
  subnet_id                 = azurerm_subnet.snet-apim.id
  network_security_group_id = azurerm_network_security_group.nsg-apim.id
}