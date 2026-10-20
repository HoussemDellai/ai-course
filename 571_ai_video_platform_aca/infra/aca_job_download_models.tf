locals {
  hf_token_configured = var.hf_token_secret_id != "" || nonsensitive(var.hf_token != "")
  bootstrap_b64       = base64encode(replace(file("${path.module}/scripts/02-install-comfyui.sh"), "\r\n", "\n"))
  downloader_b64      = base64encode(replace(file("${path.module}/scripts/03-download-models.sh"), "\r\n", "\n"))
  exporter_b64        = base64encode(replace(file("${path.module}/scripts/gpu_stats_exporter.py"), "\r\n", "\n"))
  extension_b64       = base64encode(replace(file("${path.module}/scripts/comfyui_gpu_extension.py"), "\r\n", "\n"))
  provision_version = sha256(join("", [
    local.bootstrap_b64, local.downloader_b64, local.exporter_b64, local.extension_b64,
    filesha256("${path.module}/scripts/provision-models.sh"),
    filesha256("${path.module}/scripts/run-model-job.ps1"),
    tostring(var.download_education_images), var.hf_token_secret_id,
    nonsensitive(var.hf_token == "" ? "" : sha256(var.hf_token)),
  ]))
}

resource "azurerm_container_app_job" "aca_job_download_models" {
  name                         = "download-models-${var.prefix}"
  location                     = var.aca_location
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca_environment.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = var.model_download_timeout_seconds
  replica_retry_limit          = 1

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  dynamic "secret" {
    for_each = local.hf_token_configured ? [1] : []
    content {
      name                = "hf-token"
      value               = var.hf_token_secret_id == "" ? var.hf_token : null
      key_vault_secret_id = var.hf_token_secret_id == "" ? null : var.hf_token_secret_id
      identity            = var.hf_token_secret_id == "" ? null : azurerm_user_assigned_identity.app.id
    }
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "download-models"
      image   = "ubuntu:24.04"
      cpu     = 1
      memory  = "2Gi"
      command = ["/bin/bash", "-c"]
      args    = [replace(file("${path.module}/scripts/provision-models.sh"), "\r\n", "\n")]

      dynamic "env" {
        for_each = {
          COMFY_BOOTSTRAP_B64       = local.bootstrap_b64
          MODEL_DOWNLOADER_B64      = local.downloader_b64
          GPU_EXPORTER_B64          = local.exporter_b64
          GPU_EXTENSION_B64         = local.extension_b64
          PROVISION_VERSION         = local.provision_version
          DOWNLOAD_EDUCATION_IMAGES = var.download_education_images ? "1" : "0"
        }
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.hf_token_configured ? [1] : []
        content {
          name        = "HF_TOKEN"
          secret_name = "hf-token"
        }
      }

      volume_mounts {
        name = "storage-comfyui"
        path = "/root/ComfyUI"
      }
    }
    volume {
      name         = "storage-comfyui"
      storage_name = azurerm_container_app_environment_storage.storage_aca_comfyui_nfs.name
      storage_type = "NfsAzureFile"
    }
  }
}

resource "terraform_data" "provision_models" {
  triggers_replace = [azurerm_container_app_job.aca_job_download_models.id, local.provision_version]

  provisioner "local-exec" {
    interpreter = ["pwsh", "-NoProfile", "-File"]
    command     = "${path.module}/scripts/run-model-job.ps1"
    environment = {
      JOB_NAME        = azurerm_container_app_job.aca_job_download_models.name
      COMFY_APP_NAMES = join(",", [for key in sort(keys(local.comfyui_worker_names)) : local.comfyui_worker_names[key]])
      RESOURCE_GROUP  = azurerm_resource_group.rg.name
      SUBSCRIPTION_ID = var.subscription_id
      TIMEOUT_SECONDS = tostring(var.model_download_timeout_seconds * 2 + 600)
    }
  }
}
