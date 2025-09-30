resource "azurerm_resource_group" "rg" {
  name     = "rg-frontdoor-apim-openai-${random_string.random.result}-${var.prefix}"
  location = "swedencentral" # "westeurope" # azurerm_resource_group.rg.location # APIM SKU StandardV2 is not supported in the region Sweden Central
}