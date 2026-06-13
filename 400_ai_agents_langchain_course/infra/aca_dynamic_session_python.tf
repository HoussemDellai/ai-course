resource "azapi_resource" "aca_session_pool_python" {
  type                      = "Microsoft.App/sessionPools@2025-02-02-preview"
  parent_id                 = azurerm_resource_group.rg.id
  name                      = "aca-sessionpool-python"
  location                  = azurerm_resource_group.rg.location
  schema_validation_enabled = false
  response_export_values    = ["properties.poolManagementEndpoint", "properties.mcpServerSettings.mcpServerEndpoint"]

   body = {
    properties = {
      containerType      = "PythonLTS"
      poolManagementType = "Dynamic"

      dynamicPoolConfiguration = {
        lifecycleConfiguration = {
          lifecycleType           = "Timed"
          coolDownPeriodInSeconds = 300
        }
      }

      scaleConfiguration = {
        maxConcurrentSessions = 5
      }

      sessionNetworkConfiguration = {
        status = "EgressEnabled"
      }

      mcpServerSettings = {
        isMCPServerEnabled = true # Add the "mcpServerSettings" section to enable the MCP server
      }
    }
  }
}

# role assignment to allow ACA environment to use the session pool
# Azure Container Apps Session Executor
resource "azurerm_role_assignment" "aca_session_pool_python_contributor" {
  scope                = azapi_resource.aca_session_pool_python.id
  role_definition_name = "Azure ContainerApps Session Executor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# # Get MCP server credentials
# # The platform-managed MCP server uses API key authentication through the x-ms-apikey header. 
# # This authentication method differs from the bearer-token authentication that standard session pool management APIs use.
# # API_KEY=$(az rest --method POST --uri "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/sessionPools/$SESSION_POOL_NAME/fetchMCPServerCredentials" --uri-parameters api-version=2025-10-02-preview --query "apiKey" -o tsv)
# data "azapi_resource_action" "sessionpool_apikey" {
#   type        = "Microsoft.App/sessionPools@2025-02-02-preview"
#   resource_id = azapi_resource.aca_session_pool_python.id
#   action      = "fetchMCPServerCredentials"
#   method      = "POST"

#   response_export_values = ["*"]
# }

# output "sessionpool_apikey" {
#   value     = try(data.azapi_resource_action.sessionpool_apikey.output.apiKey, "")
#   sensitive = true
# }

output "sessionpool_management_endpoint_python" {
  value = azapi_resource.aca_session_pool_python.output.properties.poolManagementEndpoint
}

output "sessionpool_mcp_endpoint_python" {
  value = azapi_resource.aca_session_pool_python.output.properties.mcpServerSettings.mcpServerEndpoint
}