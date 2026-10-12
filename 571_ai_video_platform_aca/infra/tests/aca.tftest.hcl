mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      object_id = "00000000-0000-0000-0000-000000000001"
    }
  }
  mock_resource "azurerm_cognitive_account_project" {
    defaults = {
      endpoints = { "AI Foundry API" = "https://foundry.test/api/projects/project" }
    }
  }
}
mock_provider "azapi" {}
mock_provider "random" {}
mock_provider "time" {}

variables {
  # Test fixtures, not approved or profiled deployment allocations.
  comfyui_cpu        = 2
  comfyui_memory_gib = 4
}

run "isolated_gpu_architecture" {
  command = plan

  assert {
    condition     = azurerm_resource_group.rg.name == "rg-aivideo571"
    error_message = "Deployment must not adopt the copied 570 resource group."
  }
  assert {
    condition     = azurerm_container_app.comfyui.template[0].min_replicas == 1 && azurerm_container_app.comfyui.template[0].max_replicas == 1
    error_message = "ComfyUI must have exactly one stable always-on replica."
  }
  assert {
    condition     = azurerm_container_app.comfyui.workload_profile_name == "GPU-NC24-A100"
    error_message = "ComfyUI must use the A100 consumption workload profile."
  }
  assert {
    condition     = azurerm_container_app_environment.aca_environment.location == azurerm_virtual_network.vnet_aca.location && azurerm_storage_account.storage_comfyui.location == azurerm_virtual_network.vnet_aca.location
    error_message = "ACA, VNet and NFS storage must be co-located."
  }
  assert {
    condition     = azurerm_container_app.comfyui.ingress[0].external_enabled && !azurerm_container_app.comfyui.ingress[0].allow_insecure_connections
    error_message = "Public ComfyUI must use HTTPS ingress."
  }
  assert {
    condition     = azurerm_container_app.app.workload_profile_name == "Consumption"
    error_message = "The orchestrator must remain on CPU Consumption."
  }
}
