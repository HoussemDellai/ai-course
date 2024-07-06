---
title: Create node pools in Azure Kubernetes Service (AKS)
description: Learn how to create multiple node pools for a cluster in Azure Kubernetes Service (AKS).
ms.topic: article
ms.custom: devx-track-azurecli, build-2023, linux-related-content
ms.date: 12/08/2023
author: schaffererin
ms.author: schaffererin

ms.subservice: aks-nodes
---

# Create node pools for a cluster in Azure Kubernetes Service (AKS)

In Azure Kubernetes Service (AKS), nodes of the same configuration are grouped together into *node pools*. These node pools contain the underlying VMs that run your applications. When you create an AKS cluster, you define the initial number of nodes and their size (SKU), which creates a [*system node pool*][use-system-pool].

To support applications that have different compute or storage demands, you can create *user node pools*. System node pools serve the primary purpose of hosting critical system pods such as CoreDNS and `konnectivity`. User node pools serve the primary purpose of hosting your application pods. For example, use more user node pools to provide GPUs for compute-intensive applications, or access to high-performance SSD storage. However, if you wish to have only one pool in your AKS cluster, you can schedule application pods on system node pools.

> [!NOTE]
> This feature enables more control over creating and managing multiple node pools and requires separate commands for *create/update/delete* (CRUD) operations. Previously, cluster operations through [`az aks create`][az-aks-create] or [`az aks update`][az-aks-update] used the managedCluster API and were the only options to change your control plane and a single node pool. This feature exposes a separate operation set for agent pools through the agentPool API and requires use of the [`az aks nodepool`][az-aks-nodepool] command set to execute operations on an individual node pool.

This article shows you how to create one or more node pools in an AKS cluster.

## Before you begin

* You need the Azure CLI version 2.2.0 or later installed and configured. Run `az --version` to find the version. If you need to install or upgrade, see [Install Azure CLI][install-azure-cli].
* Review [Storage options for applications in Azure Kubernetes Service][aks-storage-concepts] to plan your storage configuration.

## Limitations

The following limitations apply when you create AKS clusters that support multiple node pools:

* See [Quotas, virtual machine size restrictions, and region availability in Azure Kubernetes Service (AKS)](quotas-skus-regions.md).
* You can delete system node pools if you have another system node pool to take its place in the AKS cluster. Otherwise, you cannot delete the system node pool.
* System pools must contain at least one node, and user node pools may contain zero or more nodes.
* The AKS cluster must use the Standard SKU load balancer to use multiple node pools. This feature isn't supported with Basic SKU load balancers.
* The AKS cluster must use Virtual Machine Scale Sets for the nodes.
* The name of a node pool may only contain lowercase alphanumeric characters and must begin with a lowercase letter.
  * For Linux node pools, the length must be between 1-12 characters.
  * For Windows node pools, the length must be between 1-6 characters.
* All node pools must reside in the same virtual network.
* When you create multiple node pools at cluster creation time, the Kubernetes versions for the node pools must match the version set for the control plane.

## Create an AKS cluster

> [!IMPORTANT]
> If you run a single system node pool for your AKS cluster in a production environment, we recommend you use at least three nodes for the node pool. If one node goes down, you lose control plane resources and redundancy is compromised. You can mitigate this risk by having more control plane nodes.

1. Create an Azure resource group using the [`az group create`][az-group-create] command.

    ```azurecli-interactive
    az group create --name $RESOURCE_GROUP_NAME --location $LOCATION
    ```

2. Create an AKS cluster with a single node pool using the [`az aks create`][az-aks-create] command.

    ```azurecli-interactive
    az aks create \
        --resource-group $RESOURCE_GROUP_NAME \
        --name $CLUSTER_NAME \
        --vm-set-type VirtualMachineScaleSets \
        --node-count 2 \
        --generate-ssh-keys \
        --load-balancer-sku standard \
        --generate-ssh-keys
    ```

    It takes a few minutes to create the cluster.

3. When the cluster is ready, get the cluster credentials using the [`az aks get-credentials`][az-aks-get-credentials] command.

    ```azurecli-interactive
    az aks get-credentials --resource-group $RESOURCE_GROUP_NAME --name $CLUSTER_NAME
    ```

## Add a node pool

The cluster created in the previous step has a single node pool. In this section, we add a second node pool to the cluster.

1. Create a new node pool using the [`az aks nodepool add`][az-aks-nodepool-add] command. The following example creates a node pool named *mynodepool* that runs *three* nodes:

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --name $NODE_POOL_NAME \
        --node-count 3
    ```

2. Check the status of your node pools using the [`az aks node pool list`][az-aks-nodepool-list] command and specify your resource group and cluster name.

    ```azurecli-interactive
    az aks nodepool list --resource-group $RESOURCE_GROUP_NAME --cluster-name $CLUSTER_NAME
    ```

    The following example output shows *mynodepool* has been successfully created with three nodes. When the AKS cluster was created in the previous step, a default *nodepool1* was created with a node count of *2*.

    ```output
    [
      {
        ...
        "count": 3,
        ...
        "name": "mynodepool",
        "orchestratorVersion": "1.15.7",
        ...
        "vmSize": "Standard_DS2_v2",
        ...
      },
      {
        ...
        "count": 2,
        ...
        "name": "nodepool1",
        "orchestratorVersion": "1.15.7",
        ...
        "vmSize": "Standard_DS2_v2",
        ...
      }
    ]
    ```

## ARM64 node pools

The ARM64 processor provides low power compute for your Kubernetes workloads. To create an ARM64 node pool, you need to choose a [Dpsv5][arm-sku-vm1], [Dplsv5][arm-sku-vm2] or [Epsv5][arm-sku-vm3] series Virtual Machine.

### Limitations

* ARM64 node pools aren't supported on Defender-enabled clusters with Kubernetes version less than 1.29.0.
* FIPS-enabled node pools aren't supported with ARM64 SKUs.

### Add an ARM64 node pool

* Add an ARM64 node pool into your existing cluster using the [`az aks nodepool add`][az-aks-nodepool-add].

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --name $ARM_NODE_POOL_NAME \
        --node-count 3 \
        --node-vm-size Standard_D2pds_v5
    ```

## Azure Linux node pools

The Azure Linux container host for AKS is an open-source Linux distribution available as an AKS container host. It provides high reliability, security, and consistency. It only includes the minimal set of packages needed for running container workloads, which improve boot times and overall performance.

### Add an Azure Linux node pool

* Add an Azure Linux node pool into your existing cluster using the [`az aks nodepool add`][az-aks-nodepool-add] command and specify `--os-sku AzureLinux`.

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --name $AZ_LINUX_NODE_POOL_NAME \
        --os-sku AzureLinux
    ```

### Migrate Ubuntu nodes to Azure Linux nodes

You can migrate your existing Ubuntu nodes to Azure Linux using one of the following methods:

* [Remove existing node pools and add new Azure Linux node pools](../azure-linux/tutorial-azure-linux-migration.md#add-azure-linux-node-pools-and-remove-existing-node-pools).
* [In-place OS SKU migration (preview)](../azure-linux/tutorial-azure-linux-migration.md#in-place-os-sku-migration-preview).

## Node pools with unique subnets

A workload may require splitting cluster nodes into separate pools for logical isolation. Separate subnets dedicated to each node pool in the cluster can help support this isolation, which can address requirements such as having noncontiguous virtual network address space to split across node pools.

> [!NOTE]
> Make sure to use Azure CLI version `2.35.0` or later.

### Limitations

* All subnets assigned to node pools must belong to the same virtual network.
* System pods must have access to all nodes and pods in the cluster to provide critical functionality, such as DNS resolution and tunneling kubectl logs/exec/port-forward proxy.
* If you expand your VNET after creating the cluster, you must update your cluster before adding a subnet outside the original CIDR block. While AKS errors-out on the agent pool add, the `aks-preview` Azure CLI extension (version 0.5.66 and higher) now supports running [`az aks update`][az-aks-update] command with only the required `-g <resourceGroup> -n <clusterName>` arguments. This command performs an update operation without making any changes, which can recover a cluster stuck in a failed state.
* In clusters with Kubernetes version less than 1.23.3, kube-proxy SNATs traffic from new subnets, which can cause Azure Network Policy to drop the packets.
* Windows nodes SNAT traffic to the new subnets until the node pool is reimaged.
* Internal load balancers default to one of the node pool subnets.

### Add a node pool with a unique subnet

* Add a node pool with a unique subnet into your existing cluster using the [`az aks nodepool add`][az-aks-nodepool-add] command and specify the `--vnet-subnet-id`.

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --name $NODE_POOL_NAME \
        --node-count 3 \
        --vnet-subnet-id $SUBNET_RESOURCE_ID
    ```

## FIPS-enabled node pools

For more information on enabling Federal Information Process Standard (FIPS) for your AKS cluster, see [Enable Federal Information Process Standard (FIPS) for Azure Kubernetes Service (AKS) node pools][enable-fips-nodes].

## Windows Server node pools with `containerd`

Beginning in Kubernetes version 1.20 and higher, you can specify `containerd` as the container runtime for Windows Server 2019 node pools. Starting with Kubernetes 1.23, `containerd` is the default and only container runtime for Windows.

> [!IMPORTANT]
> When using `containerd` with Windows Server 2019 node pools:
>
> * Both the control plane and Windows Server 2019 node pools must use Kubernetes version 1.20 or greater.
> * When you create or update a node pool to run Windows Server containers, the default value for `--node-vm-size` is *Standard_D2s_v3*, which was minimum recommended size for Windows Server 2019 node pools prior to Kubernetes version 1.20. The minimum recommended size for Windows Server 2019 node pools using `containerd` is *Standard_D4s_v3*. When setting the `--node-vm-size` parameter, check the list of [restricted VM sizes][restricted-vm-sizes].
> * We recommended using [taints or labels][aks-taints] with your Windows Server 2019 node pools running `containerd` and tolerations or node selectors with your deployments to guarantee your workloads are scheduled correctly.

### Add a Windows Server node pool with `containerd`

* Add a Windows Server node pool with `containerd` into your existing cluster using the [`az aks nodepool add`][az-aks-nodepool-add].

    > [!NOTE]
    > If you don't specify the `WindowsContainerRuntime=containerd` custom header, the node pool still uses `containerd` as the container runtime by default.

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --os-type Windows \
        --name $CONTAINER_D_NODE_POOL_NAME \
        --node-vm-size Standard_D4s_v3 \
        --kubernetes-version 1.20.5 \
        --aks-custom-headers WindowsContainerRuntime=containerd \
        --node-count 1
    ```

### Upgrade a specific existing Windows Server node pool to `containerd`

* Upgrade a specific node pool from Docker to `containerd` using the [`az aks nodepool upgrade`][az-aks-nodepool-upgrade] command.

    ```azurecli-interactive
    az aks nodepool upgrade \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --name $CONTAINER_D_NODE_POOL_NAME \
        --kubernetes-version 1.20.7 \
        --aks-custom-headers WindowsContainerRuntime=containerd
    ```

### Upgrade all existing Windows Server node pools to `containerd`

* Upgrade all node pools from Docker to `containerd` using the [`az aks nodepool upgrade`][az-aks-nodepool-upgrade] command.

    ```azurecli-interactive
    az aks nodepool upgrade \
        --resource-group $RESOURCE_GROUP_NAME \
        --cluster-name $CLUSTER_NAME \
        --kubernetes-version 1.20.7 \
        --aks-custom-headers WindowsContainerRuntime=containerd
    ```

## Node pools with Ephemeral OS disks

* Add a node pool that uses Ephemeral OS disks to an existing cluster using the [`az aks nodepool add`][az-aks-nodepool-add] command with the `--node-osdisk-type` flag set to `Ephemeral`.

    > [!NOTE]
    >
    > * You can specify Ephemeral OS disks during cluster creation using the `--node-osdisk-type` flag with the [`az aks create`][az-aks-create] command.
    > * If you want to create node pools with network-attached OS disks, you can do so by specifying `--node-osdisk-type Managed`.
    >

    ```azurecli-interactive
    az aks nodepool add --name $EPHEMERAL_NODE_POOL_NAME --cluster-name $CLUSTER_NAME --resource-group $RESOURCE_GROUP_NAME -s Standard_DS3_v2 --node-osdisk-type Ephemeral
    ```

> [!IMPORTANT]
> With Ephemeral OS, you can deploy VMs and instance images up to the size of the VM cache. The default node OS disk configuration in AKS uses 128 GB, which means that you need a VM size that has a cache larger than 128 GB. The default Standard_DS2_v2 has a cache size of 86 GB, which isn't large enough. The Standard_DS3_v2 VM SKU has a cache size of 172 GB, which is large enough. You can also reduce the default size of the OS disk by using `--node-osdisk-size`, but keep in mind the minimum size for AKS images is 30 GB.

## Delete a node pool

If you no longer need a node pool, you can delete it and remove the underlying VM nodes.

> [!CAUTION]
> When you delete a node pool, AKS doesn't perform cordon and drain, and there are no recovery options for data loss that may occur when you delete a node pool. If pods can't be scheduled on other node pools, those applications become unavailable. Make sure you don't delete a node pool when in-use applications don't have data backups or the ability to run on other node pools in your cluster. To minimize the disruption of rescheduling pods currently running on the node pool you want to delete, perform a cordon and drain on all nodes in the node pool before deleting.

* Delete a node pool using the [`az aks nodepool delete`][az-aks-nodepool-delete] command and specify the node pool name.

    ```azurecli-interactive
    az aks nodepool delete --resource-group $RESOURCE_GROUP_NAME --cluster-name $CLUSTER_NAME --name $NODE_POOL_NAME --no-wait
    ```

    It takes a few minutes to delete the nodes and the node pool.

## Next steps

In this article, you learned how to create multiple node pools in an AKS cluster. To learn about how to manage multiple node pools, see [Manage multiple node pools for a cluster in Azure Kubernetes Service (AKS)](manage-node-pools.md).

<!-- LINKS -->
[aks-storage-concepts]: concepts-storage.md
[arm-sku-vm1]: ../virtual-machines/dpsv5-dpdsv5-series.md
[arm-sku-vm2]: ../virtual-machines/dplsv5-dpldsv5-series.md
[arm-sku-vm3]: ../virtual-machines/epsv5-epdsv5-series.md
[az-aks-get-credentials]: /cli/azure/aks#az_aks_get_credentials
[az-aks-create]: /cli/azure/aks#az_aks_create
[az-aks-update]: /cli/azure/aks#az_aks_update
[az-aks-nodepool]: /cli/azure/aks/nodepool
[az-aks-nodepool-add]: /cli/azure/aks/nodepool#az_aks_nodepool_add
[az-aks-nodepool-list]: /cli/azure/aks/nodepool#az_aks_nodepool_list
[az-aks-nodepool-upgrade]: /cli/azure/aks/nodepool#az_aks_nodepool_upgrade
[az-aks-nodepool-delete]: /cli/azure/aks/nodepool#az_aks_nodepool_delete
[az-group-create]: /cli/azure/group#az_group_create
[enable-fips-nodes]: enable-fips-nodes.md
[install-azure-cli]: /cli/azure/install-azure-cli
[use-system-pool]: use-system-pools.md
[restricted-vm-sizes]: ../virtual-machines/sizes.md
[aks-taints]: manage-node-pools.md#set-node-pool-taints

