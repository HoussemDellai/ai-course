resource "azurerm_resource_group" "rg" {
  name     = "rg-aca-gpu-nvidia-${var.prefix}"
  location = "swedencentral"
}