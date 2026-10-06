resource "azurerm_cognitive_account" "foundry" {
  name                          = "foundry-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  kind                          = "AIServices" # includes Azure OpenAI models and Azure AI Speech
  sku_name                      = "S0"
  project_management_enabled    = true
  custom_subdomain_name         = "foundry-${var.prefix}" # required for Entra ID auth with Speech
  local_auth_enabled            = false                   # Entra ID only, no API keys
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_account_project" "project" {
  name                 = "project-${var.prefix}"
  cognitive_account_id = azurerm_cognitive_account.foundry.id
  location             = azurerm_cognitive_account.foundry.location
  display_name         = "AI Video Platform"
  description          = "Prompt enhancement and storyboarding for the AI video platform"

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_deployment" "llm" {
  name                   = var.llm_model_name
  cognitive_account_id   = azurerm_cognitive_account.foundry.id
  rai_policy_name        = "Microsoft.DefaultV2"
  version_upgrade_option = "NoAutoUpgrade"

  sku {
    name     = "GlobalStandard"
    capacity = var.llm_capacity
  }

  model {
    format  = "OpenAI"
    name    = var.llm_model_name
    version = var.llm_model_version
  }
}

# Lets the current user run the orchestrator locally against the same resources.
resource "azurerm_role_assignment" "me_foundry_user" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Foundry User"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "me_speech_user" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Cognitive Services Speech User"
  principal_id         = data.azurerm_client_config.current.object_id
}
