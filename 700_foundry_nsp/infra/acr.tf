# https://github.com/claranet/terraform-azurerm-acr/blob/master/resources.tf

resource "azurerm_container_registry" "acr" {
  name                          = "acr4hostedagent${var.prefix}"
  resource_group_name           = azurerm_resource_group.rg.name
  location                      = azurerm_resource_group.rg.location
  sku                           = "Standard"
  admin_enabled                 = false
  public_network_access_enabled = true
  zone_redundancy_enabled       = false
  anonymous_pull_enabled        = false
  data_endpoint_enabled         = false
  network_rule_bypass_option    = "AzureServices"

  # network_rule_set {
  #   default_action = "Deny"

  #   ip_rule {
  #     action   = "Allow"
  #     ip_range = "${data.http.machine_ip.response_body}/32"
  #   }

  #   # virtual_network {
  #   #   action    = "Allow"
  #   #   subnet_id = null
  #   # }
  # }
  # identity {
  #   type = "UserAssigned"
  #   identity_ids = [
  #     azurerm_user_assigned_identity.container_registry_identity.id
  #   ]
  # }

  # georeplications {
  #   location                = "North Europe"
  #   zone_redundancy_enabled = true
  #   tags                    = {}
  # }

  provisioner "local-exec" {
    # interpreter = ["PowerShell", "-Command"]
    command = "az acr import --name ${azurerm_container_registry.acr.login_server} --source docker.io/library/hello-world:latest --image hello-world:latest"
    when    = create
  }
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "acr_fqdn" {
  value = azurerm_container_registry.acr.login_server
}