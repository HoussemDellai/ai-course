# Terraform azurerm provider doesn't support yet creating API Management instances with stv2 SKU.
resource "azapi_resource" "apim" {
  type                      = "Microsoft.ApiManagement/service@2024-06-01-preview"
  name                      = "apim-genai-basicv2-${var.prefix}"
  parent_id                 = azurerm_resource_group.rg.id
  location                  = "westeurope" # azurerm_resource_group.rg.location # SKU BasicV2 is not supported in the region Sweden Central
  schema_validation_enabled = true

  identity {
    type = "SystemAssigned"
  }

  body = {
    sku = {
      name     = "BasicV2"
      capacity = 1
    }
    properties = {
      publisherEmail      = "noreply@microsoft.com"
      publisherName       = "My Company"
      virtualNetworkType  = "None"
      publicNetworkAccess = "Enabled"
    }
  }

  response_export_values = ["*"]
}

# resource "azurerm_api_management" "apim" {
#   name                          = "apim-genai-basic-v2-${var.prefix}"
#   location                      = azurerm_resource_group.rg.location
#   resource_group_name           = azurerm_resource_group.rg.name
#   publisher_name                = "My Company"
#   publisher_email               = "noreply@microsoft.com"
#   sku_name                      = "BasicV2_1" # Consumption, Developer, Basic, BasicV2, Standard, StandardV2, Premium and PremiumV2
#   virtual_network_type          = "None"    # None, External, Internal
#   public_network_access_enabled = true      # false applies only when using private endpoint as the exclusive access method

#   identity {
#     type = "SystemAssigned"
#   }
# }

resource "azurerm_role_assignment" "Cognitive-Services-OpenAI-User" {
  scope                = azurerm_ai_services.ai-services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azapi_resource.apim.identity.0.principal_id
}
