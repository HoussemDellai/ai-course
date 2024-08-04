# https://github.com/Azure/terraform/blob/master/quickstart/101-ai-studio/main.tf

resource "azurerm_resource_group" "rg" {
  name     = "rg-openai-tf"
  location = "swedencentral"
}

resource "azurerm_cognitive_account" "cognitive-account" {
  name                = "azure-openai-swc"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "OpenAI"
  sku_name            = "S0"
}

resource "azurerm_cognitive_deployment" "text-embedding-3-large" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_cognitive_account.cognitive-account.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }

  scale {
    type = "Standard"
  }
}

resource "azurerm_cognitive_deployment" "gpt-4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_cognitive_account.cognitive-account.id
  
  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-05-13"
  }

  scale {
    type = "Standard"
  }
}