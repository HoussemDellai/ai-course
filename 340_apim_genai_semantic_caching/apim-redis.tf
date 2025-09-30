resource "azurerm_api_management_redis_cache" "apim-redis" {
  name              = "Default"
  api_management_id = azurerm_api_management.apim.id
  connection_string = "${azurerm_container_app.aca-redis-stack.name}.${azurerm_container_app_environment.aca-env.default_domain}:6379" # azurerm_redis_cache.redis.primary_connection_string # azurerm_container_app.aca-redis-stack.name # 
  description       = "Redis cache instances"
#   redis_cache_id    = azurerm_redis_cache.redis.id
#   cache_location    = azurerm_resource_group.rg.location
}