resource "azapi_resource" "function_app" {
  type                      = "Microsoft.Web/sites@2025-03-01"
  name                      = "function-app-mcp-${var.prefix}"
  location                  = azurerm_service_plan.app_service_plan_functions.location
  parent_id                 = azurerm_resource_group.rg.id
  schema_validation_enabled = false

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "functionapp,linux",
    properties = {
      serverFarmId = azurerm_service_plan.app_service_plan_functions.id
      functionAppConfig = {
        deployment = {
          storage = {
            type  = "blobContainer",
            value = "${azurerm_storage_account.storage_functions.primary_blob_endpoint}${azurerm_storage_container.container_functions.name}"
            authentication = {
              type = "SystemAssignedIdentity"
            }
          }
        },
        scaleAndConcurrency = {
          maximumInstanceCount = 40,
          instanceMemoryMB     = 2048,
        },
        runtime = {
          name    = "python",
          version = "3.13",
        }
      },
      siteConfig = {
        appSettings = [
          {
            name  = "AzureWebJobsStorage__accountName",
            value = azurerm_storage_account.storage_functions.name
          },
          {
            name  = "APPLICATIONINSIGHTS_CONNECTION_STRING",
            value = azurerm_application_insights.app_insights.connection_string
          }
          # {
          #   name  = "APPLICATIONINSIGHTS_AUTHENTICATION_STRING",
          #   value = "Authorization=AAD;ClientId=${azapi_resource.function_app.identity[0].principal_id}"
          # }
        ]
      }
    }
  }

  response_export_values = ["id", "name", "location", "identity", "properties.defaultHostName"]
}

resource "azurerm_role_assignment" "storage_roleassignment" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azapi_resource.function_app.identity[0].principal_id
}

# get the system keys for the function app
data "azapi_resource_action" "function_app_system_keys" {
  type        = "Microsoft.Web/sites/host@2024-04-01"
  resource_id = "${azapi_resource.function_app.id}/host/default"
  action      = "listkeys"
  method      = "POST"

  response_export_values = ["*"]
}

output "functions_hostname" {
  value = azapi_resource.function_app.output.properties.defaultHostName
}

output "function_app_system_keys_mcp_extension" {
  value     = try(data.azapi_resource_action.function_app_system_keys.output.systemKeys.mcp_extension, "")
  sensitive = true
}
