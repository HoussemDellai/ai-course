terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"

    }
    azapi = {
      source = "Azure/azapi"
    }
  }

  required_version = ">= 1.0.0"
}

provider "azurerm" {

  # subscription_id = var.subscription_id

  features {

  }
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "storage" {
  name                     = "${replace(var.function_app_name, "-", "")}store01"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  shared_access_key_enabled = true

  tags = {
    SecurityControl = "Ignore"
  }
}

# Storage Container for Deployment
resource "azurerm_storage_container" "storageContainer" {
  name                  = "deploymentpackage"
  storage_account_id    = azurerm_storage_account.storage.id
  container_access_type = "private"
}

# Function Plan (Flex Consumption)
resource "azapi_resource" "serverFarm" {
  type                      = "Microsoft.Web/serverfarms@2023-12-01"
  schema_validation_enabled = false
  location                  = var.location
  name                      = var.function_app_name
  parent_id                 = azurerm_resource_group.rg.id
  body = {
    kind = "functionapp",
    sku = {
      tier = "FlexConsumption",
      name = "FC1"
    },
    properties = {
      reserved = true
    }
  }
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "logAnalyticsWorkspace" {
  name                = "${var.function_app_name}loganalytics"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}
# Application Insights
resource "azurerm_application_insights" "appInsights" {
  name                = "${var.function_app_name}appinsights"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.logAnalyticsWorkspace.id
}

locals {
  blobStorageAndContainer = "${azurerm_storage_account.storage.primary_blob_endpoint}deploymentpackage"
}

# Function App Deployment
resource "azapi_resource" "functionApps" {
  type                      = "Microsoft.Web/sites@2023-12-01"
  schema_validation_enabled = false
  location                  = var.location
  name                      = var.function_app_name
  parent_id                 = azurerm_resource_group.rg.id
  body = {
    kind = "functionapp,linux",
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      serverFarmId = azapi_resource.serverFarm.id,
      functionAppConfig = {
        deployment = {
          storage = {
            type  = "blobContainer",
            value = local.blobStorageAndContainer,
            authentication = {
              type = "SystemAssignedIdentity"
            }
          }
        },
        scaleAndConcurrency = {
          maximumInstanceCount = 40,
          instanceMemoryMB     = 2048,
        },
        runtime = {
          name    = "python",
          version = "3.13",
        }
      },
      siteConfig = {
        appSettings = [
          {
            name  = "AzureWebJobsStorage__accountName",
            value = azurerm_storage_account.storage.name
          },
          {
            name  = "APPLICATIONINSIGHTS_CONNECTION_STRING",
            value = azurerm_application_insights.appInsights.connection_string
          },

          {
            name  = "YouTubeApiKey",
            value = var.youtube_api_key
          }
        ]
      }
    }
  }
  depends_on = [azapi_resource.serverFarm, azurerm_application_insights.appInsights, azurerm_storage_account.storage]
}

data "azurerm_linux_function_app" "fn_wrapper" {
  name                = azapi_resource.functionApps.name
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_role_assignment" "storage_roleassignment" {
  scope                = azurerm_storage_account.storage.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_linux_function_app.fn_wrapper.identity.0.principal_id
}

variable "location" {
  description = "The location where the resources will be created."
  type        = string
  default     = "northeurope"
}

variable "resource_group_name" {
  description = "The name of the resource group."
  type        = string
  default     = "azure-function-mcp-servers"
}

variable "function_app_name" {
  description = "The name of the function app."
  type        = string
  default     = "mcp-function-app01"
}

variable "youtube_api_key" {
  description = "The API key for YouTube."
  type        = string
  default     = ""
  sensitive   = true
}


# variable "subscription_id" {
#   description = "The Azure subscription ID."
#   type        = string
#   sensitive   = true
# }
