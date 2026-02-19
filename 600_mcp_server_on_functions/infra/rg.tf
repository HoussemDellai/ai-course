resource "azurerm_resource_group" "rg" {
  name     = "rg-mcp-server-on-functions-${var.prefix}"
  location = "swedencentral"
}