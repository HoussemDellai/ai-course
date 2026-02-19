resource "azurerm_resource_group" "rg" {
  name     = "rg-mcp-server-functions-${var.prefix}"
  location = "swedencentral"
}