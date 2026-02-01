resource "azurerm_virtual_machine_run_command" "run_command_install_nvidia_drivers" {
  name               = "run-command-install-nvidia-drivers"
  location           = azurerm_linux_virtual_machine.vm_linux.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm_linux.id

  source {
    script = file("./01-install-nvidia-drivers.sh")
  }
}

# wait for reboot to complete before running next command, about 20 seconds
resource "time_sleep" "wait_20_seconds" {
  create_duration = "20s"

  depends_on = [azurerm_virtual_machine_run_command.run_command_install_nvidia_drivers]
}

resource "azurerm_virtual_machine_run_command" "run_command_install_comfyui" {
  name               = "run-command-install-comfyui"
  location           = azurerm_linux_virtual_machine.vm_linux.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm_linux.id

  source {
    script = file("./02-install-comfyui.sh")
  }

  depends_on = [time_sleep.wait_20_seconds]
}

resource "azurerm_virtual_machine_run_command" "run_command_download_models" {
  name               = "run-command-download-models"
  location           = azurerm_linux_virtual_machine.vm_linux.location
  virtual_machine_id = azurerm_linux_virtual_machine.vm_linux.id

  source {
    script = file("./download-models.sh")
  }

  depends_on = [azurerm_virtual_machine_run_command.run_command_install_comfyui]
}