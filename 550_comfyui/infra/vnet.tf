resource "azurerm_virtual_network" "vnet_vm" {
  name                = "vnet-vm"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.0.0.0/16"]
  dns_servers         = null
}

resource "azurerm_subnet" "snet_vm" {
  name                            = "snet-vm"
  resource_group_name             = azurerm_virtual_network.vnet_vm.resource_group_name
  virtual_network_name            = azurerm_virtual_network.vnet_vm.name
  address_prefixes                = ["10.0.0.0/24"]
  default_outbound_access_enabled = false
}