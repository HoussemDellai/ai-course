---
title: Limit access to kubeconfig in Azure Kubernetes Service (AKS)
description: Learn how to control access to the Kubernetes configuration file (kubeconfig) for cluster administrators and cluster users
ms.topic: article
ms.subservice: aks-security
ms.custom: devx-track-azurecli
ms.date: 03/28/2023
---

# Use Azure role-based access control to define access to the Kubernetes configuration file in Azure Kubernetes Service (AKS)

You can interact with Kubernetes clusters using the `kubectl` tool. The Azure CLI provides an easy way to get the access credentials and *kubeconfig* configuration file to connect to your AKS clusters using `kubectl`. You can use Azure role-based access control (Azure RBAC) to limit who can get access to the *kubeconfig* file and the permissions they have.

This article shows you how to assign Azure roles that limit who can get the configuration information for an AKS cluster.

## Before you begin

* This article assumes that you have an existing AKS cluster. If you need an AKS cluster, create one using [Azure CLI][aks-quickstart-cli], [Azure PowerShell][aks-quickstart-powershell], or [the Azure portal][aks-quickstart-portal].
* This article also requires that you're running Azure CLI version 2.0.65 or later. Run `az --version` to find the version. If you need to install or upgrade, see [Install Azure CLI][azure-cli-install].

## Available permissions for cluster roles

When you interact with an AKS cluster using the `kubectl` tool, a configuration file, called *kubeconfig*, defines cluster connection information. This configuration file is typically stored in *~/.kube/config*. Multiple clusters can be defined in this *kubeconfig* file. You can switch between clusters using the [`kubectl config use-context`][kubectl-config-use-context] command.

The [`az aks get-credentials`][az-aks-get-credentials] command lets you get the access credentials for an AKS cluster and merges these credentials into the *kubeconfig* file. You can use Azure RBAC to control access to these credentials. These Azure roles let you define who can retrieve the *kubeconfig* file and what permissions they have within the cluster.

There are two Azure roles you can apply to a Microsoft Entra user or group:

- **Azure Kubernetes Service Cluster Admin Role**

     * Allows access to `Microsoft.ContainerService/managedClusters/listClusterAdminCredential/action` API call. This API call [lists the cluster admin credentials][api-cluster-admin].
     * Downloads *kubeconfig* for the *clusterAdmin* role.

- **Azure Kubernetes Service Cluster User Role**

     * Allows access to `Microsoft.ContainerService/managedClusters/listClusterUserCredential/action` API call. This API call [lists the cluster user credentials][api-cluster-user].
     * Downloads *kubeconfig* for *clusterUser* role.

> [!NOTE]
> On clusters that use Microsoft Entra ID, users with the *clusterUser* role have an empty *kubeconfig* file that prompts a login. Once logged in, users have access based on their Microsoft Entra user or group settings. Users with the *clusterAdmin* role have admin access.
>
> On clusters that don't use Microsoft Entra ID, the *clusterUser* role has same effect of *clusterAdmin* role.

## Assign role permissions to a user or group

To assign one of the available roles, you need to get the resource ID of the AKS cluster and the ID of the Microsoft Entra user account or group using the following steps:

1. Get the cluster resource ID using the [`az aks show`][az-aks-show] command for the cluster named *myAKSCluster* in the *myResourceGroup* resource group. Provide your own cluster and resource group name as needed.
2. Use the [`az account show`][az-account-show] and [`az ad user show`][az-ad-user-show] commands to get your user ID.
3. Assign a role using the [`az role assignment create`][az-role-assignment-create] command.

The following example assigns the *Azure Kubernetes Service Cluster Admin Role* to an individual user account:

```azurecli-interactive
# Get the resource ID of your AKS cluster
AKS_CLUSTER=$(az aks show --resource-group myResourceGroup --name myAKSCluster --query id -o tsv)

# Get the account credentials for the logged in user
ACCOUNT_UPN=$(az account show --query user.name -o tsv)
ACCOUNT_ID=$(az ad user show --id $ACCOUNT_UPN --query objectId -o tsv)

# Assign the 'Cluster Admin' role to the user
az role assignment create \
    --assignee $ACCOUNT_ID \
    --scope $AKS_CLUSTER \
    --role "Azure Kubernetes Service Cluster Admin Role"
```

If you want to assign permissions to a Microsoft Entra group, update the `--assignee` parameter shown in the previous example with the object ID for the *group* rather than the *user*.

To get the object ID for a group, use the [`az ad group show`][az-ad-group-show] command. The following command gets the object ID for the Microsoft Entra group named *appdev*:

```azurecli-interactive
az ad group show --group appdev --query objectId -o tsv
```

> [!IMPORTANT]
> In some cases, such as Microsoft Entra guest users, the *user.name* in the account is different than the *userPrincipalName*.
>
> ```azurecli-interactive
> $ az account show --query user.name -o tsv
> user@contoso.com
>
> $ az ad user list --query "[?contains(otherMails,'user@contoso.com')].{UPN:userPrincipalName}" -o tsv
> user_contoso.com#EXT#@contoso.onmicrosoft.com
> ```
>
> In this case, set the value of *ACCOUNT_UPN* to the *userPrincipalName* from the Microsoft Entra user. For example, if your account *user.name* is *user\@contoso.com*, this action would look like the following example:
>
> ```azurecli-interactive
> ACCOUNT_UPN=$(az ad user list --query "[?contains(otherMails,'user@contoso.com')].{UPN:userPrincipalName}" -o tsv)
> ```

## Get and verify the configuration information

Once the roles are assigned, use the [`az aks get-credentials`][az-aks-get-credentials] command to get the *kubeconfig* definition for your AKS cluster. The following example gets the *--admin* credentials, which works correctly if the user has been granted the *Cluster Admin Role*:

```azurecli-interactive
az aks get-credentials --resource-group myResourceGroup --name myAKSCluster --admin
```

You can then use the [`kubectl config view`][kubectl-config-view] command to verify that the *context* for the cluster shows that the admin configuration information has been applied.

```azurecli-interactive
$ kubectl config view
```

Your output should look similar to the following example output:

```azurecli-interactive
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: DATA+OMITTED
    server: https://myaksclust-myresourcegroup-19da35-4839be06.hcp.eastus.azmk8s.io:443
  name: myAKSCluster
contexts:
- context:
    cluster: myAKSCluster
    user: clusterAdmin_myResourceGroup_myAKSCluster
  name: myAKSCluster-admin
current-context: myAKSCluster-admin
kind: Config
preferences: {}
users:
- name: clusterAdmin_myResourceGroup_myAKSCluster
  user:
    client-certificate-data: REDACTED
    client-key-data: REDACTED
    token: e9f2f819a4496538b02cefff94e61d35
```

## Remove role permissions

To remove role assignments, use the [`az role assignment delete`][az-role-assignment-delete] command. Specify the account ID and cluster resource ID that you obtained in the previous steps. If you assigned the role to a group rather than a user, specify the appropriate group object ID rather than account object ID for the `--assignee` parameter.

```azurecli-interactive
az role assignment delete --assignee $ACCOUNT_ID --scope $AKS_CLUSTER
```

## Next steps

For enhanced security on access to AKS clusters, [integrate Microsoft Entra authentication][aad-integration].

<!-- LINKS - external -->
[kubectl-config-use-context]: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#config
[kubectl-config-view]: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#config

<!-- LINKS - internal -->
[aks-quickstart-cli]: ./learn/quick-kubernetes-deploy-cli.md
[aks-quickstart-portal]: ./learn/quick-kubernetes-deploy-portal.md
[aks-quickstart-powershell]: ./learn/quick-kubernetes-deploy-powershell.md
[azure-cli-install]: /cli/azure/install-azure-cli
[az-aks-get-credentials]: /cli/azure/aks#az_aks_get_credentials
[api-cluster-admin]: /rest/api/aks/managedclusters/listclusteradmincredentials
[api-cluster-user]: /rest/api/aks/managedclusters/listclusterusercredentials
[az-aks-show]: /cli/azure/aks#az_aks_show
[az-account-show]: /cli/azure/account#az_account_show
[az-ad-user-show]: /cli/azure/ad/user#az_ad_user_show
[az-role-assignment-create]: /cli/azure/role/assignment#az_role_assignment_create
[az-role-assignment-delete]: /cli/azure/role/assignment#az_role_assignment_delete
[aad-integration]: ./azure-ad-integration-cli.md
[az-ad-group-show]: /cli/azure/ad/group#az_ad_group_show
