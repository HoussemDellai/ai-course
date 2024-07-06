---
title: Azure Kubernetes Service (AKS) Free, Standard and Premium pricing tiers for cluster management
description: Learn about the Azure Kubernetes Service (AKS) Free, Standard, and Premium pricing plans and what features, deployment patterns, and recommendations to consider between each plan.
ms.topic: conceptual
ms.date: 04/07/2023
author: schaffererin
ms.author: schaffererin

ms.custom: references_regions, devx-track-azurecli
---

# Free, Standard and Premium pricing tiers for Azure Kubernetes Service (AKS) cluster management

Azure Kubernetes Service (AKS) is now offering three pricing tiers for cluster management: the **Free tier**, the **Standard tier** and the **Premium tier**. All tiers are in the **Base** sku. 

|                  |Free tier|Standard tier|Premium tier |
|------------------|---------|--------|
|**When to use**|• You want to experiment with AKS at no extra cost <br> • You're new to AKS and Kubernetes|• You're running production or mission-critical workloads and need high availability and reliability <br> • You need a financially backed SLA |• You're running production or mission-critical workloads and need high availability and reliability <br> • You need a financially backed SLA. <br>• All mission critical, at scale or production workloads requiring 2 years of support|
|**Supported cluster types**|• Development clusters or small scale testing environments <br> • Clusters with fewer than 10 nodes|• Enterprise-grade or production workloads <br> • Clusters with up to 5,000 nodes| • Enterprise-grade or production workloads <br> • Clusters with up to 5,000 nodes |
|**Pricing**|• Free cluster management <br> • Pay-as-you-go for resources you consume|• Pay-as-you-go for resources you consume <br> • [Standard tier Cluster Management Pricing](https://azure.microsoft.com/pricing/details/kubernetes-service/) | • Pay-as-you-go for resources you consume <br> • [Premium tier Cluster Management Pricing](https://azure.microsoft.com/pricing/details/kubernetes-service/) |
|**Feature comparison**|• Recommended for clusters with fewer than 10 nodes, but can support up to 1,000 nodes <br> • Includes all current AKS features|• Uptime SLA is enabled by default <br> • Greater cluster reliability and resources <br> • Can support up to 5,000 nodes in a cluster <br> • Includes all current AKS features | • Includes all current AKS features from standard tier <br> • [Microsoft maintenance past community support][long-term-support] |

> [!IMPORTANT]
>
> Uptime SLA has been repositioned as a default feature included with the Standard tier.
>
> The repositioning will result in the following API changes:
>
> | SKU      |Prior to 2023-02-01 API|Starting from 2023-02-01 API|
> |----------|-----------|------------|
> |ManagedClusterSKUName|"Basic"|"Base"|
> |ManagedClusterSKUTier|"Free" <br> "Paid"|"Free" <br> "Standard"|
>
> "Basic" and "Paid" are removed in the 2023-02-01 and 2023-02-02 Preview API version, and this will be a breaking change in API versions 2023-02-01 and 2023-02-02 Preview or newer. If you use automated scripts, CD pipelines, ARM templates, Terraform, or other third-party tooling that relies on the above parameters, please be sure to update the API parameters to use "Base" with "Free" or "Base" with "Standard" before upgrading to the 2023-02-01 and 2023-02-02 Preview API or newer API versions. 

For more information on pricing, see the [AKS pricing details](https://azure.microsoft.com/pricing/details/kubernetes-service/).

## Uptime SLA terms and conditions

In the Standard tier, the Uptime SLA feature is enabled by default per cluster. The Uptime SLA feature guarantees 99.95% availability of the Kubernetes API server endpoint for clusters using [Availability Zones][availability-zones], and 99.9% of availability for clusters that aren't using Availability Zones.For more information, see [SLA](https://azure.microsoft.com/support/legal/sla/kubernetes-service/v1_1/).

## Region availability

* Free tier and Standard tier are available in public regions and Azure Government regions where [AKS is supported](https://azure.microsoft.com/global-infrastructure/services/?products=kubernetes-service).
* Free tier and Standard tier are available for [private AKS clusters][private-clusters] in all public regions where AKS is supported.

## Before you begin

Make sure you have installed [Azure CLI](/cli/azure/install-azure-cli) version 2.47.0 or later. Run `az --version` to find your current version. If you need to install or upgrade, see [Install Azure CLI][install-azure-cli].

## Create a new cluster and select the pricing tier

Use the Azure CLI to create a new cluster on an AKS pricing tier. You can create your cluster in an existing resource group or create a new one. To learn more about resource groups and working with them, see [managing resource groups using the Azure CLI][manage-resource-group-cli].

Use the [`az aks create`][az-aks-create] command to create an AKS cluster. The commands below show you how to create a new resource group named *myResourceGroup* and a cluster named *myAKSCluster* in that resource group in each tier.

```azurecli-interactive
# Create a new AKS cluster in the Free tier

az aks create \
    --resource-group myResourceGroup \
    --name myAKSCluster \
    --tier free \
    --generate-ssh-keys

# Create a new AKS cluster in the Standard tier

az aks create \
    --resource-group myResourceGroup \
    --name myAKSCluster \
    --tier standard \
    --generate-ssh-keys

# Create a new AKS cluster in the Premium tier
# LongTermSupport and Premium tier should be enabled/disabled together

az aks create \
    --resource-group myResourceGroup \
    --name myAKSCluster \
    --tier premium \
    --k8s-support-plan AKSLongTermSupport \
    --generate-ssh-keys
```

Once the deployment completes, it returns JSON-formatted information about your cluster:

```output
# Sample output for --tier free

  },
  "sku": {
    "name": "Base",
    "tier": "Free"
  },

# Sample output for --tier standard

  },
  "sku": {
    "name": "Base",
    "tier": "Standard"
  },

# Sample output for --tier premium

  "sku": {
    "name": "Base",
    "tier": "Premium"
  },
  "supportPlan": "AKSLongTermSupport",
```

## Update the tier of an existing AKS cluster

The following example uses the [`az aks update`](/cli/azure/aks#az_aks_update) command to update the existing cluster.

```azurecli-interactive
# Update an existing cluster from the Standard tier to the Free tier

az aks update --resource-group myResourceGroup --name myAKSCluster --tier free

# Update an existing cluster from the Free tier to the Standard tier

az aks update --resource-group myResourceGroup --name myAKSCluster --tier standard
```

To [update existing clusters from and to the Premium tier][long-term-support-update] it requires also the changing the support plan.

```azurecli-interactive
# Update an existing cluster to the Premium tier
az aks update --resource-group myResourceGroup --name myAKSCluster --tier premium --k8s-support-plan AKSLongTermSupport

# Update an existing cluster to from Premium tier to Free or Standard tier
az aks update --resource-group myResourceGroup --name myAKSCluster --tier [free|standard] --k8s-support-plan KubernetesOfficial
```

This process takes several minutes to complete. You shouldn't experience any downtime while your cluster tier is being updated. When finished, the following example JSON snippet shows updating the existing cluster to the Standard tier in the Base SKU.

```output
  },
  "sku": {
    "name": "Base",
    "tier": "Standard"
  },
```

## Next steps

* Use [Availability Zones][availability-zones] to increase high availability with your AKS cluster workloads.
* Configure your cluster to [limit egress traffic](limit-egress-traffic.md).

[manage-resource-group-cli]: ../azure-resource-manager/management/manage-resource-groups-cli.md
[availability-zones]: ./availability-zones.md
[az-aks-create]: /cli/azure/aks?#az_aks_create
[private-clusters]: private-clusters.md
[long-term-support]: long-term-support.md
[long-term-support-update]: long-term-support.md#enable-lts-on-an-existing-cluster
[install-azure-cli]: /cli/azure/install-azure-cli

