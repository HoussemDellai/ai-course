terraform {

  required_version = ">= 1.14"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.58.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">= 2.8.0"
    }
  }
}

provider "azurerm" {
  # subscription_id = "17b12858-3960-4e6f-a663-a06fdae23428"
  subscription_id = "25a98a18-5e94-4b21-9d17-e8cf45bfd81f"
  use_cli         = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

provider "azapi" {
  use_cli = true
}
