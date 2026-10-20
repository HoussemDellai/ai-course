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

output "gpu_stats_url" {
  value = local.gpu_stats_url
}

output "model_download_job" {
  value = azurerm_container_app_job.aca_job_download_models.name
}

output "aca_environment" {
  value = azurerm_container_app_environment.aca_environment.name
}

output "comfyui_app" {
  value = azurerm_container_app.comfyui["primary"].name
}

output "comfyui_urls" {
  value = local.comfyui_urls
}

output "gpu_stats_urls" {
  value = local.comfyui_urls
}

output "comfyui_apps" {
  value = [for key in sort(keys(local.comfyui_workers)) : azurerm_container_app.comfyui[key].name]
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "subscription_id" {
  value = var.subscription_id
}

output "aca_location" {
  value = var.aca_location
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
