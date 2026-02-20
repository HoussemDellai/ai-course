resource "azurerm_network_security_perimeter" "nsp" {
  name                = "azure-nsp-${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

# resource "azapi_resource" "networkSecurityPerimeter" {
#   type      = "Microsoft.Network/networkSecurityPerimeters@2023-07-01-preview"
#   parent_id = azurerm_resource_group.rg.id
#   name      = "nsp-${var.prefix}"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {}
#   }
# }

resource "azurerm_network_security_perimeter_profile" "nsp_profile" {
  name                          = "nsp-profile"
  network_security_perimeter_id = azurerm_network_security_perimeter.nsp.id
}

# resource "azapi_resource" "nsp_profile" {
#   type      = "Microsoft.Network/networkSecurityPerimeters/profiles@2023-07-01-preview"
#   parent_id = azapi_resource.networkSecurityPerimeter.id
#   name      = "nsp-profile"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {}
#   }
# }

resource "azurerm_network_security_perimeter_access_rule" "nsp_access_rule_inbound" {
  name                                  = "nsp-access-rule-inbound"
  network_security_perimeter_profile_id = azurerm_network_security_perimeter_profile.nsp_profile.id
  direction                             = "Inbound"

  address_prefixes = ["0.0.0.0/0"]
  # service_tags     = []
  # subscription_ids = []
}

# resource "azapi_resource" "nsp_access_rule_inbound" {
#   type      = "Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2023-07-01-preview"
#   parent_id = azapi_resource.nsp_profile.id
#   name      = "nsp-access-rule-inbound"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {
#       addressPrefixes           = ["*"] # ["100.10.0.0/16"]
#       direction                 = "Inbound"
#       emailAddresses            = []
#       fullyQualifiedDomainNames = []
#       phoneNumbers              = []
#       subscriptions             = []
#     }
#   }
# }

resource "azurerm_network_security_perimeter_access_rule" "nsp_access_rule_outbound" {
  name                                  = "nsp-access-rule-outbound"
  network_security_perimeter_profile_id = azurerm_network_security_perimeter_profile.nsp_profile.id
  direction                             = "Outbound"

  fqdns            = ["contoso.com"]
  # service_tags     = []
  # subscription_ids = []
}

# resource "azapi_resource" "nsp_access_rule_outbound" {
#   type      = "Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2023-07-01-preview"
#   parent_id = azapi_resource.nsp_profile.id
#   name      = "nsp_access_rule_outbound"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {
#       addressPrefixes           = []
#       direction                 = "Outbound"
#       emailAddresses            = []
#       fullyQualifiedDomainNames = ["contoso.com"]
#       phoneNumbers              = []
#       subscriptions             = []
#     }
#   }
# }

resource "azurerm_network_security_perimeter_association" "nsp_association_keyvault" {
  name        = "nsp-association-keyvault"
  access_mode = "Learning" # "Enforced"

  network_security_perimeter_profile_id = azurerm_network_security_perimeter_profile.nsp_profile.id
  resource_id                           = azurerm_key_vault.keyvault.id
}

# resource "azapi_resource" "nsp_resource_association_keyvault" {
#   type      = "Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2023-07-01-preview"
#   parent_id = azapi_resource.networkSecurityPerimeter.id
#   name      = "nsp-resource-association-keyvault"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {
#       accessMode = "Learning" # "Enforced" # 
#       privateLinkResource = {
#         id = azurerm_key_vault.keyvault.id
#       }
#       profile = {
#         id = azapi_resource.nsp_profile.id
#       }
#     }
#   }
# }

resource "azurerm_network_security_perimeter_association" "nsp_association_foundry" {
  name        = "nsp-association-foundry"
  access_mode = "Learning" # "Enforced"

  network_security_perimeter_profile_id = azurerm_network_security_perimeter_profile.nsp_profile.id
  resource_id                           = azurerm_cognitive_account.foundry.id
}

# resource "azapi_resource" "nsp_resource_association_foundry" {
#   type      = "Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2023-07-01-preview"
#   parent_id = azapi_resource.networkSecurityPerimeter.id
#   name      = "nsp-resource-association-foundry"
#   location  = azurerm_resource_group.rg.location
#   body = {
#     properties = {
#       accessMode = "Learning" # "Enforced" # 
#       privateLinkResource = {
#         id = azurerm_cognitive_account.foundry.id
#       }
#       profile = {
#         id = azapi_resource.nsp_profile.id
#       }
#     }
#   }
# }
