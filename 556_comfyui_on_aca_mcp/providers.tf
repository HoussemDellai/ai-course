terraform {

  required_version = ">= 1.14, < 2.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.9"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.13"
    }
  }
}

provider "azurerm" {
  subscription_id = var.subscription_id
  use_cli         = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

provider "azapi" {
  subscription_id = var.subscription_id
  use_cli         = true
}
