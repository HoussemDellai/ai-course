
# List keys for the Bing Account resource
data "azapi_resource_action" "keys_bing_search_custom" {
  type        = "microsoft.bing/accounts@2025-05-01-preview"
  resource_id = azapi_resource.bing_search_custom.id
  action      = "listKeys"
  method      = "POST"

  sensitive_response_export_values = ["key1", "key2"]
}

resource "azapi_resource" "connection_bing_search_custom" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01"
  name                      = "connection-bing-custom-search"
  parent_id                 = azurerm_cognitive_account_project.project.id
  schema_validation_enabled = false

  body = {
    name = "connection-bing-custom-search"
    properties = {
      category = "GroundingWithCustomSearch"
      target   = "https://api.bing.microsoft.com/"
      authType = "ApiKey" # AuthType for GroundingWithCustomSearch Connection can only be ApiKey
      metadata = {
        ApiType    = "Azure"
        ResourceId = azapi_resource.bing_search_custom.id
        location   = azurerm_resource_group.rg.location
      }
    }
  }

  sensitive_body = {
    properties = {
      credentials = {
        key = data.azapi_resource_action.keys_bing_search_custom.sensitive_output.key1
      }
    }
  }
}

resource "azapi_resource" "connection_foundry_app_insights" {
  count                     = 0
  type                      = "Microsoft.CognitiveServices/accounts/connections@2025-06-01"
  name                      = "connection-foundry-app-insights"
  parent_id                 = azurerm_cognitive_account.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      authType                    = "ApiKey",
      category                    = "AppInsights",
      target                      = azurerm_application_insights.app_insights.id,
      useWorkspaceManagedIdentity = false,
      isSharedToAll               = false,
      sharedUserList              = [],
      peRequirement               = "NotRequired",
      peStatus                    = "NotApplicable",
    }
  }
  sensitive_body = {
    properties = {
      credentials = {
        key = azurerm_application_insights.app_insights.instrumentation_key
      }
    }
  }
}
