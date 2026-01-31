# resource "azurerm_virtual_machine_extension" "cse_install_nvidia_drivers" {
#   name                 = "cse-install-nvidia-drivers"
#   virtual_machine_id   = azurerm_linux_virtual_machine.vm_linux.id
#   publisher            = "Microsoft.Azure.Extensions"
#   type                 = "CustomScript"
#   type_handler_version = "2.0"

#   settings = <<SETTINGS
#   {
#     "commandToExecute": "hostname && uptime"
#   }
# SETTINGS
# }
