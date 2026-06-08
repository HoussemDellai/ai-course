resource "azurerm_cognitive_deployment" "gpt_54" {
  name                 = "gpt-5.4"
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 1000
  }

  model {
    format  = "OpenAI"
    name    = "gpt-5.4"
    version = "2026-03-05"
  }
}

resource "azurerm_cognitive_deployment" "kimi_k26" {
  name                 = "Kimi-K2.6"
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 100
  }

  model {
    format  = "MoonshotAI"
    name    = "Kimi-K2.6"
    version = "2026-04-20"
  }
}

output "llm_model_deployment_name_kimi" {
  value = azurerm_cognitive_deployment.kimi_k26.name
}

output "llm_model_deployment_name_chatgpt" {
  value = azurerm_cognitive_deployment.gpt_54.name
}

output "llm_model_deployment_name" {
  value = azurerm_cognitive_deployment.gpt_54.name
}