---
title: Access Azure Key Vault with the CSI Driver Identity Provider
description: Learn how to integrate the Azure Key Vault Provider for Secrets Store CSI Driver with your Azure credentials and user identities.
author: nickomang
ms.author: nickoman
ms.topic: article
ms.subservice: aks-security
ms.date: 12/19/2023
ms.custom: devx-track-azurecli
---

# Connect your Azure identity provider to the Azure Key Vault Secrets Store CSI Driver in Azure Kubernetes Service (AKS)

The Secrets Store Container Storage Interface (CSI) Driver on Azure Kubernetes Service (AKS) provides various methods of identity-based access to your Azure Key Vault. This article outlines these methods and best practices for when to use Role-based access control (RBAC) or OpenID Connect (OIDC) security models to access your key vault and AKS cluster.

You can use one of the following access methods:

- [Microsoft Entra Workload ID](#access-with-a-microsoft-entra-workload-id)
- [User-assigned managed identity](#access-with-a-user-assigned-managed-identity)

## Prerequisites for CSI Driver

- Before you begin, make sure you finish the steps in [Use the Azure Key Vault provider for Secrets Store CSI Driver in an Azure Kubernetes Service (AKS) cluster][csi-secrets-store-driver] to enable the Azure Key Vault Secrets Store CSI Driver in your AKS cluster.

<a name='access-with-an-azure-ad-workload-identity'></a>

## Access with a Microsoft Entra Workload ID

A [Microsoft Entra Workload ID][workload-identity] is an identity that an application running on a pod uses to authenticate itself against other Azure services, such as workloads in software. The Secret Store CSI Driver integrates with native Kubernetes capabilities to federate with external identity providers.

In this security model, the AKS cluster acts as token issuer. Microsoft Entra ID then uses OIDC to discover public signing keys and verify the authenticity of the service account token before exchanging it for a Microsoft Entra token. For your workload to exchange a service account token projected to its volume for a Microsoft Entra token, you need the Azure Identity client library in the Azure SDK or the Microsoft Authentication Library (MSAL)

> [!NOTE]
>
> - This authentication method replaces Microsoft Entra pod-managed identity (preview). The open source Microsoft Entra pod-managed identity (preview) in Azure Kubernetes Service has been deprecated as of 10/24/2022.
> - Microsoft Entra Workload ID is supports both Windows and Linux clusters.

### Configure workload identity

1. Set your subscription using the [`az account set`][az-account-set] command.

    ```azurecli-interactive
    export SUBSCRIPTION_ID=<subscription id>
    export RESOURCE_GROUP=<resource group name>
    export UAMI=<name for user assigned identity>
    export KEYVAULT_NAME=<existing keyvault name>
    export CLUSTER_NAME=<aks cluster name>

    az account set --subscription $SUBSCRIPTION_ID
    ```

2. Create a managed identity using the [`az identity create`][az-identity-create] command.

    ```azurecli-interactive
    az identity create --name $UAMI --resource-group $RESOURCE_GROUP

    export USER_ASSIGNED_CLIENT_ID="$(az identity show --resource-group $RESOURCE_GROUP --name $UAMI --query 'clientId' -o tsv)"
    export IDENTITY_TENANT=$(az aks show --name $CLUSTER_NAME --resource-group $RESOURCE_GROUP --query identity.tenantId -o tsv)
    ```

3. Create a role assignment that grants the workload identity permission to access the key vault secrets, access keys, and certificates using the [`az role assignment create`][az-role-assignment-create] command.

    > [!IMPORTANT]
    >
    > * If your key vault is set with `--enable-rbac-authorization` and you're using `key` or `certificate` type, assign the [`Key Vault Certificate User`](../key-vault/general/rbac-guide.md#azure-built-in-roles-for-key-vault-data-plane-operations) role to give permissions.
    > * If your key vault is set with `--enable-rbac-authorization` and you're using `secret` type, assign the [`Key Vault Secrets User`](../key-vault/general/rbac-guide.md#azure-built-in-roles-for-key-vault-data-plane-operations) role.
    > * If your key vault isn't set with `--enable-rbac-authorization`, you can use the [`az keyvault set-policy`][az-keyvault-set-policy] command with the `--key-permissions get`, `--certificate-permissions get`, or `--secret-permissions get` parameter to create a key vault policy to grant access for keys, certificates, or secrets. For example:
    >
    > ```azurecli-interactive
    > az keyvault set-policy --name $KEYVAULT_NAME --key-permissions get --object-id $IDENTITY_OBJECT_ID
    > ```

    ```azurecli-interactive
    export KEYVAULT_SCOPE=$(az keyvault show --name $KEYVAULT_NAME --query id -o tsv)

    # Example command for key vault with RBAC enabled using `key` type
    az role assignment create --role "Key Vault Certificate User" --assignee $USER_ASSIGNED_CLIENT_ID --scope $KEYVAULT_SCOPE
    ```

4. Get the AKS cluster OIDC Issuer URL using the [`az aks show`][az-aks-show] command.

    > [!NOTE]
    > This step assumes you have an existing AKS cluster with the OIDC Issuer URL enabled. If you don't have it enabled, see [Update an AKS cluster with OIDC Issuer](./use-oidc-issuer.md#update-an-aks-cluster-with-oidc-issuer) to enable it.

    ```bash
    export AKS_OIDC_ISSUER="$(az aks show --resource-group $RESOURCE_GROUP --name $CLUSTER_NAME --query "oidcIssuerProfile.issuerUrl" -o tsv)"
    echo $AKS_OIDC_ISSUER
    ```

5. Establish a federated identity credential between the Microsoft Entra application, service account issuer, and subject. Get the object ID of the Microsoft Entra application using the following commands. Make sure to update the values for `serviceAccountName` and `serviceAccountNamespace` with the Kubernetes service account name and its namespace.

    ```bash
    export SERVICE_ACCOUNT_NAME="workload-identity-sa"  # sample name; can be changed
    export SERVICE_ACCOUNT_NAMESPACE="default" # can be changed to namespace of your workload

    cat <<EOF | kubectl apply -f -
    apiVersion: v1
    kind: ServiceAccount
    metadata:
      annotations:
        azure.workload.identity/client-id: ${USER_ASSIGNED_CLIENT_ID}
      name: ${SERVICE_ACCOUNT_NAME}
      namespace: ${SERVICE_ACCOUNT_NAMESPACE}
    EOF
    ```

6. Create the federated identity credential between the managed identity, service account issuer, and subject using the [`az identity federated-credential create`][az-identity-federated-credential-create] command.

    ```bash
    export FEDERATED_IDENTITY_NAME="aksfederatedidentity" # can be changed as needed

    az identity federated-credential create --name $FEDERATED_IDENTITY_NAME --identity-name $UAMI --resource-group $RESOURCE_GROUP --issuer ${AKS_OIDC_ISSUER} --subject system:serviceaccount:${SERVICE_ACCOUNT_NAMESPACE}:${SERVICE_ACCOUNT_NAME}
    ```

7. Deploy a `SecretProviderClass` using the `kubectl apply` command and the following YAML script.

    ```bash
    cat <<EOF | kubectl apply -f -
    # This is a SecretProviderClass example using workload identity to access your key vault
    apiVersion: secrets-store.csi.x-k8s.io/v1
    kind: SecretProviderClass
    metadata:
      name: azure-kvname-wi # needs to be unique per namespace
    spec:
      provider: azure
      parameters:
        usePodIdentity: "false"
        clientID: "${USER_ASSIGNED_CLIENT_ID}" # Setting this to use workload identity
        keyvaultName: ${KEYVAULT_NAME}       # Set to the name of your key vault
        cloudName: ""                         # [OPTIONAL for Azure] if not provided, the Azure environment defaults to AzurePublicCloud
        objects:  |
          array:
            - |
              objectName: secret1             # Set to the name of your secret
              objectType: secret              # object types: secret, key, or cert
              objectVersion: ""               # [OPTIONAL] object versions, default to latest if empty
            - |
              objectName: key1                # Set to the name of your key
              objectType: key
              objectVersion: ""
        tenantId: "${IDENTITY_TENANT}"        # The tenant ID of the key vault
    EOF
    ```

    > [!NOTE]
    > If you use `objectAlias` instead of `objectName`, update the YAML script to account for it.

    > [!NOTE]
    > In order for the `SecretProviderClass` to function properly, make sure to populate your Azure Key Vault with secrets, keys, or certificates before referencing them in the `objects` section.

8. Deploy a sample pod using the `kubectl apply` command and the following YAML script.

    ```bash
    cat <<EOF | kubectl apply -f -
    # This is a sample pod definition for using SecretProviderClass and workload identity to access your key vault
    kind: Pod
    apiVersion: v1
    metadata:
      name: busybox-secrets-store-inline-wi
      labels:
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: "workload-identity-sa"
      containers:
        - name: busybox
          image: registry.k8s.io/e2e-test-images/busybox:1.29-4
          command:
            - "/bin/sleep"
            - "10000"
          volumeMounts:
          - name: secrets-store01-inline
            mountPath: "/mnt/secrets-store"
            readOnly: true
      volumes:
        - name: secrets-store01-inline
          csi:
            driver: secrets-store.csi.k8s.io
            readOnly: true
            volumeAttributes:
              secretProviderClass: "azure-kvname-wi"
    EOF
    ```

<a name='access-with-a-user-assigned-managed-identity'></a>

## Access with managed identity

A [Microsoft Entra Managed ID][managed-identity] is an identity that an administrator uses to authenticate themselves against other Azure services. The managed identity uses RBAC to federate with external identity providers.

In this security model, you can grant access to your cluster's resources to team members or tenants sharing a managed role. The role is checked for scope to access the keyvault and other credentials. When you [enabled the Azure Key Vault provider for Secrets Store CSI Driver on your AKS Cluster](./csi-secrets-store-driver.md#create-an-aks-cluster-with-azure-key-vault-provider-for-secrets-store-csi-driver-support), it created a user identity.

### Configure managed identity

1. Access your key vault using the [`az aks show`][az-aks-show] command and the user-assigned managed identity created by the add-on. You should also retrieve the identity's `clientId`, which you'll use in later steps when creating a `SecretProviderClass`.

    ```azurecli-interactive
    az aks show --resource-group <resource-group> --name <cluster-name> --query addonProfiles.azureKeyvaultSecretsProvider.identity.objectId -o tsv
    az aks show --resource-group <resource-group> --name <cluster-name> --query addonProfiles.azureKeyvaultSecretsProvider.identity.clientId -o tsv
    ```

    Alternatively, you can create a new managed identity and assign it to your virtual machine (VM) scale set or to each VM instance in your availability set using the following commands.

    ```azurecli-interactive
    az identity create -resource-group <resource-group> --name <identity-name>
    az vmss identity assign --resource-group <resource-group> --name <agent-pool-vmss> --identities <identity-resource-id>
    az vm identity assign --resource-group <resource-group> --name <agent-pool-vm> --identities <identity-resource-id>

    az identity show --resource-group <resource-group> --name <identity-name> --query 'clientId' -o tsv
    ```

2. Create a role assignment that grants the identity permission to access the key vault secrets, access keys, and certificates using the [`az role assignment create`][az-role-assignment-create] command.

    > [!IMPORTANT]
    >
    > * If your key vault is set with `--enable-rbac-authorization` and you're using `key` or `certificate` type, assign the [`Key Vault Certificate User`](../key-vault/general/rbac-guide.md#azure-built-in-roles-for-key-vault-data-plane-operations) role.
    > * If your key vault is set with `--enable-rbac-authorization` and you're using `secret` type, assign the [`Key Vault Secrets User`](../key-vault/general/rbac-guide.md#azure-built-in-roles-for-key-vault-data-plane-operations) role.
    > * If your key vault isn't set with `--enable-rbac-authorization`, you can use the [`az keyvault set-policy`][az-keyvault-set-policy] command with the `--key-permissions get`, `--certificate-permissions get`, or `--secret-permissions get` parameter to create a key vault policy to grant access for keys, certificates, or secrets. For example:
    >
    > ```azurecli-interactive
    > az keyvault set-policy --name $KEYVAULT_NAME --key-permissions get --object-id $IDENTITY_OBJECT_ID
    > ```

    ```azurecli-interactive
    export IDENTITY_OBJECT_ID="$(az identity show --resource-group <resource-group> --name <identity-name> --query 'principalId' -o tsv)"
    export KEYVAULT_SCOPE=$(az keyvault show --name <key-vault-name> --query id -o tsv)

    # Example command for key vault with RBAC enabled using `key` type
    az role assignment create --role "Key Vault Certificate User" --assignee $USER_ASSIGNED_CLIENT_ID --scope $KEYVAULT_SCOPE
    ```

3. Create a `SecretProviderClass` using the following YAML. Make sure to use your own values for `userAssignedIdentityID`, `keyvaultName`, `tenantId`, and the objects to retrieve from your key vault.

    ```yml
    # This is a SecretProviderClass example using user-assigned identity to access your key vault
    apiVersion: secrets-store.csi.x-k8s.io/v1
    kind: SecretProviderClass
    metadata:
      name: azure-kvname-user-msi
    spec:
      provider: azure
      parameters:
        usePodIdentity: "false"
        useVMManagedIdentity: "true"          # Set to true for using managed identity
        userAssignedIdentityID: <client-id>   # Set the clientID of the user-assigned managed identity to use
        keyvaultName: <key-vault-name>        # Set to the name of your key vault
        cloudName: ""                         # [OPTIONAL for Azure] if not provided, the Azure environment defaults to AzurePublicCloud
        objects:  |
          array:
            - |
              objectName: secret1
              objectType: secret              # object types: secret, key, or cert
              objectVersion: ""               # [OPTIONAL] object versions, default to latest if empty
            - |
              objectName: key1
              objectType: key
              objectVersion: ""
        tenantId: <tenant-id>                 # The tenant ID of the key vault
    ```

    > [!NOTE]
    > If you use `objectAlias` instead of `objectName`, make sure to update the YAML script.
    
    > [!NOTE]
    > In order for the `SecretProviderClass` to function properly, make sure to populate your Azure Key Vault with secrets, keys, or certificates before referencing them in the `objects` section.

4. Apply the `SecretProviderClass` to your cluster using the `kubectl apply` command.

    ```bash
    kubectl apply -f secretproviderclass.yaml
    ```

5. Create a pod using the following YAML.

    ```yml
    # This is a sample pod definition for using SecretProviderClass and the user-assigned identity to access your key vault
    kind: Pod
    apiVersion: v1
    metadata:
      name: busybox-secrets-store-inline-user-msi
    spec:
      containers:
        - name: busybox
          image: registry.k8s.io/e2e-test-images/busybox:1.29-4
          command:
            - "/bin/sleep"
            - "10000"
          volumeMounts:
          - name: secrets-store01-inline
            mountPath: "/mnt/secrets-store"
            readOnly: true
      volumes:
        - name: secrets-store01-inline
          csi:
            driver: secrets-store.csi.k8s.io
            readOnly: true
            volumeAttributes:
              secretProviderClass: "azure-kvname-user-msi"
    ```

6. Apply the pod to your cluster using the `kubectl apply` command.

    ```bash
    kubectl apply -f pod.yaml
    ```

## Validate Key Vault secrets

After the pod starts, the mounted content at the volume path specified in your deployment YAML is available. Use the following commands to validate your secrets and print a test secret.

1. Show secrets held in the secrets store using the following command.

    ```bash
    kubectl exec busybox-secrets-store-inline-user-msi -- ls /mnt/secrets-store/
    ```

2. Display a secret in the store using the following command. This example command shows the test secret `ExampleSecret`.

    ```bash
    kubectl exec busybox-secrets-store-inline-user-msi -- cat /mnt/secrets-store/ExampleSecret
    ```

## Obtain certificates and keys

The Azure Key Vault design makes sharp distinctions between keys, secrets, and certificates. The certificate features of the Key Vault service are designed to make use of key and secret capabilities. When you create a key vault certificate, it creates an addressable key and secret with the same name. This key allows authentication operations, and the secret allows the retrieval of the certificate value as a secret.

A key vault certificate also contains public x509 certificate metadata. The key vault stores both the public and private components of your certificate in a secret. You can obtain each individual component by specifying the `objectType` in `SecretProviderClass`. The following table shows which objects map to the various resources associated with your certificate:

| Object | Return value | Returns entire certificate chain |
|---|---|---|
|`key`|The public key, in Privacy Enhanced Mail (PEM) format.|N/A|
|`cert`|The certificate, in PEM format.|No|
|`secret`|The private key and certificate, in PEM format.|Yes|

## Disable the addon on existing clusters

> [!NOTE]
> Before you disable the add-on, ensure that *no* `SecretProviderClass` is in use. Trying to disable the add-on while a `SecretProviderClass` exists results in an error.

- Disable the Azure Key Vault provider for Secrets Store CSI Driver capability in an existing cluster using the [`az aks disable-addons`][az-aks-disable-addons] command with the `azure-keyvault-secrets-provider` add-on.

    ```azurecli-interactive
    az aks disable-addons --addons azure-keyvault-secrets-provider --resource-group myResourceGroup --name myAKSCluster
    ```

> [!NOTE]
> When you disable the add-on, existing workloads should have no issues or see any updates in the mounted secrets. If the pod restarts or a new pod is created as part of scale-up event, the pod fails to start because the driver is no longer running.

## Next steps

In this article, you learned how to create and provide an identity to access your Azure Key Vault. If you want to configure extra configuration options or perform troubleshooting, continue to the next article.

> [!div class="nextstepaction"]
> [Configuration options and troubleshooting resources for Azure Key Vault provider with Secrets Store CSI Driver in AKS](./csi-secrets-store-configuration-options.md)

<!-- LINKS INTERNAL -->

[csi-secrets-store-driver]: ./csi-secrets-store-driver.md
[az-aks-show]: /cli/azure/aks#az-aks-show
[az-identity-federated-credential-create]: /cli/azure/identity/federated-credential#az-identity-federated-credential-create
[workload-identity]: ./workload-identity-overview.md
[managed-identity]:/entra/identity/managed-identities-azure-resources/overview
[az-account-set]: /cli/azure/account#az-account-set
[az-identity-create]: /cli/azure/identity#az-identity-create
[az-role-assignment-create]: /cli/azure/role/assignment#az-role-assignment-create
[az-aks-disable-addons]: /cli/azure/aks#az-aks-disable-addons
[az-keyvault-set-policy]: /cli/azure/keyvault#az-keyvault-set-policy
