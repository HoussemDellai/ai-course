resource "azurerm_container_registry" "acr" {
  name                = "acr4${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Standard" # Basic's 10 GiB quota cannot hold the multi-engine voice-clone image
  admin_enabled       = false
}

locals {
  app_dir = "${path.module}/../app"
  # Single source of truth shared with the application (video_platform/version.py) and the image tag.
  app_version    = trimspace(file("${path.module}/../app/video_platform/VERSION"))
  app_image_tag  = "video-platform:${local.app_version}"
  app_dockerfile = var.educational_runtime ? "drawio_runtime/Dockerfile.education" : "Dockerfile"
  app_image      = "${azurerm_container_registry.acr.login_server}/${local.app_image_tag}"
}

# Builds the orchestrator image in ACR (no local Docker needed) only when the semantic-version tag is missing.
# To ship app changes, bump app/video_platform/VERSION; the image tag always equals the version shown in the UI.
resource "terraform_data" "build_app_image" {
  triggers_replace = [azurerm_container_registry.acr.id, local.app_image]

  lifecycle {
    precondition {
      condition     = can(regex("^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?(\\+[0-9A-Za-z.-]+)?$", local.app_version))
      error_message = "app/video_platform/VERSION must contain a semantic version such as 1.0.0."
    }
  }

  provisioner "local-exec" {
    working_dir = local.app_dir
    interpreter = ["pwsh", "-NoProfile", "-File"]
    command     = "${abspath(path.module)}/scripts/build-app-image.ps1"
    environment = {
      SUBSCRIPTION_ID = var.subscription_id
      ACR_NAME        = azurerm_container_registry.acr.name
      APP_IMAGE_TAG   = local.app_image_tag
      APP_DOCKERFILE  = local.app_dockerfile
    }
  }
}
