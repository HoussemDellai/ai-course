resource "azurerm_resource_group" "rg" {
  name     = "rg-apim-genai-openai-lb-${var.prefix}"
  location = "swedencentral"
}