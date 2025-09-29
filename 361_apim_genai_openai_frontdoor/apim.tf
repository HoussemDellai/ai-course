# Terraform azurerm provider doesn't support yet creating API Management instances with stv2 SKU.
resource "azapi_resource" "apim" {
  type                      = "Microsoft.ApiManagement/service@2024-06-01-preview"
  name                      = "apim-std-v2-${random_string.random.result}-${var.prefix}"
  parent_id                 = azurerm_resource_group.rg.id
  location                  = azurerm_resource_group.rg.location
  schema_validation_enabled = true

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = {
      name     = "StandardV2" # "PremiumV2" # PremiumV2 doesn't support yet Private Endpoint
      capacity = 1
    }
    properties = {
      publisherEmail      = "noreply@microsoft.com"
      publisherName       = "My Company"
      virtualNetworkType  = "External" # "Internal" # Setting up 'Internal' Internal Virtual Network Type is not supported for Sku Type 'StandardV2'.
      publicNetworkAccess = "Enabled"  # "Disabled" # Blocking all public network access by setting property `publicNetworkAccess` of API Management service is not enabled during service creation.

      virtualNetworkConfiguration = {
        subnetResourceId = azurerm_subnet.snet-apim.id
      }
    }
  }

  response_export_values = ["*"]
  depends_on             = [azurerm_subnet_network_security_group_association.nsg-association]
}

# # Update APIM's publicNetworkAccess to "Disabled"
# resource "azapi_update_resource" "update-apim-public-network-access" {
#   type        = "Microsoft.ApiManagement/service@2024-06-01-preview"
#   resource_id = azapi_resource.apim.id

#   body = {
#     properties = {
#       publicNetworkAccess = "Disabled"
#     }
#   }
# }

# resource "azurerm_api_management" "apim" {
#   name                          = "apim-genai-${var.prefix}"
#   location                      = azurerm_resource_group.rg.location
#   resource_group_name           = azurerm_resource_group.rg.name
#   publisher_name                = "My Company"
#   publisher_email               = "noreply@microsoft.com"
#   sku_name                      = "Consumption_0" # "Developer_1"
#   virtual_network_type          = "None"          # None, External, Internal
#   public_network_access_enabled = true            # false applies only when using private endpoint as the exclusive access method

#   identity {
#     type = "SystemAssigned"
#   }
# }

resource "azurerm_role_assignment" "Cognitive-Services-OpenAI-User" {
  scope                = azurerm_ai_services.ai-services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azapi_resource.apim.identity.0.principal_id
}
