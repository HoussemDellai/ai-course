---
title: Abort an Azure Kubernetes Service (AKS) long running operation 
description: Learn how to terminate a long running operation on an Azure Kubernetes Service cluster at the node pool or cluster level.
ms.topic: article
ms.date: 3/23/2023
author: tamram
ms.author: tamram

ms.subservice: aks-nodes
---

# Terminate a long running operation on an Azure Kubernetes Service (AKS) cluster

Sometimes deployment or other processes running within pods on nodes in a cluster can run for periods of time longer than expected due to various reasons. You can get insight into the progress of any ongoing operation, such as create, upgrade, and scale, using any preview API version after `2024-01-02-preview` using the following az rest command:

```azurecli-interactive
export ResourceID="You cluster ResourceID"
az rest --method get --url "https://management.azure.com$ResourceID/operations/latest?api-version=2024-01-02-preview"
```

This command provides you with a percentage that indicates how close the operation is to completion. You can use this method to get these insights for up to 50 of the latest operations on your cluster. The "percentComplete" attribute denotes the extent of completion for the ongoing operation, as shown in the following example:

```azurecli-interactive
"id": "/subscriptions/26fe00f8-9173-4872-9134-bb1d2e00343a/resourcegroups/testStatus/providers/Microsoft.ContainerService/managedClusters/contoso/operations/fc10e97d-b7a8-4a54-84de-397c45f322e1",
  "name": "fc10e97d-b7a8-4a54-84de-397c45f322e1",
  "percentComplete": 10,
  "startTime": "2024-04-08T18:21:31Z",
  "status": "InProgress"
```

While it's important to allow operations to gracefully terminate when they're no longer needed, there are circumstances where you need to release control of node pools and clusters with long running operations using an *abort* command.

AKS support for aborting long running operations is now generally available. This feature allows you to take back control and run another operation seamlessly. This design is supported using the [Azure REST API](/rest/api/azure/) or the [Azure CLI](/cli/azure/).

The abort operation supports the following scenarios:

- If a long running operation is stuck or suspected to be in a bad state or failing, the operation can be aborted provided it's the last running operation on the Managed Cluster or agent pool.
- If a long running operation is stuck or failing, that operation can be aborted.
- An operation that was triggered in error can be aborted as long as the operation doesn't reach a terminal state first.

## Before you begin

- The Azure CLI version 2.47.0 or later. Run `az --version` to find the version, and run `az upgrade` to upgrade the version. If you need to install or upgrade, see [Install Azure CLI][install-azure-cli].

## Abort a long running operation

### [Azure CLI](#tab/azure-cli)

You can use the [az aks nodepool](/cli/azure/aks/nodepool) command with the `operation-abort` argument to abort an operation on a node pool or a managed cluster.

The following example terminates an operation on a node pool on a specified cluster.
```azurecli-interactive
az aks nodepool operation-abort --resource-group myResourceGroup --cluster-name myAKSCluster --name myNodePool 
```

The following example terminates an operation on a specified cluster.

```azurecli-interactive
az aks operation-abort --name myAKSCluster --resource-group myResourceGroup
```

In the response, an HTTP status code of 204 is returned.

### [Azure REST API](#tab/azure-rest)

You can use the Azure REST API [Abort](/rest/api/aks/managed-clusters) operation to stop an operation against the Managed Cluster.

The following example terminates a process for a specified agent pool.

```rest
/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.ContainerService/managedclusters/{resourceName}/agentPools/{agentPoolName}/abort
```

The following example terminates a process for a specified cluster.

```rest
/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.ContainerService/managedclusters/{resourceName}/abort
```

In the response, an HTTP status code of 204 is returned.

---

The provisioning state on the managed cluster or agent pool should be **Canceled**. Use the REST API [Get Managed Clusters](/rest/api/aks/managed-clusters/get) or [Get Agent Pools](/rest/api/aks/agent-pools/get) to verify the operation. The provisioning state should update to **Canceled** within a few seconds of the abort request being accepted. The operation status of last running operation ID on the managed cluster/agent pool, which can be retrieved by performing a GET operation against the Managed Cluster or agent pool, should show a status of **Canceling**.

When you terminate an operation, it doesn't roll back to the previous state and it stops at whatever step in the operation was in-process. Once complete, the cluster provisioning state shows a **Canceled** state. If the operation happens to be a cluster upgrade, during a cancel operation it stops where it is.

## Next steps

Learn more about [Container insights](../azure-monitor/containers/container-insights-overview.md) to understand how it helps you monitor the performance and health of your Kubernetes cluster and container workloads.

<!-- LINKS - internal -->
[install-azure-cli]: /cli/azure/install-azure-cli

