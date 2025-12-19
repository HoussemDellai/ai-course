resource "azurerm_ai_services" "ai-services" {
  name                               = "ai-services"
  location                           = azurerm_resource_group.rg.location
  resource_group_name                = azurerm_resource_group.rg.name
  sku_name                           = "S0" # F0, F1, S0, S, S1, S2, S3, S4, S5, S6, P0, P1, P2, E0 and DC0.
  local_authentication_enabled       = true
  public_network_access              = "Enabled"
  outbound_network_access_restricted = false
  custom_subdomain_name              = "ai-services-${random_string.random.result}-${var.prefix}"
  # fqdns                              = [] # (Optional) List of FQDNs allowed for the AI Services Account.

  tags = {
    SecurityControl = "Ignore"
    CostControl     = "Ignore"
  }
}
