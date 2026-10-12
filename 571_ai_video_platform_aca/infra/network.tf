resource "azurerm_virtual_network" "vnet_aca" {
  name                = "vnet-aca-${var.prefix}"
  location            = var.aca_location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.11.0.0/16"]
}

# Container Apps environment (workload profiles) needs a delegated subnet of at least /27.
resource "azurerm_subnet" "snet_aca" {
  name                 = "snet-aca-env"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet_aca.name
  address_prefixes     = ["10.11.0.0/23"]

  delegation {
    name = "aca"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "snet_pe" {
  name                 = "snet-pe"
  resource_group_name  = azurerm_virtual_network.vnet_aca.resource_group_name
  virtual_network_name = azurerm_virtual_network.vnet_aca.name
  address_prefixes     = ["10.11.2.0/27"]
}
