resource "azurerm_container_registry" "acr" {
  name                = "acr${var.prefix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = false
}

locals {
  app_dir = "${path.module}/../app"
  app_files = sort([
    for f in fileset(local.app_dir, "**") : f
    if !startswith(f, ".venv/") && !strcontains(f, "__pycache__") && !startswith(f, "tests/") && !startswith(f, ".") && !startswith(f, "output/")
  ])
  app_hash      = substr(sha256(join("", [for f in local.app_files : filesha256("${local.app_dir}/${f}")])), 0, 12)
  app_image_tag = "video-platform:1.0.0"
  app_image     = "${azurerm_container_registry.acr.login_server}/${local.app_image_tag}"
  # app_image = "${azurerm_container_registry.acr.login_server}/video-platform:${local.app_hash}"
}

# Builds the orchestrator image in ACR (no local Docker needed) only when the tag is missing, e.g. in a new registry.
# To ship app changes, rebuild the tag manually or bump it in local.app_image_tag.
resource "terraform_data" "build_app_image" {
  triggers_replace = [azurerm_container_registry.acr.id, local.app_image]

  provisioner "local-exec" {
    working_dir = local.app_dir
    command     = "az acr repository show --name ${azurerm_container_registry.acr.name} --image ${local.app_image_tag} --output none || az acr build --registry ${azurerm_container_registry.acr.name} --image ${local.app_image_tag} --file Dockerfile ."
  }
}
