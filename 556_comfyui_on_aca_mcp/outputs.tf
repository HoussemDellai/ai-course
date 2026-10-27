output "comfyui_url" {
  value = "https://${azurerm_container_app.aca_comfyui_cu130_a100.ingress[0].fqdn}"
}

output "mcp_url" {
  value = "https://${azurerm_container_app.comfyui_mcp.ingress[0].fqdn}/mcp"
}
