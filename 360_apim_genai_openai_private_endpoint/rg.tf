resource "azurerm_resource_group" "rg" {
  name     = "rg-apim-genai-openai-pe-${var.prefix}"
  location = "swedencentral" # azurerm_resource_group.rg.location # APIM SKU StandardV2 is not supported in the region Sweden Central
}