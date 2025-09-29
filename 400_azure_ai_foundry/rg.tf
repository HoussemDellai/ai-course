resource "azurerm_resource_group" "rg" {
  name     = "rg-ai-foundry-${random_string.random.result}-${var.prefix}"
  location = "swedencentral" # "eastus" # "swedencentral"
}