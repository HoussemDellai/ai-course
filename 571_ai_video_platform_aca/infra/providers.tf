terraform {

  required_version = ">= 1.14"

  backend "local" {
    path = "state-571/terraform.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = ">= 2.8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.13.1"
    }
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  use_cli             = true
  storage_use_azuread = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    cognitive_account {
      purge_soft_delete_on_destroy = true
    }
  }
}

provider "azapi" {
  use_cli         = true
  subscription_id = var.subscription_id
}
