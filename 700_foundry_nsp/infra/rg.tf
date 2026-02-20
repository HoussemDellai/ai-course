resource "azurerm_resource_group" "rg" {
  name     = "rg-foundry-${var.prefix}"
  location = "swedencentral" # "northcentralus" # 
}