output "azure_openai_endpoint" {
  value = azurerm_ai_services.ai-services.endpoint
}

output "azure_openai_api_key" {
  value     = azurerm_ai_services.ai-services.primary_access_key
  sensitive = true
}

output "azure_openai_deployment_name" {
  value = azurerm_cognitive_deployment.gpt-4o.name
}

output "azure_openai_embedding_model" {
  value = azurerm_cognitive_deployment.text-embedding-3-large.name
}

output "azure_search_service_endpoint" {
  value = "https://${azurerm_search_service.search-service.name}.search.windows.net"
}

output "azure_search_service_admin_key" {
  value     = azurerm_search_service.search-service.primary_key
  sensitive = true
}

# output "ai_foundry_project_connection_string" {
#   value     = azurerm_ai_foundry_project.project.primary_blob_connection_string
#   sensitive = true 
# }

output "dot_env" {
  sensitive = true
  value     = <<EOT
AZURE_OPENAI_ENDPOINT=${azurerm_ai_services.ai-services.endpoint}
AZURE_OPENAI_API_KEY=${azurerm_ai_services.ai-services.primary_access_key}
AZURE_OPENAI_DEPLOYMENT_NAME=${azurerm_cognitive_deployment.gpt-4o.name}
AZURE_OPENAI_API_VERSION=2024-11-20
AZURE_OPENAI_EMBEDDING_MODEL=${azurerm_cognitive_deployment.text-embedding-3-large.name}
EMBEDDING_VECTOR_DIMENSIONS=3072
AZURE_SEARCH_SERVICE_ENDPOINT=https://${azurerm_search_service.search-service.name}.search.windows.net
AZURE_SEARCH_SERVICE_ADMIN_KEY=${azurerm_search_service.search-service.primary_key}
SEARCH_INDEX_NAME=index-doc
EOT
}
