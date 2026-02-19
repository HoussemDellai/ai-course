resource "azurerm_service_plan" "app_service_plan_functions" {
  name                = "app-service-plan-functions"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku_name            = "FC1"
  os_type             = "Linux"
}

resource "azurerm_function_app_flex_consumption" "function_app" {
  name                          = "function-app-mcp-${var.prefix}"
  resource_group_name           = azurerm_resource_group.rg.name
  location                      = azurerm_resource_group.rg.location
  service_plan_id               = azurerm_service_plan.app_service_plan_functions.id
  public_network_access_enabled = true
  virtual_network_subnet_id     = null # Set to your subnet ID if you want to integrate with a VNet
  https_only                    = true
  webdeploy_publish_basic_authentication_enabled = false

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${azurerm_storage_account.storage_functions.primary_blob_endpoint}${azurerm_storage_container.container_functions.name}"
  storage_authentication_type       = "UserAssignedIdentity" # "StorageAccountConnectionString"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.identity_function_app.id
  # # storage_access_key          = azurerm_storage_account.storage_functions.primary_access_key

  runtime_name           = "python"
  runtime_version        = "3.12" # 3.14 is in preview
  maximum_instance_count = 50
  instance_memory_in_mb  = 2048

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity_function_app.id]
  }

  #   always_ready {
  #     name           = "alwaysReady"
  #     instance_count = 1
  #   }

  site_config {
  }

  app_settings = {
    AzureWebJobsStorage__credential     = "managedidentity"
    AzureWebJobsStorage__clientId       = azurerm_user_assigned_identity.identity_function_app.client_id
    AzureWebJobsStorage__blobServiceUri = azurerm_storage_account.storage_functions.primary_blob_endpoint
    # AzureWebJobsFeatureFlags = "EnableMcpCustomHandlerPreview"
    # PYTHONPATH               = "/home/site/wwwroot/.python_packages/lib/site-packages"
  }
}

output "mcp_function_app_hostname" {
  value = azurerm_function_app_flex_consumption.function_app.default_hostname
}
