resource "azapi_resource" "ai-services-connection" {
  type      = "Microsoft.MachineLearningServices/workspaces/connections@2024-07-01-preview"
  name      = "ai-service-connection"
  parent_id = azurerm_ai_foundry.ai-foundry-hub.id

  body = {
    properties = {
      category      = "AIServices",
      target        = azurerm_ai_services.ai-services.endpoint,
      authType      = "AAD",
      isSharedToAll = true,

      metadata = {
        ApiType    = "Azure",
        ResourceId = azurerm_ai_services.ai-services.id
      }
    }
  }

  response_export_values = ["*"]
}

resource "azapi_resource" "search-service-connection" {
  type      = "Microsoft.MachineLearningServices/workspaces/connections@2024-07-01-preview"
  name      = "search-service-connection"
  parent_id = azurerm_ai_foundry.ai-foundry-hub.id

  body = {
    properties = {
      category      = "CognitiveSearch"
      target        = "${azurerm_search_service.search-service.name}.search.windows.net"
      authType      = "AAD"
      isSharedToAll = true

      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_search_service.search-service.id
      }
    }
  }
}

# resource "azapi_resource" "storage-account-connection" {
#   type      = "Microsoft.MachineLearningServices/workspaces/datastores@2025-01-01-preview"
#   name      = "storage-account-connection"
#   parent_id = azurerm_ai_foundry.ai-foundry-hub.id

#   body = {
#     properties = {
#       category      = "AzureStorageAccount"
#       datastoreType = "AzureBlob"
#       target        = azurerm_storage_account.storage.id
#       authType      = "AccountKey"
#       isSharedToAll = true

#       metadata = {
#         ApiType    = "Azure"
#         ResourceId = azurerm_storage_account.storage.id
#       }

#       credentials = {
#         key = azurerm_storage_account.storage.primary_access_key
#       }
#     }
#   }
# }

# // Creates the Azure Foundry connection to your Azure Storage account
# resource connection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
#   name: '${aiFoundryName}-storage'
#   parent: aiFoundry
#   properties: {
#     category: 'AzureStorageAccount'
#     target: ((newOrExisting == 'new') ? newStorage.id : existingStorage.id)
#     authType: 'AccountKey'
#     isSharedToAll: true
#     credentials: {
#       key: string((newOrExisting == 'new') ? newStorage.listKeys().keys : existingStorage.listKeys().keys)
#     }
#     metadata: {
#       ApiType: 'Azure'
#       ResourceId: ((newOrExisting == 'new') ? newStorage.id : existingStorage.id)
#     }
#   }
# }