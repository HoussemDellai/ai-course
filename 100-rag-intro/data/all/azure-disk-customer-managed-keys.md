---
title: Use a customer-managed key to encrypt Azure managed disks in Azure Kubernetes Service (AKS)
description: Bring your own keys (BYOK) to encrypt managed OS and data disks in AKS.
ms.topic: article
ms.custom: devx-track-azurecli
ms.subservice: aks-storage
ms.date: 02/01/2024
author: tamram
ms.author: tamram

---

# Bring your own keys (BYOK) with Azure managed disks in Azure Kubernetes Service (AKS)

Azure encrypts all data in a managed disk at rest. By default, data is encrypted with Microsoft-managed keys. For more control over encryption keys, you can supply customer-managed keys to use for encryption at rest for both the OS and data disks for your AKS clusters.

Learn more about customer-managed keys on [Linux][customer-managed-keys-linux] and [Windows][customer-managed-keys-windows].

## Prerequisites

* You must enable soft delete and purge protection for *Azure Key Vault* when using Key Vault to encrypt managed disks.
* You need the Azure CLI version 2.11.1 or later.
* Data disk encryption and customer-managed keys are supported on Kubernetes versions 1.24 and higher.
* If you choose to rotate (change) your keys periodically, see [Customer-managed keys and encryption of Azure managed disk](../virtual-machines/disk-encryption.md) for more information.

## Limitations

* Encryption of an OS disk with customer-managed keys can only be enabled when creating an AKS cluster.
* Virtual nodes are not supported.
* When encrypting an ephemeral OS disk-enabled node pool with customer-managed keys, if you want to rotate the key in Azure Key Vault, you need to:

   * Scale down the node pool count to 0
   * Rotate the key
   * Scale up the node pool to the original count.

## Create an Azure Key Vault instance

Use an Azure Key Vault instance to store your keys.  You can optionally use the Azure portal to [Configure customer-managed keys with Azure Key Vault][byok-azure-portal]

Create a new *resource group*, then create a new *Key Vault* instance and enable soft delete and purge protection.  Ensure you use the same region and resource group names for each command.

```azurecli-interactive
# Optionally retrieve Azure region short names for use on upcoming commands
az account list-locations
```

```azurecli-interactive
# Create new resource group in a supported Azure region
az group create --location myAzureRegionName --name myResourceGroup

# Create an Azure Key Vault resource in a supported Azure region
az keyvault create --name myKeyVaultName --resource-group myResourceGroup --location myAzureRegionName  --enable-purge-protection true
```

## Create an instance of a DiskEncryptionSet

Replace *myKeyVaultName* with the name of your key vault. You also need a *key* stored in Azure Key Vault to complete the following steps. Either store your existing Key in the Key Vault you created on the previous steps, or [generate a new key][key-vault-generate] and replace *myKeyName* with the name of your key.

```azurecli-interactive
# Retrieve the Key Vault Id and store it in a variable
keyVaultId=$(az keyvault show --name myKeyVaultName --query "[id]" -o tsv)

# Retrieve the Key Vault key URL and store it in a variable
keyVaultKeyUrl=$(az keyvault key show --vault-name myKeyVaultName --name myKeyName --query "[key.kid]" -o tsv)

# Create a DiskEncryptionSet
az disk-encryption-set create --name myDiskEncryptionSetName --location myAzureRegionName --resource-group myResourceGroup --source-vault $keyVaultId --key-url $keyVaultKeyUrl
```

> [!IMPORTANT]
> Make sure that the DiskEncryptionSet is located in the same region as your AKS cluster and that the AKS cluster identity has **read** access to the DiskEncryptionSet.

## Grant the DiskEncryptionSet access to key vault

Use the DiskEncryptionSet and resource groups you created on the prior steps, and grant the DiskEncryptionSet resource access to the Azure Key Vault.

```azurecli-interactive
# Retrieve the DiskEncryptionSet value and set a variable
desIdentity=$(az disk-encryption-set show --name myDiskEncryptionSetName --resource-group myResourceGroup --query "[identity.principalId]" -o tsv)

# Update security policy settings
az keyvault set-policy --name myKeyVaultName --resource-group myResourceGroup --object-id $desIdentity --key-permissions wrapkey unwrapkey get
```

## Create a new AKS cluster and encrypt the OS disk

Either create a new resource group, or select an existing resource group hosting other AKS clusters, then use your key to encrypt either using network-attached OS disks or ephemeral OS disk. By default, a cluster uses ephemeral OS disk when possible in conjunction with VM size and OS disk size.

Run the following command to retrieve the DiskEncryptionSet value and set a variable:

```azurecli-interactive
diskEncryptionSetId=$(az disk-encryption-set show --name mydiskEncryptionSetName --resource-group myResourceGroup --query "[id]" -o tsv)
```

If you want to create a new resource group for the cluster, run the following command:

```azurecli-interactive
az group create --name myResourceGroup --location myAzureRegionName
```

To create a regular cluster using network-attached OS disks encrypted with your key, you can do so by specifying the `--node-osdisk-type=Managed` argument.

```azurecli-interactive
az aks create --name myAKSCluster --resource-group myResourceGroup --node-osdisk-diskencryptionset-id $diskEncryptionSetId --generate-ssh-keys --node-osdisk-type Managed
```

To create a cluster with ephemeral OS disk encrypted with your key, you can do so by specifying the `--node-osdisk-type=Ephemeral` argument. You also need to specify the argument `--node-vm-size` because the default vm size is too small and doesn't support ephemeral OS disk.

```azurecli-interactive
az aks create --name myAKSCluster --resource-group myResourceGroup --node-osdisk-diskencryptionset-id $diskEncryptionSetId --generate-ssh-keys --node-osdisk-type Ephemeral --node-vm-size Standard_DS3_v2
```

When new node pools are added to the cluster, the customer-managed key provided during the create process is used to encrypt the OS disk. The following example shows how to deploy a new node pool with an ephemeral OS disk.

```azurecli-interactive
az aks nodepool add --cluster-name $CLUSTER_NAME --resource-group $RG_NAME --name $NODEPOOL_NAME --node-osdisk-type Ephemeral
```

## Encrypt your AKS cluster data disk

If you have already provided a disk encryption set during cluster creation, encrypting data disks with the same disk encryption set is the default option. Therefore, this step is optional. However, if you want to encrypt data disks with a different disk encryption set, you can follow these steps.

> [!IMPORTANT]
> Ensure you have the proper AKS credentials. The managed identity needs to have contributor access to the resource group where the diskencryptionset is deployed. Otherwise, you'll get an error suggesting that the managed identity does not have permissions.

To assign the AKS cluster identity the Contributor role for the diskencryptionset, execute the following commands:

```azurecli-interactive
aksIdentity=$(az aks show --resource-group $RG_NAME --name $CLUSTER_NAME --query "identity.principalId")
az role assignment create --role "Contributor" --assignee $aksIdentity --scope $diskEncryptionSetId
```

Create a file called **byok-azure-disk.yaml** that contains the following information.  Replace *myAzureSubscriptionId*, *myResourceGroup*, and *myDiskEncrptionSetName* with your values, and apply the yaml.  Make sure to use the resource group where your DiskEncryptionSet is deployed.

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: byok
provisioner: disk.csi.azure.com # replace with "kubernetes.io/azure-disk" if aks version is less than 1.21
parameters:
  skuname: StandardSSD_LRS
  kind: managed
  diskEncryptionSetID: "/subscriptions/{myAzureSubscriptionId}/resourceGroups/{myResourceGroup}/providers/Microsoft.Compute/diskEncryptionSets/{myDiskEncryptionSetName}"
```

Next, run the following commands to update your AKS cluster:

```azurecli-interactive
# Get credentials
az aks get-credentials --name myAksCluster --resource-group myResourceGroup --output table

# Update cluster
kubectl apply -f byok-azure-disk.yaml
```

## Next steps

Review [best practices for AKS cluster security][best-practices-security]

<!-- LINKS - external -->

<!-- LINKS - internal -->
[best-practices-security]: ./operator-best-practices-cluster-security.md
[byok-azure-portal]: ../storage/common/customer-managed-keys-configure-key-vault.md
[customer-managed-keys-windows]: ../virtual-machines/disk-encryption.md#customer-managed-keys
[customer-managed-keys-linux]: ../virtual-machines/disk-encryption.md#customer-managed-keys
[key-vault-generate]: ../key-vault/general/manage-with-cli2.md
