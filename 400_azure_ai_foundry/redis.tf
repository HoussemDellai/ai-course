resource "azurerm_managed_redis" "redis" {
  name                      = "redis-${var.prefix}"
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = azurerm_resource_group.rg.location
  sku_name                  = "Balanced_B1"
  high_availability_enabled = true
  public_network_access     = "Enabled"


  default_database {
    # geo_replication_group_name         = "myGeoGroup"
    access_keys_authentication_enabled = true
    client_protocol                    = "Encrypted"
  }
}

output "redis_hostname" {
  value = azurerm_managed_redis.redis.hostname
}

output "redis_port" {
  value = azurerm_managed_redis.redis.default_database.0.port
}

output "redis_primary_access_key" {
  value     = azurerm_managed_redis.redis.default_database.0.primary_access_key
  sensitive = true
}
