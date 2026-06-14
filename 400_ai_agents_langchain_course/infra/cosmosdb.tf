resource "azurerm_cosmosdb_account" "cosmosdb" {
  name                = "cosmosdb-agent-memory-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }

  capabilities {
    name = "EnableServerless"
  }

  tags = {
    SecurityControl = "Ignore"
  }
}

output "cosmosdb_endpoint" {
  value = azurerm_cosmosdb_account.cosmosdb.endpoint
}

output "cosmosdb_key" {
  value     = azurerm_cosmosdb_account.cosmosdb.primary_key
  sensitive = true
}
