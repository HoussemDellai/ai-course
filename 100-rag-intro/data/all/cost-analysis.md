---
title: Azure Kubernetes Service cost analysis
description: Learn how to use cost analysis to surface granular cost allocation data for your Azure Kubernetes Service (AKS) cluster.
author: nickomang
ms.author: nickoman
ms.service: azure-kubernetes-service
ms.subservice: aks-monitoring
ms.custom: ignite-2023, devx-track-azurecli, build-2024
ms.topic: how-to
ms.date: 05/06/2024

#CustomerIntent: As a cluster operator, I want to obtain cost management information, perform cost attribution, and improve my cluster footprint
---

# Azure Kubernetes Service cost analysis

An Azure Kubernetes Service (AKS) cluster is reliant on Azure resources like virtual machines, virtual disks, load-balancers, and public IP addresses. Multiple applications can use these resources, which might be maintained by different teams within your organization. Resource consumption patterns for those applications are often variable, so their contribution towards the total cluster resource cost can also vary. Some applications can also have footprints across multiple clusters, which can pose a challenge when performing cost attribution and cost management.

Previously, [Microsoft Cost Management (MCM)](../cost-management-billing/cost-management-billing-overview.md) aggregated cluster resource consumption under the cluster resource group. You could use MCM to analyze costs, but there were several challenges:

* There was no Azure-native capability to display cluster resource usage at a level more granular than a cluster. There was no breakdown into discrete categories such as compute (including CPU cores and memory), storage, and networking.

* There was no Azure-native functionality to distinguish between types of costs, for example between individual application costs and shared costs. MCM reported the cost of resources, but there was no insight into how much of the resource cost was used to run individual applications, how much was reserved for system processes required by the cluster, or what were the idle costs associated with the cluster.

* There was no Azure-native mechanism to analyze costs across multiple clusters in the same subscription scope.

As a result, you might have used third-party solutions to gather and analyze resource consumption and costs by Kubernetes-specific levels of granularity, such as by namespace or pod. Third-party solutions, however, require effort to deploy, fine-tune, and maintain for each AKS cluster. In some cases, you even need to pay for advanced features, increasing the cluster's total cost of ownership.

To address this challenge, AKS has integrated with MCM to offer detailed cost drill-down scoped to Kubernetes constructs, such as cluster and namespace, in addition to Azure Compute, Network, and Storage categories.

The AKS cost analysis addon is built on top of [OpenCost](https://www.opencost.io/), an open-source Cloud Native Computing Foundation Sandbox project for usage data collection. The cost analysis is reconciled with your Azure invoice data. Post-processed data is visible directly in the [MCM Cost Analysis portal experience](/azure/cost-management-billing/costs/quick-acm-cost-analysis).

## Prerequisites and limitations

* Your cluster must be either `Standard` or `Premium` tier, not the `Free` tier.

* To view cost analysis information, you must have one of the following roles on the subscription hosting the cluster: Owner, Contributor, Reader, Cost management contributor, or Cost management reader.

* Once you have enabled cost analysis, you can't downgrade your cluster to the `Free` tier without first disabling cost analysis.

* Your cluster must be deployed with a [Microsoft Entra Workload ID](./workload-identity-overview.md) configured.

* Kubernetes cost views are available only for the following Microsoft Azure Offer types. For more information on offer types, see [Supported Microsoft Azure offers](/azure/cost-management-billing/costs/understand-cost-mgt-data#supported-microsoft-azure-offers). 
    * Enterprise Agreement
    * Microsoft Customer Agreement

* Access to the Azure API including Azure Resource Manager (ARM) API. For a list of fully qualified domain names (FQDNs) required, see [AKS Cost Analysis required FQDN](./outbound-rules-control-egress.md#aks-cost-analysis-add-on).

* Virtual nodes aren't supported at this time.

* AKS Automatic is not supported at this time.

* If using the Azure CLI, you must have version `2.44.0` or later installed, and the `aks-preview` Azure CLI extension version `0.5.155` or later installed.

### Install or update the `aks-preview` Azure CLI extension

Install the `aks-preview` Azure CLI extension using the [`az extension add`][az-extension-add] command.

```azurecli-interactive
az extension add --name aks-preview
```

If you need to update the extension version, you can do this using the [`az extension update`][az-extension-update] command.

```azurecli-interactive
az extension update --name aks-preview
```

## Enable cost analysis on your AKS cluster

You can enable the cost analysis with the `--enable-cost-analysis` flag during one of the following operations:

* Create a `Standard` or `Premium` tier AKS cluster.

* Update an AKS cluster that is already in `Standard` or `Premium` tier.

* Upgrade a `Free` cluster to `Standard` or `Premium`.

* Upgrade a `Standard` cluster to `Premium`.

* Downgrade a `Premium` cluster to `Standard` tier.

The following example creates a new AKS cluster in the `Standard` tier with cost analysis enabled:

```azurecli-interactive
az aks create --resource-group <resource-group> --name <cluster-name> --location <location> --enable-managed-identity --generate-ssh-keys --tier standard --enable-cost-analysis
```

The following example updates an existing AKS cluster in the `Standard` tier to enable cost analysis:

```azurecli-interactive
az aks update --resource-group <resource-group> --name <cluster-name> --enable-cost-analysis
```

> [!WARNING]
> The AKS cost analysis addon Memory usage is dependent on the number of containers deployed. Memory consumption can be roughly approximated by 200MB + 0.5MB per Container. The current memory limit is set to 4GB which will support approximately 7000 containers per cluster but could be more or less depending on various factors. These estimates are subject to change.

## Disable cost analysis

You can disable cost analysis at any time using `az aks update`.

```azurecli-interactive
az aks update --name myAKSCluster --resource-group myResourceGroup --disable-cost-analysis
```

> [!NOTE]
> If you intend to downgrade your cluster from the `Standard` or `Premium` tiers to the `Free` tier while cost analysis is enabled, you must first explicitly disable cost analysis as shown here.

## View the cost data

You can view cost allocation data in the Azure portal. To learn more about how to navigate the cost analysis UI view, see the [Cost Management documentation](/azure/cost-management-billing/costs/view-kubernetes-costs). 

### Cost definitions

In the Kubernetes namespaces and assets views you'll see the following charges:

- **Idle charges**: Represents the cost of available resource capacity that wasn't used by any workloads.
- **Service charges**: Represents the charges associated with the service like Uptime SLA, Microsoft Defender for Containers etc.
- **System charges**: Represents the cost of capacity reserved by AKS on each node to run system processes required by the cluster, including the kubelet and container runtime. [Learn more](./concepts-clusters-workloads.md#resource-reservations).
- **Unallocated charges**: Represents the cost of resources that couldn't be allocated to namespaces.

> [!NOTE]
> It might take up to one day for data to finalize. After 24 hours, any fluctuations in costs for the previous day will have stabilized.

## Troubleshooting

See the following guide to troubleshoot [AKS cost analysis add-on issues](/troubleshoot/azure/azure-kubernetes/aks-cost-analysis-add-on-issues).

<!-- LINKS -->
[az-extension-add]: /cli/azure/extension#az-extension-add
[az-extension-update]: /cli/azure/extension#az-extension-update

## Learn more

Visibility is one element of cost management. Refer to [Optimize Costs in Azure Kubernetes Service (AKS)](./best-practices-cost.md) for other best practices on how to gain control over your kubernetes cost.
