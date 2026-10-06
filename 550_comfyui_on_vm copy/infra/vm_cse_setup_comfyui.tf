# # Optional: Install NVIDIA GPU Drivers using Custom Script Extension
# # The extension will not wait for the script to complete, so we add a time_sleep and reboot command afterwards
# resource "azurerm_virtual_machine_extension" "cse_install_nvidia_drivers" {
#   name                       = "cse-install-nvidia-drivers"
#   virtual_machine_id         = azurerm_linux_virtual_machine.vm_linux.id
#   publisher                  = "Microsoft.HpcCompute"
#   type                       = "NvidiaGpuDriverLinux"
#   type_handler_version       = "1.9"
#   auto_upgrade_minor_version = true
# }

# # wait for reboot to complete before running next command
# resource "time_sleep" "wait_for_nvidia_gpu_install_and_reboot" {
#   create_duration = "60s"

#   depends_on = [azurerm_virtual_machine_extension.cse_install_nvidia_drivers]
# }

# resource "azurerm_virtual_machine_run_command" "run_command_install_comfyui" {
#   name               = "run-command-install-comfyui"
#   location           = azurerm_linux_virtual_machine.vm_linux.location
#   virtual_machine_id = azurerm_linux_virtual_machine.vm_linux.id

#   source {
#     script = file("./02-install-comfyui.sh")
#   }

#   depends_on = [time_sleep.wait_for_nvidia_gpu_install_and_reboot]
# }

# resource "azurerm_virtual_machine_run_command" "run_command_download_models" {
#   name               = "run-command-download-models"
#   location           = azurerm_linux_virtual_machine.vm_linux.location
#   virtual_machine_id = azurerm_linux_virtual_machine.vm_linux.id

#   source {
#     script = file("./03-download-models.sh")
#   }

#   depends_on = [azurerm_virtual_machine_run_command.run_command_install_comfyui]
# }