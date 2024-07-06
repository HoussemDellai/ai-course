---
title: Create a managed or user-assigned NAT gateway for your Azure Kubernetes Service (AKS) cluster
titleSuffix: Azure Kubernetes Service
description: Learn how to create an AKS cluster with managed NAT integration and user-assigned NAT gateway.
author: asudbring
ms.subservice: aks-networking
ms.custom: devx-track-azurecli
ms.topic: how-to
ms.date: 01/10/2024
ms.author: allensu
---

# Create a managed or user-assigned NAT gateway for your Azure Kubernetes Service (AKS) cluster

While you can route egress traffic through an Azure Load Balancer, there are limitations on the number of outbound flows of traffic you can have. Azure NAT Gateway allows up to 64,512 outbound UDP and TCP traffic flows per IP address with a maximum of 16 IP addresses.

This article shows you how to create an Azure Kubernetes Service (AKS) cluster with a managed NAT gateway and a user-assigned NAT gateway for egress traffic. It also shows you how to disable OutboundNAT on Windows.

## Before you begin

* Make sure you're using the latest version of [Azure CLI][az-cli].
* Make sure you're using Kubernetes version 1.20.x or above.
* Managed NAT gateway is incompatible with custom virtual networks.

## Create an AKS cluster with a managed NAT gateway

* Create an AKS cluster with a new managed NAT gateway using the [`az aks create`][az-aks-create] command with the `--outbound-type managedNATGateway`, `--nat-gateway-managed-outbound-ip-count`, and `--nat-gateway-idle-timeout` parameters. If you want the NAT gateway to operate out of a specific availability zone, specify the zone using `--zones`.
* If no zone is specified when creating a managed NAT gateway, then NAT gateway is deployed to "no zone" by default. When NAT gateway is placed in **no zone**, Azure places the resource in a zone for you. For more information on non-zonal deployment model, see [non-zonal NAT gateway](/azure/nat-gateway/nat-availability-zones#non-zonal).
* A managed NAT gateway resource can't be used across multiple availability zones.

   ```azurecli-interactive
    az aks create \
        --resource-group myResourceGroup \
        --name myNatCluster \
        --node-count 3 \
        --outbound-type managedNATGateway \
        --nat-gateway-managed-outbound-ip-count 2 \
        --nat-gateway-idle-timeout 4 \
        --generate-ssh-keys
   ```

* Update the outbound IP address or idle timeout using the [`az aks update`][az-aks-update] command with the `--nat-gateway-managed-outbound-ip-count` or `--nat-gateway-idle-timeout` parameter.

    ```azurecli-interactive
    az aks update \ 
        --resource-group myResourceGroup \
        --name myNatCluster\
        --nat-gateway-managed-outbound-ip-count 5
    ```

## Create an AKS cluster with a user-assigned NAT gateway

This configuration requires bring-your-own networking (via [Kubenet][byo-vnet-kubenet] or [Azure CNI][byo-vnet-azure-cni]) and that the NAT gateway is preconfigured on the subnet. The following commands create the required resources for this scenario.



1. Create a resource group using the [`az group create`][az-group-create] command.

    ```azurecli-interactive
    az group create --name myResourceGroup \
        --location southcentralus
    ```

2. Create a managed identity for network permissions and store the ID to `$IDENTITY_ID` for later use.

    ```azurecli-interactive
    IDENTITY_ID=$(az identity create \
        --resource-group myResourceGroup \
        --name myNatClusterId \
        --location southcentralus \
        --query id \
        --output tsv)
    ```

3. Create a public IP for the NAT gateway using the [`az network public-ip create`][az-network-public-ip-create] command.

    ```azurecli-interactive
    az network public-ip create \
        --resource-group myResourceGroup \
        --name myNatGatewayPip \
        --location southcentralus \
        --sku standard
    ```

4. Create the NAT gateway using the [`az network nat gateway create`][az-network-nat-gateway-create] command.

    ```azurecli-interactive
    az network nat gateway create \
        --resource-group myResourceGroup \
        --name myNatGateway \
        --location southcentralus \
        --public-ip-addresses myNatGatewayPip
    ```
   > [!Important]
   > A single NAT gateway resource can't be used across multiple availability zones. To ensure zone-resiliency, it is recommended to deploy a NAT gateway resource to each availability zone and assign to subnets containing AKS clusters in each zone. For more information on this deployment model, see [NAT gateway for each zone](/azure/nat-gateway/nat-availability-zones#zonal-nat-gateway-resource-for-each-zone-in-a-region-to-create-zone-resiliency).
   > If no zone is configured for NAT gateway, the default zone placement is "no zone", in which Azure places NAT gateway into a zone for you.

5. Create a virtual network using the [`az network vnet create`][az-network-vnet-create] command.

    ```azurecli-interactive
    az network vnet create \
        --resource-group myResourceGroup \
        --name myVnet \
        --location southcentralus \
        --address-prefixes 172.16.0.0/20 
    ```

6. Create a subnet in the virtual network using the NAT gateway and store the ID to `$SUBNET_ID` for later use.

    ```azurecli-interactive
    SUBNET_ID=$(az network vnet subnet create \
        --resource-group myResourceGroup \
        --vnet-name myVnet \
        --name myNatCluster \
        --address-prefixes 172.16.0.0/22 \
        --nat-gateway myNatGateway \
        --query id \
        --output tsv)
    ```

7. Create an AKS cluster using the subnet with the NAT gateway and the managed identity using the [`az aks create`][az-aks-create] command.

    ```azurecli-interactive
    az aks create \
        --resource-group myResourceGroup \
        --name myNatCluster \
        --location southcentralus \
        --network-plugin azure \
        --vnet-subnet-id $SUBNET_ID \
        --outbound-type userAssignedNATGateway \
        --assign-identity $IDENTITY_ID \
        --generate-ssh-keys
    ```

## Disable OutboundNAT for Windows

Windows OutboundNAT can cause certain connection and communication issues with your AKS pods. An example issue is node port reuse. In this example, Windows OutboundNAT uses ports to translate your pod IP to your Windows node host IP, which can cause an unstable connection to the external service due to a port exhaustion issue.

Windows enables OutboundNAT by default. You can now manually disable OutboundNAT when creating new Windows agent pools.

### Prerequisites

* Existing AKS cluster with v1.26 or above. If you're using Kubernetes version 1.25 or older, you need to [update your deployment configuration][upgrade-kubernetes].

### Limitations

* You can't set cluster outbound type to LoadBalancer. You can set it to Nat Gateway or UDR:
  * [NAT Gateway](./nat-gateway.md): NAT Gateway can automatically handle NAT connection and is more powerful than Standard Load Balancer. You might incur extra charges with this option.
  * [UDR (UserDefinedRouting)](./limit-egress-traffic.md): You must keep port limitations in mind when configuring routing rules.
  * If you need to switch from a load balancer to NAT Gateway, you can either add a NAT gateway into the VNet or run [`az aks upgrade`][aks-upgrade] to update the outbound type.

> [!NOTE]
> UserDefinedRouting has the following limitations:
>
> * SNAT by Load Balancer (must use the default OutboundNAT) has "64 ports on the host IP".
> * SNAT by Azure Firewall (disable OutboundNAT) has 2496 ports per public IP.
> * SNAT by NAT Gateway (disable OutboundNAT) has 64512 ports per public IP.
> * If the Azure Firewall port range isn't enough for your application, you need to use NAT Gateway.
> * Azure Firewall doesn't SNAT with Network rules when the destination IP address is in a private IP address range per [IANA RFC 1918 or shared address space per IANA RFC 6598](../firewall/snat-private-range.md).

### Manually disable OutboundNAT for Windows

* Manually disable OutboundNAT for Windows when creating new Windows agent pools using the [`az aks nodepool add`][az-aks-nodepool-add] command with the `--disable-windows-outbound-nat` flag.

    > [!NOTE]
    > You can use an existing AKS cluster, but you might need to update the outbound type and add a node pool to enable `--disable-windows-outbound-nat`.

    ```azurecli-interactive
    az aks nodepool add \
        --resource-group myResourceGroup \
        --cluster-name myNatCluster \
        --name mynp \
        --node-count 3 \
        --os-type Windows \
        --disable-windows-outbound-nat
    ```

## Next steps

For more information on Azure NAT Gateway, see [Azure NAT Gateway][nat-docs].

<!-- LINKS - internal -->

<!-- LINKS - external-->
[nat-docs]: ../virtual-network/nat-gateway/nat-overview.md
[az-feature-list]: /cli/azure/feature#az_feature_list
[az-feature-register]: /cli/azure/feature#az_feature_register
[byo-vnet-azure-cni]: configure-azure-cni.md
[byo-vnet-kubenet]: configure-kubenet.md
[az-extension-add]: /cli/azure/extension#az_extension_add
[az-extension-update]: /cli/azure/extension#az_extension_update
[az-cli]: /cli/azure/install-azure-cli
[agic]: ../application-gateway/ingress-controller-overview.md
[app-gw]: ../application-gateway/overview.md
[upgrade-kubernetes]:tutorial-kubernetes-upgrade-cluster.md
[aks-upgrade]: /cli/azure/aks#az-aks-update
[az-aks-create]: /cli/azure/aks#az-aks-create
[az-aks-update]: /cli/azure/aks#az-aks-update
[az-group-create]: /cli/azure/group#az_group_create
[az-network-public-ip-create]: /cli/azure/network/public-ip#az_network_public_ip_create
[az-network-nat-gateway-create]: /cli/azure/network/nat/gateway#az_network_nat_gateway_create
[az-network-vnet-create]: /cli/azure/network/vnet#az_network_vnet_create
[az-aks-nodepool-add]: /cli/azure/aks/nodepool#az_aks_nodepool_add
[az-provider-register]: /cli/azure/provider#az_provider_register

