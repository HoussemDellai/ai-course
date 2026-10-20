resource "azurerm_resource_group" "rg" {
  name     = "rg-aca-gpu-nvidia-comfyui-mcp-${var.prefix}"
  location = var.location
}