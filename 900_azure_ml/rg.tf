resource "azurerm_resource_group" "rg" {
  name     = "rg-aml-${var.prefix}"
  location = "swedencentral" # "eastus" # "swedencentral"
}