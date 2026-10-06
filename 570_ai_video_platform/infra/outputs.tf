output "resource_group" {
  value = azurerm_resource_group.rg.name
}

output "app_url" {
  value = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "api_key" {
  value     = random_password.api_key.result
  sensitive = true
}

output "comfyui_url" {
  value = local.comfyui_url
}

output "vm_public_ip" {
  value = azurerm_public_ip.pip_vm.ip_address
}

output "vm_admin_password" {
  value     = random_password.vm_admin.result
  sensitive = true
}

output "ssh_tunnel_to_comfyui" {
  description = "Open the ComfyUI UI on http://localhost:8188 through an SSH tunnel."
  value       = "ssh -L 8188:localhost:8188 azureuser@${azurerm_public_ip.pip_vm.ip_address}"
}

output "foundry_project_endpoint" {
  value = azurerm_cognitive_account_project.project.endpoints["AI Foundry API"]
}

output "llm_deployment_name" {
  value = azurerm_cognitive_deployment.llm.name
}

output "speech_endpoint" {
  value = azurerm_cognitive_account.foundry.endpoint
}

output "storage_account_url" {
  value = azurerm_storage_account.storage.primary_blob_endpoint
}

output "storage_container" {
  value = azurerm_storage_container.videos.name
}
