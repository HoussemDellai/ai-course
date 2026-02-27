resource "azurerm_cognitive_deployment" "gpt_52" {
  name                       = "gpt-5.2"
  cognitive_account_id       = azurerm_cognitive_account.foundry.id
  rai_policy_name            = "Microsoft.DefaultV2"
  version_upgrade_option     = "NoAutoUpgrade" # OnceNewDefaultVersionAvailable, OnceCurrentVersionExpired
  dynamic_throttling_enabled = false

  sku {
    name     = "GlobalStandard" # "Standard" # DataZoneStandard, GlobalBatch, GlobalStandard and ProvisionedManaged
    capacity = 1000             # Tokens-per-Minute (TPM)
    tier     = null             # Free, Basic, Standard, Premium, Enterprise
  }

  model {
    format  = "OpenAI" # AI21 Labs, Black Forest Labs, Cohere, Core42, DeepSeek, Meta, Microsoft, Mistral AI, OpenAI, and xAI
    name    = "gpt-5.2"
    version = "2025-12-11"
  }
}

output "llm_model_deployment_name" {
  value = azurerm_cognitive_deployment.gpt_52.name
}
