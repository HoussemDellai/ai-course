# resource "azurerm_cognitive_deployment" "gpt_52" {
#   name                 = "gpt-5.2"
#   cognitive_account_id = azurerm_cognitive_account.foundry.id

#   sku {
#     name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
#     capacity = 10
#   }

#   model {
#     format  = "OpenAI"
#     name    = "gpt-5.2"
#     version = "2025-12-11"
#   }
# }

resource "azurerm_cognitive_deployment" "gpt_4o_mini" {
  name                 = "gpt-4o-mini"
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 20
  }

  model {
    format  = "OpenAI"
    name    = "gpt-4o-mini"
    version = "2024-07-18"
  }
}

# Mistral Large 3 (25.12)
resource "azurerm_cognitive_deployment" "mistral_large" {
  name                 = "mistral-large"
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 250
  }

  model {
    format  = "Mistral AI"
    name    = "Mistral-Large-3"
    version = "1"
  }
}

resource "azurerm_cognitive_deployment" "mistral_document_ai" {
  name                 = "mistral-document-ai-2505"
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = "DataZoneStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 60
  }

  model {
    format  = "Mistral AI"
    name    = "mistral-document-ai-2505"
    version = "1"
  }
}

output "llm_model_deployment_name" {
  value = azurerm_cognitive_deployment.gpt_4o_mini.name
}