# NOTE: Azure Functions Flex Consumption (FC1) does NOT support custom Docker
# container images (code-package deployment only). To run the same container as
# the Container App, an Elastic Premium (EP1) plan is used, which is the
# Functions plan that supports custom Linux containers.

resource "azurerm_service_plan" "function_plan" {
  name                = "function-mcp-web-search-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "EP1" # Elastic Premium (supports custom containers)
}

resource "azurerm_storage_account" "function_storage" {
  name                      = "stfuncmcpwebsearch${var.prefix}"
  location                  = azurerm_resource_group.rg.location
  resource_group_name       = azurerm_resource_group.rg.name
  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = true

  tags = {
    SecurityControl = "Ignore"
  }
}

resource "azurerm_linux_function_app" "mcp_server_open_web_search" {
  name                       = "func-mcp-server-web-search-${var.prefix}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  service_plan_id            = azurerm_service_plan.function_plan.id
  storage_account_name       = azurerm_storage_account.function_storage.name
  storage_account_access_key = azurerm_storage_account.function_storage.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      docker {
        registry_url = "https://ghcr.io"
        image_name   = "aas-ee/open-web-search"
        image_tag    = "v2.1.10"
      }
    }
  }

  app_settings = {
    # Tells the platform which port the container listens on (same as ACA target_port)
    "WEBSITES_PORT" = "3000"

    # Same environment variables as the Container App
    "DEFAULT_SEARCH_ENGINE"  = "startpage"            # bing, duckduckgo, exa, brave, baidu, csdn, juejin, startpage
    "ALLOWED_SEARCH_ENGINES" = "duckduckgo,startpage" # empty (all available) or comma-separated list of allowed engines
    "ENABLE_CORS"            = "true"
    "CORS_ORIGIN"            = "*"
    "PORT"                   = "3000" # 1-65535
  }
}

output "function_mcp_server_open_web_search_fqdn" {
  value = azurerm_linux_function_app.mcp_server_open_web_search.default_hostname
}
