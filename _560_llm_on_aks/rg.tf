resource "azurerm_resource_group" "rg" {
  name     = "rg-aks-gpu-nvidia-${var.prefix}"
  location = "swedencentral"
}