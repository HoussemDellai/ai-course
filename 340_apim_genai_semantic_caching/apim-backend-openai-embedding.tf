resource "azurerm_api_management_backend" "apim-backend-openai-embedding" {
  name                = "apim-backend-openai-embedding"
  resource_group_name = azurerm_resource_group.rg.name # azurerm_api_management.apim.resource_group_name
  api_management_name = azurerm_api_management.apim.name
  protocol            = "http"
  url                 = "${azurerm_ai_services.ai-services.endpoint}openai/deployments/${azurerm_cognitive_deployment.text-embedding-3-large.name}/embeddings"
}