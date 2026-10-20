output "subscription_id" {
  value = var.subscription_id
}
output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}
output "environment_name" {
  value = azurerm_container_app_environment.aca_environment.name
}
output "acr_name" {
  value = azurerm_container_registry.mcp.name
}
output "acr_login_server" {
  value = azurerm_container_registry.mcp.login_server
}
output "comfyui_url" {
  value = "https://${azurerm_container_app.aca_comfyui_cu130_a100.ingress[0].fqdn}"
}
output "mcp_url" {
  value = var.enable_mcp ? "https://${azurerm_container_app.mcp[0].ingress[0].fqdn}/mcp" : null
}
output "portal_url" {
  value = "https://portal.azure.com/#@/resource${azurerm_resource_group.rg.id}/overview"
}
