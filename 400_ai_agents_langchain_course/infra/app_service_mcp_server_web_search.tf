resource "azurerm_service_plan" "app_service_plan_mcp_server" {
  name                = "app-service-plan-mcp-server"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1" # B1 (basic) is cheap; use P0v3/P1v3 for production
}

resource "azurerm_linux_web_app" "mcp_server_open_web_search" {
  name                = "mcp-open-web-search" # must be globally unique
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.app_service_plan_mcp_server.id
  https_only          = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true # keep the container warm (requires Basic SKU or higher)

    application_stack {
      docker_image_name   = "aas-ee/open-web-search:v2.1.11" # check here for newer versions: https://github.com/Aas-ee/open-webSearch/pkgs/container/open-web-search
      docker_registry_url = "https://ghcr.io"
    }
  }

  app_settings = {
    # Tell App Service which port the container listens on
    WEBSITES_PORT = "3000"

    DEFAULT_SEARCH_ENGINE  = "startpage"            # bing, duckduckgo, exa, brave, baidu, csdn, juejin, startpage
    ALLOWED_SEARCH_ENGINES = "duckduckgo,startpage" # empty (all available) or comma-separated list of allowed engines
    ENABLE_CORS            = "true"
    CORS_ORIGIN            = "*"
    PORT                   = "3000" # 1-65535
  }
}

output "app_service_mcp_server_open_web_search_fqdn" {
  value = azurerm_linux_web_app.mcp_server_open_web_search.default_hostname
}
