resource "azurerm_cognitive_account" "foundry" {
  name                               = "foundry-${var.prefix}"
  location                           = azurerm_resource_group.rg.location
  resource_group_name                = azurerm_resource_group.rg.name
  kind                               = "AIServices"
  sku_name                           = "S0"
  project_management_enabled         = true
  custom_subdomain_name              = "foundry-${var.prefix}"
  local_auth_enabled                 = true # false # true
  public_network_access_enabled      = true
  outbound_network_access_restricted = false

  identity {
    type = "SystemAssigned"
  }

  tags = {
    SecurityControl = "Ignore"
  }
}

# resource "azurerm_role_assignment" "foundry_project_openai_user" {
#   scope                = azurerm_container_registry.acr.id
#   role_definition_name = "Cognitive Services OpenAI User"
#   principal_id         = azurerm_cognitive_account_project.project.identity.0.principal_id
# }

# resource "azurerm_role_assignment" "ai-services" {
#   scope                = azurerm_cognitive_account.foundry.id
#   role_definition_name = "Cognitive Services OpenAI Contributor" # "Cognitive Services OpenAI User"
#   principal_id         = data.azurerm_client_config.current.object_id
# }

# # Azure AI User
# resource "azurerm_role_assignment" "ai-user" {
#   scope                = azurerm_cognitive_account.foundry.id
#   role_definition_name = "Azure AI User"
#   principal_id         = data.azurerm_client_config.current.object_id
# }

# # Azure AI Project Manager
# resource "azurerm_role_assignment" "ai-project-manager" {
#   scope                = azurerm_cognitive_account_project.project.id
#   role_definition_name = "Azure AI Project Manager"
#   principal_id         = data.azurerm_client_config.current.object_id
# }

# # # Your project, "ai-project" does not have permission to access the connected Azure OpenAI resource because its connection is set to use role-based authentication. To resolve this issue, you can either assign the role of Azure AI Developer to your project for the resource, or change the connection's authentication method to use an API key and try again. If you recently added the role, it could take up to 15 minutes for the roles to update.
# # resource "azurerm_role_assignment" "azure-ai-developer-project-on-ai-services" {
# #   scope                = azurerm_ai_services.ai-services.id
# #   role_definition_name = "Azure AI Developer"
# #   principal_id         = azurerm_ai_foundry_project.ai-foundry-project.identity.0.principal_id # azapi_resource.project.identity.0.principal_id
# # }

## Added AI Foundry account purger to avoid running into InUseSubnetCannotBeDeleted-lock caused by the agent subnet delegation.
## The azapi_resource_action.purge_ai_foundry (only gets executed during destroy) purges the AI foundry account removing /subnets/snet-agent/serviceAssociationLinks/legionservicelink so the agent subnet can get properly removed.
resource "azapi_resource_action" "purge_ai_foundry" {
  method      = "DELETE"
  resource_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/providers/Microsoft.CognitiveServices/locations/${azurerm_resource_group.rg.location}/resourceGroups/${azurerm_resource_group.rg.name}/deletedAccounts/foundry-${var.prefix}"
  type        = "Microsoft.Resources/resourceGroups/deletedAccounts@2021-04-30"
  when        = "destroy"

  depends_on = [time_sleep.purge_ai_foundry_cooldown]
}

resource "time_sleep" "purge_ai_foundry_cooldown" {
  destroy_duration = "900s" # 10-15m is enough time to let the backend remove the /subnets/snet-agent/serviceAssociationLinks/legionservicelink

  # depends_on = [azurerm_subnet.subnet_agent]
}

output "foundry_name" {
  value = azurerm_cognitive_account.foundry.name
}

output "foundry_endpoint" {
  value = azurerm_cognitive_account.foundry.endpoint
}

output "foundry_api_key" {
  value     = azurerm_cognitive_account.foundry.primary_access_key
  sensitive = true
}
