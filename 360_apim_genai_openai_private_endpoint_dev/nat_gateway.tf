resource "azurerm_public_ip" "pip-nat-gateway" {
  name                = "pip-nat-gateway"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  ip_version          = "IPv4" # "IPv6"
  sku                 = "Standard"
  zones               = ["1"]
}

resource "azurerm_nat_gateway" "nat-gateway" {
  name                    = "nat-gateway"
  location                = azurerm_resource_group.rg.location
  resource_group_name     = azurerm_resource_group.rg.name
  sku_name                = "Standard"
  idle_timeout_in_minutes = 10
  zones                   = ["1"]
}

resource "azurerm_nat_gateway_public_ip_association" "natgw-pip-association" {
  nat_gateway_id       = azurerm_nat_gateway.nat-gateway.id
  public_ip_address_id = azurerm_public_ip.pip-nat-gateway.id
}

resource "azurerm_subnet_nat_gateway_association" "association" {
  subnet_id      = azurerm_subnet.snet-apim.id
  nat_gateway_id = azurerm_nat_gateway.nat-gateway.id
}

output "nat_gateway_ip" {
  value = azurerm_public_ip.pip-nat-gateway.ip_address
}