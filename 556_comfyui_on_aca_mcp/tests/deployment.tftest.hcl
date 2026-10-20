mock_provider "azurerm" {
  mock_resource "azurerm_container_registry" {
    defaults = {
      login_server = "test.azurecr.io"
    }
  }
}
mock_provider "azapi" {}

variables {
  enable_mcp = false
  mcp_image  = ""
}

run "base_has_no_public_placeholder_mcp" {
  command = plan

  assert {
    condition     = length(azurerm_container_app.mcp) == 0
    error_message = "MCP must not be created before its image exists."
  }
  assert {
    condition     = azurerm_container_app.aca_comfyui_cu130_a100.template[0].min_replicas == 0 && azurerm_container_app.aca_comfyui_cu130_a100.template[0].max_replicas == 1
    error_message = "The GPU app must retain zero-to-one scaling."
  }
  assert {
    condition     = azurerm_container_app_environment_storage.models.access_mode == "ReadOnly"
    error_message = "The GPU replica must not modify the shared model source."
  }
  assert {
    condition     = !azurerm_container_registry.mcp.admin_enabled
    error_message = "ACR must use managed identity, not admin credentials."
  }
  assert {
    condition     = !azurerm_storage_account.storage_comfyui.shared_access_key_enabled
    error_message = "Private NFS storage must not enable shared-key authentication."
  }
}

run "mcp_is_cpu_consumption" {
  command = plan
  variables {
    enable_mcp = true
    mcp_image  = "test.azurecr.io/comfy-mcp@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  assert {
    condition     = azurerm_container_app.mcp[0].workload_profile_name == "Consumption"
    error_message = "MCP must use CPU Consumption, not the GPU profile."
  }
  assert {
    condition     = azurerm_container_app.mcp[0].template[0].min_replicas == 1 && azurerm_container_app.mcp[0].template[0].max_replicas == 1
    error_message = "Keep exactly one MCP replica ready."
  }
  assert {
    condition     = !azurerm_container_app.mcp[0].ingress[0].allow_insecure_connections
    error_message = "The public MCP endpoint must retain HTTPS."
  }
  assert {
    condition     = azurerm_role_assignment.mcp_pull.role_definition_name == "AcrPull"
    error_message = "Use the image-pull role, not broad subscription permissions."
  }
}

run "mcp_requires_no_credentials" {
  command = plan
  variables {
    enable_mcp = true
    mcp_image  = "test.azurecr.io/comfy-mcp@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  assert {
    condition     = length(azurerm_container_app.mcp[0].secret) == 0
    error_message = "The anonymous MCP app must not require an ACA secret."
  }
  assert {
    condition     = !contains([for env in azurerm_container_app.mcp[0].template[0].container[0].env : env.name], "MCP_TOKEN")
    error_message = "The gateway must not require a token environment variable."
  }
}

run "reject_mutable_image_tag" {
  command = plan
  variables {
    mcp_image = "test.azurecr.io/comfy-mcp:latest"
  }
  expect_failures = [var.mcp_image]
}
