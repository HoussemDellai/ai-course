resource "azurerm_resource_group" "rg_functions" {
  name     = "rg-functions-${var.prefix}"
  location = "swedencentral"
}

resource "azurerm_storage_account" "storage_functions" {
  name                      = "storage4functions${var.prefix}"
  resource_group_name       = azurerm_resource_group.rg_functions.name
  location                  = azurerm_resource_group.rg_functions.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"
  shared_access_key_enabled = true

  tags = {
    SecurityControl = "Ignore"
  }
}

resource "azurerm_storage_container" "container_functions" {
  name                  = "container-functions"
  storage_account_id    = azurerm_storage_account.storage_functions.id
  container_access_type = "private"
}

resource "azurerm_service_plan" "app_service_plan_functions" {
  name                = "app-service-plan-functions"
  resource_group_name = azurerm_resource_group.rg_functions.name
  location            = azurerm_resource_group.rg_functions.location
  sku_name            = "FC1"
  os_type             = "Linux"
}

resource "azurerm_function_app_flex_consumption" "function_app" {
  name                          = "function-app-${var.prefix}"
  resource_group_name           = azurerm_resource_group.rg_functions.name
  location                      = azurerm_resource_group.rg_functions.location
  service_plan_id               = azurerm_service_plan.app_service_plan_functions.id
  public_network_access_enabled = true
  virtual_network_subnet_id     = null # Set to your subnet ID if you want to integrate with a VNet

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${azurerm_storage_account.storage_functions.primary_blob_endpoint}${azurerm_storage_container.container_functions.name}"
  storage_authentication_type       = "UserAssignedIdentity" # "StorageAccountConnectionString"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.identity_function_app.id
  # storage_access_key          = azurerm_storage_account.storage_functions.primary_access_key

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

  # app_settings = {
  #   "AzureWebJobsStorage__blobServiceUri" = azurerm_storage_account.storage_functions.primary_blob_endpoint
  #   "AzureWebJobsStorage__credential"     = "managedidentity"
  #   "AzureWebJobsStorage__clientId"       = azurerm_user_assigned_identity.identity_function_app.client_id
  #   # AzureWebJobsFeatureFlags = "EnableMcpCustomHandlerPreview"
  #   # PYTHONPATH               = "/home/site/wwwroot/.python_packages/lib/site-packages"
  # }
}

output "mcp_function_app_hostname" {
  value = azurerm_function_app_flex_consumption.function_app.default_hostname
}

# user assigned identity for the function app
resource "azurerm_user_assigned_identity" "identity_function_app" {
  name                = "identity-function-app-${var.prefix}"
  resource_group_name = azurerm_resource_group.rg_functions.name
  location            = azurerm_resource_group.rg_functions.location
}

# --- Storage Blob Data Owner --- Managed Identity
resource "azurerm_role_assignment" "storage_blob_mi" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
}

# --- Storage Blob Data Owner --- User Identity
resource "azurerm_role_assignment" "storage_blob_user" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Storage Queue Data Contributor
resource "azurerm_role_assignment" "storage_queue_mi" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
}

# Storage Table Data Contributor
resource "azurerm_role_assignment" "storage_table_mi" {
  scope                = azurerm_storage_account.storage_functions.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.identity_function_app.principal_id
}

# data "azurerm_client_config" "current" {}

# locals {
#   # Build storage endpoint app settings dynamically based on feature flags
#   blob_settings = var.enable_blob ? {
#     "AzureWebJobsStorage__blobServiceUri" = azurerm_storage_account.storage.primary_blob_endpoint
#   } : {}

#   queue_settings = var.enable_queue ? {
#     "AzureWebJobsStorage__queueServiceUri" = azurerm_storage_account.storage.primary_queue_endpoint
#   } : {}

#   table_settings = var.enable_table ? {
#     "AzureWebJobsStorage__tableServiceUri" = azurerm_storage_account.storage.primary_table_endpoint
#   } : {}

#   file_settings = var.enable_files ? {
#     "AzureWebJobsStorage__fileServiceUri" = azurerm_storage_account.storage.primary_file_endpoint
#   } : {}

#   # Base app settings always included
#   base_app_settings = {
#     "AzureWebJobsStorage__credential"           = "managedidentity"
#     "AzureWebJobsStorage__clientId"             = azurerm_user_assigned_identity.api.client_id
#     "APPLICATIONINSIGHTS_AUTHENTICATION_STRING" = "ClientId=${azurerm_user_assigned_identity.api.client_id};Authorization=AAD"
#     "APPLICATIONINSIGHTS_CONNECTION_STRING"     = azurerm_application_insights.appinsights.connection_string
#   }

#   # Merge all app settings
#   all_app_settings = merge(
#     local.base_app_settings,
#     local.blob_settings,
#     local.queue_settings,
#     local.table_settings,
#     local.file_settings,
#   )
# }
