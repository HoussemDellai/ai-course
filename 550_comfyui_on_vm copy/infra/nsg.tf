resource "azurerm_network_security_group" "nsg_vm" {
  name                = "nsg-vm"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_network_security_rule" "allow_ssh" {
  network_security_group_name = azurerm_network_security_group.nsg_vm.name
  resource_group_name         = azurerm_network_security_group.nsg_vm.resource_group_name
  name                        = "allow-ssh"
  access                      = "Allow"
  priority                    = 1000
  direction                   = "Inbound"
  protocol                    = "Tcp"
  source_address_prefix       = "*"
  source_port_range           = "*"
  destination_address_prefix  = "*"
  destination_port_range      = "22"
}

resource "azurerm_network_security_rule" "allow_http" {
  network_security_group_name = azurerm_network_security_group.nsg_vm.name
  resource_group_name         = azurerm_network_security_group.nsg_vm.resource_group_name
  name                        = "allow-http"
  access                      = "Allow"
  priority                    = 101
  direction                   = "Inbound"
  protocol                    = "Tcp"
  source_address_prefix       = "*"
  source_port_range           = "*"
  destination_address_prefix  = "*"
  destination_port_range      = "8188"
}

resource "azurerm_subnet_network_security_group_association" "nsg-association" {
  subnet_id                 = azurerm_subnet.snet_vm.id
  network_security_group_id = azurerm_network_security_group.nsg_vm.id
}
