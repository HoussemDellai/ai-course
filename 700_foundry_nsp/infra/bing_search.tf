resource "azapi_resource" "bing_search" {
  type                      = "Microsoft.Bing/accounts@2025-05-01-preview"
  parent_id                 = azurerm_resource_group.rg.id
  name                      = "bing-search-270"
  location                  = "global"
  schema_validation_enabled = false

  body = {
    kind = "Bing.Grounding"
    # properties = {
    #   endpoint          = "https://api.bing.microsoft.com/"
    #   internalId        = "64f3200655aa44078d82b223fce1cce3"
    #   provisioningState = "Succeeded"
    #   statisticsEnabled = false
    # }
    sku = {
      name = "G1"
    }
  }
}

resource "azapi_resource" "bing_search_custom" {
  type                      = "Microsoft.Bing/accounts@2025-05-01-preview"
  parent_id                 = azurerm_resource_group.rg.id
  name                      = "bing-search-custom"
  location                  = "global"
  schema_validation_enabled = false
  response_export_values    = ["*"]

  body = {
    kind = "Bing.GroundingCustomSearch"
    # properties = {
    #   endpoint          = "https://api.bing.microsoft.com/"
    #   internalId        = "8bd2dba0e2964d058853d23eb44bc095"
    #   provisioningState = "Succeeded"
    #   statisticsEnabled = false
    # }
    sku = {
      name = "G2"
    }
  }
}

# role assignment: Azure AI Owner role to create Foundry connections to Bing resources.
resource "azurerm_role_assignment" "ai-owner-bing-search" {
  scope                = azapi_resource.bing_search_custom.id
  role_definition_name = "Azure AI Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azapi_resource" "configuration_bing_search_custom" {
  type                      = "Microsoft.Bing/accounts/customSearchConfigurations@2025-05-01-preview"
  name                      = "configuration-bing-search-custom"
  parent_id                 = azapi_resource.bing_search_custom.id
  schema_validation_enabled = false

  body = {
    properties = {
      allowedDomains = [
        {
          boostLevel      = "Boosted"
          domain          = "microsoft.com"
          includeSubPages = true
        },
        {
          boostLevel      = "Boosted"
          domain          = "github.com"
          includeSubPages = true
        },
        {
          boostLevel      = "Boosted"
          domain          = "learn.microsoft.com"
          includeSubPages = true
        },
        {
          boostLevel      = "Boosted"
          domain          = "techcommunity.microsoft.com"
          includeSubPages = true
        },
      ]
      blockedDomains = [
        {
          domain          = "wikipedia.org"
          includeSubPages = true
        }
      ]
    }
  }
}

output "bing_search_custom_name" {
  value = azapi_resource.bing_search_custom.name
}

output "connection_id_bing_search_custom" {
  value = azapi_resource.connection_bing_search_custom.id
}

output "keys_bing_search_custom" {
  value     = data.azapi_resource_action.keys_bing_search_custom.sensitive_output
  sensitive = true
}