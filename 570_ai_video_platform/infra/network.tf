resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.10.0.0/16"]
}

resource "azurerm_subnet" "snet_vm" {
  name                            = "snet-vm"
  resource_group_name             = azurerm_resource_group.rg.name
  virtual_network_name            = azurerm_virtual_network.vnet.name
  address_prefixes                = ["10.10.1.0/24"]
  default_outbound_access_enabled = false
}

resource "azurerm_virtual_network" "vnet_aca" {
  name                = "vnet-aca-${var.prefix}"
  location            = "italynorth" # azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.11.0.0/16"]
}

# Container Apps environment (workload profiles) needs a delegated subnet of at least /27.
resource "azurerm_subnet" "snet_aca" {
  name                 = "snet-aca"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet_aca.name
  address_prefixes     = ["10.11.2.0/23"]

  delegation {
    name = "aca"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_network_security_group" "nsg_vm" {
  name                = "nsg-vm"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

# The Container App calls ComfyUI on the VM's public IP, and its outbound IPs come from a large, changing pool.
# WARNING: ComfyUI has no authentication, so anyone who knows the IP can queue jobs on the GPU.
resource "azurerm_network_security_rule" "allow_comfyui_from_internet" {
  network_security_group_name = azurerm_network_security_group.nsg_vm.name
  resource_group_name         = azurerm_resource_group.rg.name
  name                        = "allow-comfyui-from-internet"
  access                      = "Allow"
  priority                    = 105
  direction                   = "Inbound"
  protocol                    = "Tcp"
  source_address_prefix       = "*"
  source_port_range           = "*"
  destination_address_prefix  = "*"
  destination_port_range      = "8188"
}

resource "azurerm_network_security_rule" "allow_ssh" {
  network_security_group_name = azurerm_network_security_group.nsg_vm.name
  resource_group_name         = azurerm_resource_group.rg.name
  name                        = "allow-ssh"
  access                      = "Allow"
  priority                    = 1000
  direction                   = "Inbound"
  protocol                    = "Tcp"
  source_address_prefix       = var.admin_source_address_prefix
  source_port_range           = "*"
  destination_address_prefix  = "*"
  destination_port_range      = "22"
}

resource "azurerm_subnet_network_security_group_association" "nsg_vm" {
  subnet_id                 = azurerm_subnet.snet_vm.id
  network_security_group_id = azurerm_network_security_group.nsg_vm.id
}
