terraform {

  required_version = ">= 1.14"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.58.0"
    }
  }
}

provider "azurerm" {
  use_cli = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}