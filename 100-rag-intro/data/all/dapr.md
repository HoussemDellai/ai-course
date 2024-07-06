---
title: Dapr extension for Azure Kubernetes Service (AKS) and Arc-enabled Kubernetes
description: Install and configure Dapr on your Azure Kubernetes Service (AKS) and Arc-enabled Kubernetes clusters using the Dapr cluster extension.
author: greenie-msft
ms.author: nigreenf
ms.service: azure-kubernetes-service
ms.topic: article
ms.date: 02/14/2024
ms.subservice: aks-developer
ms.custom: devx-track-azurecli, references_regions
---

# Dapr extension for Azure Kubernetes Service (AKS) and Arc-enabled Kubernetes

[Dapr](./dapr-overview.md) simplifies building resilient, stateless, and stateful applications that run on the cloud and edge and embrace the diversity of languages and developer frameworks. With Dapr's sidecar architecture, you can keep your code platform agnostic while tackling challenges around building microservices, like:
- Calling other services reliably and securely
- Building event-driven apps with pub/sub
- Building applications that are portable across multiple cloud services and hosts (for example, Kubernetes vs. a VM)

> [!NOTE]
> If you plan on installing Dapr in a Kubernetes production environment, see the [Dapr guidelines for production usage][kubernetes-production] documentation page.

## How it works

The Dapr extension uses the Azure CLI or a Bicep template to provision the Dapr control plane on your AKS or Arc-enabled Kubernetes cluster, creating the following Dapr services:

| Dapr service | Description |
| ------------ | ----------- | 
| `dapr-operator` | Manages component updates and Kubernetes services endpoints for Dapr (state stores, pub/subs, etc.) |
| `dapr-sidecar-injector` | Injects Dapr into annotated deployment pods and adds the environment variables `DAPR_HTTP_PORT` and `DAPR_GRPC_PORT` to enable user-defined applications to easily communicate with Dapr without hard-coding Dapr port values. |
| `dapr-placement` | Used for actors only. Creates mapping tables that map actor instances to pods. |
| `dapr-sentry` | Manages mTLS between services and acts as a certificate authority. For more information, read the [security overview][dapr-security]. |

Once Dapr is installed on your cluster, you can begin to develop using the Dapr building block APIs by [adding a few annotations][dapr-deployment-annotations] to your deployments. For a more in-depth overview of the building block APIs and how to best use them, see the [Dapr building blocks overview][building-blocks-concepts].

> [!WARNING]
> If you install Dapr through the AKS or Arc-enabled Kubernetes extension, our recommendation is to continue using the extension for future management of Dapr instead of the Dapr CLI. Combining the two tools can cause conflicts and result in undesired behavior.

## Prerequisites 

- An Azure subscription. [Don't have one? Create a free account.](https://azure.microsoft.com/free/?WT.mc_id=A261C142F)
- Install the latest version of the [Azure CLI][install-cli].
- If you don't have one already, you need to create an [AKS cluster][deploy-cluster] or connect an [Arc-enabled Kubernetes cluster][arc-k8s-cluster].
- Make sure you have [an Azure Kubernetes Service RBAC Admin role](../role-based-access-control/built-in-roles.md#azure-kubernetes-service-rbac-admin) 

Select how you'd like to install, deploy, and configure the Dapr extension.

# [Azure CLI](#tab/cli)

### Set up the Azure CLI extension for cluster extensions

Install the `k8s-extension` Azure CLI extension by running the following commands:

```azurecli-interactive
az extension add --name k8s-extension
```

If the `k8s-extension` extension is already installed, you can update it to the latest version using the following command:

```azurecli-interactive
az extension update --name k8s-extension
```

### Register the `KubernetesConfiguration` resource provider

If you haven't previously used cluster extensions, you may need to register the resource provider with your subscription. You can check the status of the provider registration using the [az provider list][az-provider-list] command, as shown in the following example:

```azurecli-interactive
az provider list --query "[?contains(namespace,'Microsoft.KubernetesConfiguration')]" -o table
```

The *Microsoft.KubernetesConfiguration* provider should report as *Registered*, as shown in the following example output:

```output
Namespace                          RegistrationState    RegistrationPolicy
---------------------------------  -------------------  --------------------
Microsoft.KubernetesConfiguration  Registered           RegistrationRequired
```

If the provider shows as *NotRegistered*, register the provider using the [az provider register][az-provider-register] as shown in the following example:

```azurecli-interactive
az provider register --namespace Microsoft.KubernetesConfiguration
```

## Create the extension and install Dapr on your AKS or Arc-enabled Kubernetes cluster

When installing the Dapr extension, use the flag value that corresponds to your cluster type:

- **AKS cluster**: `--cluster-type managedClusters`. 
- **Arc-enabled Kubernetes cluster**: `--cluster-type connectedClusters`.

> [!NOTE]
> If you're using Dapr OSS on your AKS cluster and would like to install the Dapr extension for AKS, read more about [how to successfully migrate to the Dapr extension][dapr-migration]. 

Create the Dapr extension, which installs Dapr on your AKS or Arc-enabled Kubernetes cluster. 

For example, install the latest version of Dapr via the Dapr extension on your AKS cluster:
```azurecli
az k8s-extension create --cluster-type managedClusters \
--cluster-name myAKSCluster \
--resource-group myResourceGroup \
--name dapr \
--extension-type Microsoft.Dapr \
--auto-upgrade-minor-version false
```

### Configuring automatic updates to Dapr control plane

> [!WARNING]
> You can enable automatic updates to the Dapr control plane only in dev or test environments. Auto-upgrade is not suitable for production environments.

If you install Dapr without specifying a version, `--auto-upgrade-minor-version` *is automatically enabled*, configuring the Dapr control plane to automatically update its minor version on new releases.

You can disable auto-update by specifying the `--auto-upgrade-minor-version` parameter and setting the value to `false`. 

[Dapr versioning is in `MAJOR.MINOR.PATCH` format](https://docs.dapr.io/operations/support/support-versioning/#versioning), which means `1.11.0` to `1.12.0` is a _minor_ version upgrade.

```azurecli
--auto-upgrade-minor-version true
```

### Targeting a specific Dapr version

> [!NOTE]
> Dapr is supported with a rolling window, including only the current and previous versions. It is your operational responsibility to remain up to date with these supported versions. If you have an older version of Dapr, you may have to do intermediate upgrades to get to a supported version.

The same command-line argument is used for installing a specific version of Dapr or rolling back to a previous version. Set `--auto-upgrade-minor-version` to `false` and `--version` to the version of Dapr you wish to install. If the `version` parameter is omitted, the extension installs the latest version of Dapr. For example, to use Dapr 1.11.2:

```azurecli
az k8s-extension create --cluster-type managedClusters \
--cluster-name myAKSCluster \
--resource-group myResourceGroup \
--name dapr \
--extension-type Microsoft.Dapr \
--auto-upgrade-minor-version false \
--version 1.11.2
```

### Choosing a release train

When configuring the extension, you can choose to install Dapr from a particular release train. Specify one of the two release train values:

| Value    | Description                               |
| -------- | ----------------------------------------- |
| `stable` | Default.                                  |
| `dev`    | Early releases, can contain experimental features. Not suitable for production. |

For example:

```azurecli
--release-train stable
```

# [Bicep](#tab/bicep)

### Register the `KubernetesConfiguration` resource provider

If you haven't previously used cluster extensions, you may need to register the resource provider with your subscription. You can check the status of the provider registration using the [az provider list][az-provider-list] command, as shown in the following example:

```azurecli-interactive
az provider list --query "[?contains(namespace,'Microsoft.KubernetesConfiguration')]" -o table
```

The *Microsoft.KubernetesConfiguration* provider should report as *Registered*, as shown in the following example output:

```output
Namespace                          RegistrationState    RegistrationPolicy
---------------------------------  -------------------  --------------------
Microsoft.KubernetesConfiguration  Registered           RegistrationRequired
```

If the provider shows as *NotRegistered*, register the provider using the [az provider register][az-provider-register] as shown in the following example:

```azurecli-interactive
az provider register --namespace Microsoft.KubernetesConfiguration
```

## Deploy the Dapr extension on your AKS or Arc-enabled Kubernetes cluster

Create a Bicep template similar to the following example to deploy the Dapr extension to your existing cluster. 

```bicep
@description('The name of the Managed Cluster resource.')
param clusterName string

resource existingManagedClusters 'Microsoft.ContainerService/managedClusters@2023-05-02-preview' existing = {
  name: clusterName
}

resource daprExtension 'Microsoft.KubernetesConfiguration/extensions@2022-11-01' = {
  name: 'dapr'
  scope: existingManagedClusters
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    autoUpgradeMinorVersion: true
    configurationProtectedSettings: {}
    configurationSettings: {
      'global.clusterType': 'managedclusters'
    }
    extensionType: 'microsoft.dapr'
    releaseTrain: 'stable'
    scope: {
      cluster: {
        releaseNamespace: 'dapr-system'
      }
    }
    version: '1.11.2'
  }
}
```

Set the following variables, changing the values below to your actual resource group and cluster names.

```azurecli-interactive
MY_RESOURCE_GROUP=myResourceGroup
MY_AKS_CLUSTER=myAKScluster
```

Deploy the Bicep template using the `az deployment group` command. 

```azurecli-interactive
az deployment group create \
  --resource-group $MY_RESOURCE_GROUP \
  --template-file ./my-bicep-file-path.bicep \
  --parameters clusterName=$MY_AKS_CLUSTER
```

### Configuring automatic updates to Dapr control plane

> [!WARNING]
> You can enable automatic updates to the Dapr control plane only in dev or test environments. Auto-upgrade is not suitable for production environments.

If you deploy Dapr without specifying a version, `autoUpgradeMinorVersion` *is automatically enabled*, configuring the Dapr control plane to automatically update its minor version on new releases.

You can disable auto-update by specifying the `autoUpgradeMinorVersion` parameter and setting the value to `false`. 

[Dapr versioning is in `MAJOR.MINOR.PATCH` format](https://docs.dapr.io/operations/support/support-versioning/#versioning), which means `1.11.0` to `1.12.0` is a _minor_ version upgrade.

```bicep
properties {
  autoUpgradeMinorVersion: true
}
```

### Targeting a specific Dapr version

> [!NOTE]
> Dapr is supported with a rolling window, including only the current and previous versions. It is your operational responsibility to remain up to date with these supported versions. If you have an older version of Dapr, you may have to do intermediate upgrades to get to a supported version.

Set `autoUpgradeMinorVersion` to `false` and `version` to the version of Dapr you wish to install. If the `autoUpgradeMinorVersion` parameter is set to `true`, and `version` parameter is omitted, the extension installs the latest version of Dapr. 

For example, to use Dapr 1.11.2:

```bicep
properties: {
  autoUpgradeMinorVersion: false
  version: '1.11.2'
}
```

### Choosing a release train

When configuring the extension, you can choose to install Dapr from a particular release train. Specify one of the two release train values:

| Value    | Description                               |
| -------- | ----------------------------------------- |
| `stable` | Default.                                  |
| `dev`    | Early releases, can contain experimental features. Not suitable for production. |

For example:

```bicep
properties: {
  releaseTrain: 'stable'
}
```

---

## Troubleshooting extension errors

If the extension fails to create or update, try suggestions and solutions in the [Dapr extension troubleshooting guide](./dapr-troubleshooting.md).

### Troubleshooting Dapr

Troubleshoot Dapr errors via the [common Dapr issues and solutions guide][dapr-troubleshooting].

## Delete the extension

If you need to delete the extension and remove Dapr from your AKS cluster, you can use the following command: 

```azurecli
az k8s-extension delete --resource-group myResourceGroup --cluster-name myAKSCluster --cluster-type managedClusters --name dapr
```

Or simply remove the Bicep template.

## Next Steps

- Learn more about [extra settings and preferences you can set on the Dapr extension][dapr-settings].
- Once you have successfully provisioned Dapr in your AKS cluster, try deploying a [sample application][sample-application].
- Try out [Dapr Workflow on your Dapr extension for AKS][dapr-workflow]

<!-- LINKS INTERNAL -->
[deploy-cluster]: ./tutorial-kubernetes-deploy-cluster.md
[az-feature-register]: /cli/azure/feature#az-feature-register
[az-feature-list]: /cli/azure/feature#az-feature-list
[az-provider-register]: /cli/azure/provider#az-provider-register
[sample-application]: ./quickstart-dapr.md
[k8s-version-support-policy]: ./supported-kubernetes-versions.md?tabs=azure-cli#kubernetes-version-support-policy
[arc-k8s-cluster]: ../azure-arc/kubernetes/quickstart-connect-cluster.md
[install-cli]: /cli/azure/install-azure-cli
[dapr-migration]: ./dapr-migration.md
[dapr-settings]: ./dapr-settings.md
[dapr-workflow]: ./dapr-workflow.md

<!-- LINKS EXTERNAL -->
[kubernetes-production]: https://docs.dapr.io/operations/hosting/kubernetes/kubernetes-production
[building-blocks-concepts]: https://docs.dapr.io/developing-applications/building-blocks/
[dapr-configuration-options]: https://github.com/dapr/dapr/blob/master/charts/dapr/README.md#configuration
[sample-application]: https://github.com/dapr/quickstarts/tree/master/hello-kubernetes#step-2---create-and-configure-a-state-store
[dapr-security]: https://docs.dapr.io/concepts/security-concept/
[dapr-deployment-annotations]: https://docs.dapr.io/operations/hosting/kubernetes/kubernetes-overview/#adding-dapr-to-a-kubernetes-deployment
[dapr-oss-support]: https://docs.dapr.io/operations/support/support-release-policy/
[dapr-supported-version]: https://docs.dapr.io/operations/support/support-release-policy/#supported-versions
[dapr-troubleshooting]: https://docs.dapr.io/operations/troubleshooting/common_issues/
[supported-cloud-regions]: https://azure.microsoft.com/global-infrastructure/services/?products=azure-arc

