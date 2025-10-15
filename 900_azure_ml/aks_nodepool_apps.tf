# variable "nodepoolapps" {
#   default = {
#     # "poolappsarm" = {
#     #   vm_size           = "Standard_D2pds_v5" # arm
#     #   os_disk_type      = "Ephemeral"         # "Managed"         # 
#     #   cidr_subnet_nodes = ["10.1.5.0/24"]
#     #   cidr_subnet_pods  = ["10.1.6.0/24"]
#     #   os_sku            = "Ubuntu"
#     # },
#     "poolappsamd" = {
#       vm_size           = "Standard_D2s_v5" # intel # Standard_D2s_v5 does not support Ephemeral OS disk
#       os_disk_type      = "Managed"         # "Ephemeral" # 
#       cidr_subnet_nodes = ["10.1.2.0/24"]
#       cidr_subnet_pods  = ["10.10.240.0/20"]
#       os_sku            = "Ubuntu"
#     },
#     # "npmariner" = {
#     #   vm_size           = "Standard_D2_v2"
#     #   os_disk_type      = "Managed" # "Ephemeral" # 
#     #   cidr_subnet_nodes = ["10.1.9.0/24"]
#     #   cidr_subnet_pods  = ["10.1.10.0/24"]
#     #   os_sku            = "Mariner" # Ubuntu, CBLMariner, Mariner, Windows2019, Windows2022
#     # },
#     # "npmarinercbl" = {
#     #   vm_size           = "Standard_D2_v2"
#     #   os_disk_type      = "Managed" # "Ephemeral" # 
#     #   cidr_subnet_nodes = ["10.1.11.0/24"]
#     #   cidr_subnet_pods  = ["10.1.12.0/24"]
#     #   os_sku            = "CBLMariner" # Ubuntu, CBLMariner, Mariner, Windows2019, Windows2022
#     # },
#     # "poolapps05" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.13.0/24"]
#     #   cidr_subnet_pods  = ["10.1.14.0/24"]
#     # },
#     # "poolapps06" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.15.0/24"]
#     #   cidr_subnet_pods  = ["10.1.16.0/24"]
#     # },
#     # "poolapps07" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.17.0/24"]
#     #   cidr_subnet_pods  = ["10.1.18.0/24"]
#     # },
#     # "poolapps08" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.19.0/24"]
#     #   cidr_subnet_pods  = ["10.1.20.0/24"]
#     # },
#     # "poolapps09" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.21.0/24"]
#     #   cidr_subnet_pods  = ["10.1.22.0/24"]
#     # },
#     # "poolapps10" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.23.0/24"]
#     #   cidr_subnet_pods  = ["10.1.24.0/24"]
#     # },
#     # "poolapps11" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.25.0/24"]
#     #   cidr_subnet_pods  = ["10.1.26.0/24"]
#     # },
#     # "poolapps12" = {
#     #   vm_size           = "Standard_D2pds_v5"
#     #   cidr_subnet_nodes = ["10.1.27.0/24"]
#     #   cidr_subnet_pods  = ["10.1.28.0/24"]
#     # }
#   }
# }

# resource "azurerm_subnet" "subnet_nodes_user_nodepool" {
#   for_each             = var.nodepoolapps
#   name                 = "snet-nodes-${each.key}"
#   virtual_network_name = azurerm_virtual_network.vnet_spoke_aks.name
#   resource_group_name  = azurerm_virtual_network.vnet_spoke_aks.resource_group_name
#   address_prefixes     = each.value.cidr_subnet_nodes
# }

# # resource "azurerm_subnet" "subnet_pods_user_nodepool" {
# #   for_each             = var.nodepoolapps
# #   name                 = "snet-pods-${each.key}"
# #   virtual_network_name = azurerm_virtual_network.vnet_spoke_aks.name
# #   resource_group_name  = azurerm_virtual_network.vnet_spoke_aks.resource_group_name
# #   address_prefixes     = each.value.cidr_subnet_pods

# #   # src: https://github.com/hashicorp/terraform-provider-azurerm/blob/4ea5f92ccc27a75807d704f6d66d53a6c31459cb/internal/services/containers/kubernetes_cluster_node_pool_resource_test.go#L1433
# #   delegation {
# #     name = "Microsoft.ContainerService.managedClusters"
# #     service_delegation {
# #       actions = [
# #         "Microsoft.Network/virtualNetworks/subnets/join/action",
# #       ]
# #       name = "Microsoft.ContainerService/managedClusters"
# #     }
# #   }
# # }

# resource "azurerm_kubernetes_cluster_node_pool" "poolapps" {
#   for_each                = var.nodepoolapps
#   name                    = each.key
#   kubernetes_cluster_id   = azurerm_kubernetes_cluster.aks.id
#   vm_size                 = each.value.vm_size # "Standard_D2pds_v5" # "Standard_D2ds_v5" # "Standard_D4pls_v5" # "Standard_D4s_v5" #  # "Standard_D2as_v5" doesn't support Ephemeral disk
#   node_count              = 1
#   auto_scaling_enabled    = true
#   min_count               = 1
#   max_count               = 3
#   zones                   = [1, 2, 3] # []
#   mode                    = "User"
#   orchestrator_version    = "1.33.0"
#   os_type                 = "Linux"
#   host_encryption_enabled = false
#   node_public_ip_enabled  = false
#   max_pods                = 250
#   os_disk_size_gb         = 60
#   os_disk_type            = each.value.os_disk_type # "Ephemeral" # "Managed" # 
#   os_sku                  = each.value.os_sku       # "Ubuntu"    # "CBLMariner" #
#   fips_enabled            = false
#   vnet_subnet_id          = azurerm_subnet.subnet_nodes_user_nodepool[each.key].id
#   scale_down_mode         = "Delete"       # ScaleDownModeDeallocate
#   workload_runtime        = "OCIContainer" # WasmWasi
#   priority                = "Regular"      # "Spot"
#   # pod_subnet_id           = var.aks_network_plugin == var.network_plugin_mode == "overlay" ? null : azurerm_subnet.subnet_pods_user_nodepool[each.key].id
#   # eviction_policy        = "Delete"
#   # spot_max_price         = 0.5 # note: this is the "maximum" price
#   # node_labels = {
#   #   "kubernetes.azure.com/scalesetpriority" = "spot"
#   # }
#   # node_taints = [
#   #   "kubernetes.azure.com/scalesetpriority=spot:NoSchedule"
#   # ]

#   upgrade_settings {
#     max_surge = 3
#   }

#   lifecycle {
#     # create_before_destroy = true
#     ignore_changes = [
#       node_count,
#       node_taints
#     ]
#   }

#   depends_on = [
#     azurerm_subnet_nat_gateway_association.association,
#     azurerm_nat_gateway_public_ip_prefix_association.natgw-pip-prefix-association
#   ]
# }
