resource "azurerm_cdn_frontdoor_profile" "frontdoor" {
  name                = "frontdoor-${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Premium_AzureFrontDoor" # "Standard_AzureFrontDoor"
}

resource "azurerm_cdn_frontdoor_endpoint" "endpoint-apim" {
  name                     = "endpoint-apim"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.frontdoor.id
  enabled                  = true
}

resource "azurerm_cdn_frontdoor_origin_group" "origin-group-apim" {
  name                     = "origin-group-apim"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.frontdoor.id
  session_affinity_enabled = true

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }

  health_probe {
    path                = "/"
    request_type        = "GET"
    protocol            = "Https"
    interval_in_seconds = 60
  }
}

resource "azurerm_cdn_frontdoor_origin" "origin-apim" {
  name                           = "origin-apim"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.origin-group-apim.id
  enabled                        = true
  host_name                      = replace(azurerm_api_management.apim.gateway_url, "https://", "")
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = replace(azurerm_api_management.apim.gateway_url, "https://", "")
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true

  # private_link {
  #   request_message        = "Request access for Private Link Origin CDN Frontdoor"
  #   target_type            = "Gateway" # Error: expected private_link.0.target_type to be one of ["blob" "blob_secondary" "sites" "web"], got Gateway
  #   location               = azurerm_resource_group.rg.location
  #   private_link_target_id = azapi_resource.apim.id
  # }

  lifecycle {
    ignore_changes = [private_link]
  }
}

resource "azapi_update_resource" "configure-private-link-frontdoor-origin" {
  type        = "Microsoft.Cdn/profiles/origingroups/origins@2024-09-01"
  resource_id = azurerm_cdn_frontdoor_origin.origin-apim.id

  body = {
    properties = {
      sharedPrivateLinkResource = {
        groupId             = "Gateway",
        privateLinkLocation = azurerm_resource_group.rg.location,
        requestMessage      = "Please validate PE connection"
        privateLink = {
          id = azurerm_api_management.apim.id
        }
      }
    }
  }
}

resource "azurerm_cdn_frontdoor_route" "route-apim" {
  name                          = "route-apim"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.endpoint-apim.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.origin-group-apim.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.origin-apim.id]
  supported_protocols           = ["Http", "Https"]
  patterns_to_match             = ["/*"]
  forwarding_protocol           = "MatchRequest" # "HttpsOnly"
  link_to_default_domain        = true
  https_redirect_enabled        = true # false
  cdn_frontdoor_origin_path     = "/"
}
