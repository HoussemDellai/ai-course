
resource "azurerm_machine_learning_compute_cluster" "aml_compute_cluster" {
  name                          = "aml-compute-cluster-${var.prefix}"
  location                      = azurerm_resource_group.rg.location
  vm_priority                   = "LowPriority"
  vm_size                       = "Standard_DS2_v2" # "Standard_DS2_v2"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.aml_workspace.id
  subnet_resource_id            = azurerm_subnet.snet_aml_compute.id

  scale_settings {
    min_node_count                       = 0
    max_node_count                       = 1
    scale_down_nodes_after_idle_duration = "PT30S" # 30 seconds
  }

  identity {
    type = "SystemAssigned"
  }
}