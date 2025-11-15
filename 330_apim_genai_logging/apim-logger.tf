resource "azurerm_api_management_logger" "apim-logger" {
  name                = "apim-logger"
  api_management_name = azurerm_api_management.apim.name
  resource_group_name = azurerm_api_management.apim.resource_group_name
  buffered            = false
  resource_id         = azurerm_application_insights.app-insights.id

  application_insights {
    connection_string = azurerm_application_insights.app-insights.connection_string
  }
}

# resource "azapi_update_resource" "enable-apim-logger-managed-identity" {
#   type        = "Microsoft.ApiManagement/service/loggers@2022-08-01"
#   resource_id = azurerm_api_management_logger.apim-logger.id

#   body = {
#     properties = {
#       credentials = {
#         # identityClientId = "systemAssigned"
#         instrumentationKey = azurerm_application_insights.app-insights.instrumentation_key
#       }
#     }
#   }
# }
