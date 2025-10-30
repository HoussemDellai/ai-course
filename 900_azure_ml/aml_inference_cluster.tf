resource "azurerm_machine_learning_inference_cluster" "aml_aks_inference_cluster" {
  name                  = "aml-inf-cluster"
  location              = azurerm_resource_group.rg.location
  cluster_purpose       = "FastProd"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.aks_simple.id
  description           = "This is an example cluster used with Terraform"
  machine_learning_workspace_id = azurerm_machine_learning_workspace.aml_workspace.id
}