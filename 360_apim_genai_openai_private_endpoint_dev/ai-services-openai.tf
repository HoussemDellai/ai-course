resource "azurerm_ai_services" "ai-services" {
  name                               = "ai-services-${random_string.random.result}-${var.prefix}"
  location                           = azurerm_resource_group.rg.location
  resource_group_name                = azurerm_resource_group.rg.name
  sku_name                           = "S0"
  local_authentication_enabled       = true
  public_network_access              = "Disabled" # "Enabled"
  outbound_network_access_restricted = false
  custom_subdomain_name              = "ai-services-${random_string.random.result}-${var.prefix}"
}

resource "azurerm_cognitive_deployment" "gpt-4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 20
  }

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-08-06" # "2024-11-20"
  }
}