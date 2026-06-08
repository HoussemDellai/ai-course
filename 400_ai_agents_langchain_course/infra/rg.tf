resource "azurerm_resource_group" "rg" {
  name     = "rg-ai-agents-langchain-${var.prefix}"
  location = "swedencentral"
}