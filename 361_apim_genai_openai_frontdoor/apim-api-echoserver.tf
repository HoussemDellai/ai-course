resource "azurerm_api_management_api" "api-myip" {
  name                  = "api-myip"
  resource_group_name   = azurerm_resource_group.rg.name
  api_management_name   = azurerm_api_management.apim.name
  revision              = "1"
  display_name          = "MyIP API"
  path                  = "ip"
  api_type              = "http" # graphql, http, soap, and websocket
  protocols             = ["http", "https"]
  service_url           = "https://ifconfig.me/ip"
  subscription_required = false
}

resource "azurerm_api_management_api_operation" "operation-myip-get" {
  operation_id        = "api-myip-get"
  api_name            = azurerm_api_management_api.api-myip.name
  api_management_name = azurerm_api_management_api.api-myip.api_management_name
  resource_group_name = azurerm_api_management_api.api-myip.resource_group_name
  display_name        = "MyIP API GET"
  method              = "GET"
  url_template        = "/"
  description         = "GET returns IP used by APIM for outbound traffic."
}