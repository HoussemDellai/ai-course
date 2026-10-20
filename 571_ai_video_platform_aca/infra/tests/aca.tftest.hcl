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
  comfyui_memory_gib = 4
}

run "isolated_gpu_architecture" {
  command = plan

  assert {
    condition     = azurerm_resource_group.rg.name == "rg-aivideo571"
    error_message = "Deployment must not adopt the copied 570 resource group."
  }
  assert {
    condition     = length(azurerm_container_app.comfyui) == 2 && alltrue([for app in azurerm_container_app.comfyui : app.template[0].min_replicas == 1 && app.template[0].max_replicas == 1])
    error_message = "Each of the two ComfyUI workers must have exactly one stable always-on replica."
  }
  assert {
    condition     = alltrue([for app in azurerm_container_app.comfyui : app.workload_profile_name == "GPU-NC24-A100"])
    error_message = "ComfyUI must use the A100 consumption workload profile."
  }
  assert {
    condition     = azurerm_container_app_environment.aca_environment.location == azurerm_virtual_network.vnet_aca.location && azurerm_storage_account.storage_comfyui.location == azurerm_virtual_network.vnet_aca.location
    error_message = "ACA, VNet and NFS storage must be co-located."
  }
  assert {
    condition     = alltrue([for app in azurerm_container_app.comfyui : app.ingress[0].external_enabled && !app.ingress[0].allow_insecure_connections])
    error_message = "Public ComfyUI must use HTTPS ingress."
  }
  assert {
    condition     = azurerm_container_app.app.workload_profile_name == "Consumption"
    error_message = "The orchestrator must remain on CPU Consumption."
  }
}

run "stable_worker_names_and_wiring" {
  command = plan

  override_resource {
    target          = azurerm_container_app.comfyui["primary"]
    override_during = plan
    values = {
      ingress = { fqdn = "primary.test" }
    }
  }
  override_resource {
    target          = azurerm_container_app.comfyui["secondary"]
    override_during = plan
    values = {
      ingress = { fqdn = "secondary.test" }
    }
  }

  assert {
    condition     = output.comfyui_urls == ["https://primary.test", "https://secondary.test"]
    error_message = "Workers must have distinct deterministic endpoints."
  }
  assert {
    condition     = output.comfyui_apps == ["comfyui-aivideo571", "comfyui-aivideo571-2"] && output.comfyui_app == "comfyui-aivideo571"
    error_message = "The existing primary name and legacy output must remain stable."
  }
  assert {
    condition = alltrue([
      for env in azurerm_container_app.app.template[0].container[0].env :
      env.value == join(",", local.comfyui_urls) if contains(["COMFYUI_URLS", "GPU_STATS_URLS"], env.name)
    ])
    error_message = "Rendering and telemetry must use every stable worker endpoint."
  }
  assert {
    condition     = output.comfyui_url == output.comfyui_urls[0] && output.gpu_stats_url == output.gpu_stats_urls[0]
    error_message = "Singular URL outputs must remain aliases for the primary worker."
  }
  assert {
    condition = alltrue([
      for key, app in azurerm_container_app.comfyui :
      one([for env in app.template[0].container[0].env : env.value if env.name == "COMFY_WORKER"]) == key
    ])
    error_message = "Each worker must receive its isolated runtime identity."
  }
}

run "one_worker_configuration" {
  command = plan
  variables {
    comfyui_worker_count = 1
  }
  assert {
    condition     = keys(azurerm_container_app.comfyui) == ["primary"] && length(output.comfyui_urls) == 1
    error_message = "One-worker mode must retain only the existing primary."
  }
}

run "reject_fractional_worker_count" {
  command = plan
  variables {
    comfyui_worker_count = 1.5
  }
  expect_failures = [var.comfyui_worker_count]
}

run "reject_three_workers" {
  command = plan
  variables {
    comfyui_worker_count = 3
  }
  expect_failures = [var.comfyui_worker_count]
}

run "inline_hf_token_uses_secret_reference" {
  command = plan

  variables {
    hf_token = "test-read-token"
  }

  assert {
    condition     = one(azurerm_container_app_job.aca_job_download_models.secret).value == var.hf_token
    error_message = "The inline HF token must be stored as a Container Apps secret."
  }
  assert {
    condition = anytrue([
      for env in azurerm_container_app_job.aca_job_download_models.template[0].container[0].env :
      env.name == "HF_TOKEN" && env.secret_name == "hf-token" && env.value == null
    ])
    error_message = "HF_TOKEN must reference the secret, never a literal environment value."
  }
}

run "key_vault_hf_token_remains_supported" {
  command = plan

  variables {
    hf_token_secret_id = "https://example-vault.vault.azure.net/secrets/hf-token/version"
  }

  assert {
    condition     = one(azurerm_container_app_job.aca_job_download_models.secret).key_vault_secret_id == var.hf_token_secret_id
    error_message = "Key Vault references must remain supported."
  }
}

run "reject_ambiguous_hf_credentials" {
  command = plan

  variables {
    hf_token           = "test-read-token"
    hf_token_secret_id = "https://example-vault.vault.azure.net/secrets/hf-token/version"
  }

  expect_failures = [var.hf_token]
}
