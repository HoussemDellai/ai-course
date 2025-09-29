resource "azurerm_ai_services" "ai-services" {
  name                               = "ai-services"
  location                           = azurerm_resource_group.rg.location
  resource_group_name                = azurerm_resource_group.rg.name
  sku_name                           = "S0"
  local_authentication_enabled       = true
  public_network_access              = "Enabled"
  outbound_network_access_restricted = false
  custom_subdomain_name              = "ai-services-${random_string.random.result}-${var.prefix}"
}

resource "azurerm_cognitive_deployment" "gpt-4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 8                # (8k tokens per minute) to showcase the retry logic in the load balancer
  }

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-11-20"
  }
}

resource "azurerm_cognitive_deployment" "gpt-4o-mini" {
  name                 = "gpt-4o-mini"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 8                # (8k tokens per minute) to showcase the retry logic in the load balancer
  }

  model {
    format  = "OpenAI"
    name    = "gpt-4o-mini"
    version = "2024-07-18"
  }
}

resource "azurerm_cognitive_deployment" "gpt-o4-mini" {
  name                 = "gpt-o4-mini"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 8                # (8k tokens per minute) to showcase the retry logic in the load balancer
  }

  model {
    format  = "OpenAI"
    name    = "o4-mini"
    version = "2025-04-16"
  }
}

resource "azurerm_cognitive_deployment" "gpt-41" {
  name                 = "gpt-4.1"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 8                # (8k tokens per minute) to showcase the retry logic in the load balancer
  }

  model {
    format  = "OpenAI"
    name    = "gpt-4.1"
    version = "2025-04-14"
  }
}

resource "azurerm_cognitive_deployment" "text-embedding-3-large" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_ai_services.ai-services.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }

  sku {
    name     = "Standard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 10 # 350
  }
}

resource "azapi_resource" "serverless_endpoint_deepseek" {
  type      = "Microsoft.MachineLearningServices/workspaces/serverlessEndpoints@2024-10-01-preview"
  parent_id = azurerm_ai_foundry_project.ai-foundry-project.id
  name      = "DeepSeek-R1-${random_string.random.result}"
  location  = azurerm_resource_group.rg.location

  body = {
    properties = {
      authMode = "Key"
      contentSafety = {
        contentSafetyStatus = "Enabled"
      }
      modelSettings = {
        modelId = "azureml://registries/azureml-deepseek/models/DeepSeek-R1"
      }
    }
    sku = {
      name = "Consumption"
      tier = "Free"
    }
  }
}

# Doesn't work
# resource "azurerm_cognitive_deployment" "deepseek-r1" {
#   name                 = "DeepSeek-R1"
#   cognitive_account_id = azurerm_ai_services.ai-services.id

#   sku {
#     name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
#     capacity = 8                # (8k tokens per minute) to showcase the retry logic in the load balancer
#   }

#   model {
#     format  = "OpenAI"
#     name    = "DeepSeek-R1"
#     # version = "2024-11-20"
#   }
# }

# resource "azurerm_cognitive_account" "cognitive-account" {
#   name                = "azure-openai-swc"
#   location            = azurerm_resource_group.rg.location
#   resource_group_name = azurerm_resource_group.rg.name
#   kind                = "OpenAI"
#   sku_name            = "S0"
# }

