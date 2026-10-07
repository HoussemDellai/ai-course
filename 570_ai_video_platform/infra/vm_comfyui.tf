resource "random_password" "vm_admin" {
  length           = 20
  special          = true
  override_special = "!@#%*-_"
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 1
}

resource "azurerm_public_ip" "pip_vm" {
  name                = "pip-vm-comfyui"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  allocation_method   = "Static"
  sku                 = "Standard"

  lifecycle {
    ignore_changes = [ip_tags]
  }
}

resource "azurerm_network_interface" "nic_vm" {
  name                = "nic-vm-comfyui"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.snet_vm.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.10.1.10"
    public_ip_address_id          = azurerm_public_ip.pip_vm.id
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  name                            = "vm-comfyui"
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  size                            = var.vm_size
  admin_username                  = "azureuser"
  admin_password                  = random_password.vm_admin.result
  disable_password_authentication = false
  network_interface_ids           = [azurerm_network_interface.nic_vm.id]
  priority                        = var.vm_spot ? "Spot" : "Regular"
  eviction_policy                 = var.vm_spot ? "Deallocate" : null
  secure_boot_enabled             = false # the NVIDIA driver install doesn't support Secure Boot

  # Managed OS disk so the ~240 GB of models (with LTX-2.5) survive reboots and Spot deallocations.
  os_disk {
    name                 = "osdisk-vm-comfyui"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 512
  }

  source_image_reference {
    publisher = "canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  boot_diagnostics {
    storage_account_uri = null
  }
}

resource "azurerm_virtual_machine_run_command" "install_nvidia_drivers" {
  name               = "01-install-nvidia-drivers"
  location           = azurerm_linux_virtual_machine.vm.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm.id

  source {
    script = replace(file("${path.module}/scripts/01-install-nvidia-drivers.sh"), "\r\n", "\n")
  }
}

# 01 schedules a reboot one minute after it completes.
resource "time_sleep" "wait_for_reboot" {
  create_duration = "180s"

  triggers = {
    script_hash = filesha256("${path.module}/scripts/01-install-nvidia-drivers.sh")
  }

  depends_on = [azurerm_virtual_machine_run_command.install_nvidia_drivers]
}

resource "azurerm_virtual_machine_run_command" "install_comfyui" {
  name               = "02-install-comfyui"
  location           = azurerm_linux_virtual_machine.vm.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm.id

  source {
    script = replace(file("${path.module}/scripts/02-install-comfyui.sh"), "\r\n", "\n")
  }

  depends_on = [time_sleep.wait_for_reboot]
}

resource "azurerm_virtual_machine_run_command" "download_models" {
  name               = "03-download-models"
  location           = azurerm_linux_virtual_machine.vm.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm.id

  source {
    script = replace(file("${path.module}/scripts/03-download-models.sh"), "\r\n", "\n")
  }

  timeouts {
    create = "3h"
    update = "3h"
  }

  depends_on = [azurerm_virtual_machine_run_command.install_comfyui]
}

# Independent of ComfyUI (02/03): installing or updating the exporter never restarts a running render.
resource "azurerm_virtual_machine_run_command" "install_gpu_stats" {
  name               = "04-install-gpu-stats"
  location           = azurerm_linux_virtual_machine.vm.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm.id

  source {
    script = replace(
      replace(file("${path.module}/scripts/04-install-gpu-stats.sh"), "\r\n", "\n"),
      "__EXPORTER_B64__",
      base64encode(replace(file("${path.module}/scripts/gpu_stats_exporter.py"), "\r\n", "\n"))
    )
  }

  depends_on = [time_sleep.wait_for_reboot]
}

# The Container Apps VNet (italynorth) isn't peered with the VM VNet, so ACA reaches ComfyUI through the VM's public IP.
locals {
  comfyui_url   = "http://${azurerm_public_ip.pip_vm.ip_address}:8188"
  gpu_stats_url = "http://${azurerm_public_ip.pip_vm.ip_address}:8189"
}
