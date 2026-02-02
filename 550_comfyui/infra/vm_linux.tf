resource "azurerm_public_ip" "pip_vm_linux" {
  name                = "pip-vm-linux"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "nic_vm_linux" {
  name                = "nic-vm-linux"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.snet_vm.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip_vm_linux.id
  }
}

resource "azurerm_linux_virtual_machine" "vm_linux" {
  name                            = "vm-linux-comfyui"
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  size                            = "Standard_NC40ads_H100_v5"
  disable_password_authentication = false
  admin_username                  = "azureuser"
  admin_password                  = "@Aa123456789"
  priority                        = "Spot"
  eviction_policy                 = "Delete" # "Deallocate" # With Spot, there's no option of Stop-Deallocate for Ephemeral VMs, rather users need to Delete instead of deallocating them.
  network_interface_ids           = [azurerm_network_interface.nic_vm_linux.id]
  disk_controller_type            = "SCSI" # "NVMe" is not supported in this SKU

  os_disk {
    name                 = "os-disk-vm-linux"
    caching              = "ReadOnly"        # "ReadWrite" # None, ReadOnly and ReadWrite.
    storage_account_type = "StandardSSD_LRS" # "Standard_LRS"
    disk_size_gb         = 1024              # GB

    diff_disk_settings {
      option    = "Local"    # Specifies the Ephemeral Disk Settings for the OS Disk. At this time the only possible value is Local.
      placement = "NvmeDisk" # "ResourceDisk" # "CacheDisk" # Specifies the Ephemeral Disk Placement for the OS Disk. NvmeDisk can only be used for v6 VMs
    }
  }

  source_image_reference {
    publisher = "canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "ubuntu-pro"
    version   = "latest"
  }

  boot_diagnostics {
    storage_account_uri = null
  }
}

output "vm_linux_public_ip" {
  value = azurerm_public_ip.pip_vm_linux.ip_address
}

output "vm_linux_private_ip" {
  value = azurerm_network_interface.nic_vm_linux.private_ip_address
}

output "comfyui_portal" {
  value = "http://${azurerm_public_ip.pip_vm_linux.ip_address}:8188"
}