# resource "azapi_resource" "function_app" {
#   type                      = "Microsoft.Web/sites@2025-03-01"
#   name                      = "function-app-mcp-${var.prefix}-azapi"
#   location                  = azurerm_service_plan.app_service_plan_functions.location
#   parent_id                 = azurerm_resource_group.rg.id
#   schema_validation_enabled = false

#   identity {
#     type         = "UserAssigned"
#     identity_ids = [azurerm_user_assigned_identity.identity_function_app.id]
#   }

#   body = {
#     kind = "functionapp,linux",
#     properties = {
#       serverFarmId = azurerm_service_plan.app_service_plan_functions.id
#       functionAppConfig = {
#         deployment = {
#           storage = {
#             type  = "blobContainer",
#             value = "${azurerm_storage_account.storage_functions.primary_blob_endpoint}${azurerm_storage_container.container_functions.name}"
#             authentication = {
#               type                           = "UserAssignedIdentity"
#               userAssignedIdentityResourceId = azurerm_user_assigned_identity.identity_function_app.id
#             }
#           }
#         },
#         scaleAndConcurrency = {
#           maximumInstanceCount = 40,
#           instanceMemoryMB     = 2048,
#         },
#         runtime = {
#           name    = "python",
#           version = "3.13",
#         }
#       },
#       siteConfig = {
#         appSettings = [
#           {
#             name  = "AzureWebJobsStorage__accountName",
#             value = azurerm_storage_account.storage_functions.name
#           },
#           {
#             name  = "APPLICATIONINSIGHTS_AUTHENTICATION_STRING",
#             value = "Authorization=AAD;ClientId=${azurerm_user_assigned_identity.identity_function_app.client_id}"
#           }
#           # {
#           #   name  = "APPLICATIONINSIGHTS_CONNECTION_STRING",
#           #   value = azurerm_application_insights.appInsights.connection_string
#           # }
#         ]
#       }
#     }
#   }
#   # depends_on = [azapi_resource.serverFarm, azurerm_application_insights.appInsights, azurerm_storage_account.storage]
# }
