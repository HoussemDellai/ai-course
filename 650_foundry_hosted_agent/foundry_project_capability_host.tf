# Creating capability hosts is not required. 
# However if you do want agents to use your own resources, you must create a capability host on both the account and project.
# https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/capabilityhosts?pivots=deployment-language-terraform
resource "azapi_resource" "foundry_capability_host" {
  type                      = "Microsoft.CognitiveServices/accounts/capabilityHosts@2025-10-01-preview"
  name                      = "foundry-capability-host-${var.prefix}"
  parent_id                 = azurerm_cognitive_account.foundry.id
  schema_validation_enabled = false

  body = {
    properties = {
      capabilityHostKind             = "Agents"
      enablePublicHostingEnvironment = true
    }
  }
}

# Foundry Account capabilityHost Not Found, please retry again after creating capabilityHost for the Foundry Account.
resource "azapi_resource" "foundry_project_capability_host" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-10-01-preview"
  name                      = "foundry-project-capability-host"
  parent_id                 = azurerm_cognitive_account_project.project.id
  schema_validation_enabled = false

  body = {
    properties = {
      capabilityHostKind             = "Agents"
      enablePublicHostingEnvironment = true
    }
  }

  depends_on = [azapi_resource.foundry_capability_host]

}
