---
title: Set up a custom domain name and SSL certificate with the application routing add-on for Azure Kubernetes Service (AKS)
description: Understand the advanced configuration options that are supported with the application routing add-on for Azure Kubernetes Service (AKS). 
ms.subservice: aks-networking
ms.custom: devx-track-azurecli
ms.topic: how-to
ms.date: 12/04/2023
---

# Set up a custom domain name and SSL certificate with the application routing add-on

An Ingress is an API object that defines rules, which allow external access to services in an Azure Kubernetes Service (AKS) cluster. When you create an Ingress object that uses the application routing add-on nginx Ingress classes, the add-on creates, configures, and manages one or more Ingress controllers in your AKS cluster.

This article shows you how to set up an advanced Ingress configuration to encrypt the traffic with SSL/TLS certificates stored in an Azure Key Vault, and use Azure DNS to manage DNS zones.

## Application routing add-on with nginx features

The application routing add-on with nginx delivers the following:

* Easy configuration of managed nginx Ingress controllers.
* Integration with an external DNS such as [Azure DNS][azure-dns-overview] for global and private zone management
* SSL termination with certificates stored in a key vault, such as [Azure Key Vault][azure-key-vault-overview].

## Prerequisites

- An AKS cluster with the [application routing add-on][app-routing-add-on-basic-configuration].
- Azure Key Vault if you want to configure SSL termination and store certificates in the vault hosted in Azure.
- Azure DNS if you want to configure global and private zone management and host them in Azure.
- To attach an Azure Key Vault or Azure DNS Zone, you need the [Owner][rbac-owner], [Azure account administrator][rbac-classic], or [Azure co-administrator][rbac-classic] role on your Azure subscription.

## Connect to your AKS cluster

To connect to the Kubernetes cluster from your local computer, you use `kubectl`, the Kubernetes command-line client. You can install it locally using the [az aks install-cli][az-aks-install-cli] command. If you use the Azure Cloud Shell, `kubectl` is already installed.

Configure kubectl to connect to your Kubernetes cluster using the [`az aks get-credentials`][az-aks-get-credentials] command.

```azurecli-interactive
az aks get-credentials --resource-group <ResourceGroupName> --name <ClusterName>
```

## Terminate HTTPS traffic with certificates from Azure Key Vault

To enable support for HTTPS traffic, see the following prerequisites:

* An SSL certificate. If you don't have one, you can [create a certificate][create-and-export-a-self-signed-ssl-certificate].

### Create an Azure Key Vault to store the certificate

> [!NOTE]
> If you already have an Azure Key Vault, you can skip this step.

Create an Azure Key Vault using the [`az keyvault create`][az-keyvault-create] command.

```azurecli-interactive
az keyvault create --resource-group <ResourceGroupName> --location <Location> --name <KeyVaultName> --enable-rbac-authorization true
```

### Create and export a self-signed SSL certificate

For testing, you can use a self-signed public certificate instead of a Certificate Authority (CA)-signed certificate. If you already have a certificate, you can skip this step.

> [!CAUTION]
> Self-signed certificates are digital certificates that are not signed by a trusted third-party CA. Self-signed certificates are created, issued, and signed by the company or developer who is responsible for the website or software being signed. This is why self-signed certificates are considered unsafe for public-facing websites and applications. Azure Key Vault has a [trusted partnership with the some Certificate Authorities](../key-vault/certificates/how-to-integrate-certificate-authority.md).

1. Create a self-signed SSL certificate to use with the Ingress using the `openssl req` command. Make sure you replace *`<Hostname>`* with the DNS name you're using.

    ```bash
    openssl req -new -x509 -nodes -out aks-ingress-tls.crt -keyout aks-ingress-tls.key -subj "/CN=<Hostname>" -addext "subjectAltName=DNS:<Hostname>"
    ```

2. Export the SSL certificate and skip the password prompt using the `openssl pkcs12 -export` command.

    ```bash
    openssl pkcs12 -export -in aks-ingress-tls.crt -inkey aks-ingress-tls.key -out aks-ingress-tls.pfx
    ```

### Import certificate into Azure Key Vault

Import the SSL certificate into Azure Key Vault using the [`az keyvault certificate import`][az-keyvault-certificate-import] command. If your certificate is password protected, you can pass the password through the `--password` flag.

```azurecli-interactive
az keyvault certificate import --vault-name <KeyVaultName> --name <KeyVaultCertificateName> --file aks-ingress-tls.pfx [--password <certificate password if specified>]
```

> [!IMPORTANT]
> To enable the add-on to reload certificates from Azure Key Vault when they change, you should to enable the [secret autorotation feature][csi-secrets-store-autorotation] of the Secret Store CSI driver with the `--enable-secret-rotation` argument. When autorotation is enabled, the driver updates the pod mount and the Kubernetes secret by polling for changes periodically, based on the rotation poll interval you define. The default rotation poll interval is two minutes.

### Enable Azure Key Vault integration

On a cluster with the application routing add-on enabled, use the [`az aks approuting update`][az-aks-approuting-update] command using the `--enable-kv` and  `--attach-kv` arguments to enable the Azure Key Vault provider for Secrets Store CSI Driver and apply the required role assignments.

Azure Key Vault offers [two authorization systems][authorization-systems]: **Azure role-based access control (Azure RBAC)**, which operates on the management plane, and the **access policy model**, which operates on both the management plane and the data plane. The `--attach-kv` operation will choose the appropriate access model to use.

> [!NOTE]
> The `az aks approuting update --attach-kv` command uses the permissions of the user running the command to create the Azure Key Vault role assignment. This role is assigned to the add-on's managed identity. For more information on AKS managed identities, see [Summary of managed identities][summary-msi].

Retrieve the Azure Key Vault resource ID.

```azurecli-interactive
KEYVAULTID=$(az keyvault show --name <KeyVaultName> --query "id" --output tsv)
```

Then update the app routing add-on to enable the Azure Key Vault secret store CSI driver and apply the role assignment.

```azurecli-interactive
az aks approuting update --resource-group <ResourceGroupName> --name <ClusterName> --enable-kv --attach-kv ${KEYVAULTID}
```

## Enable Azure DNS integration

To enable support for DNS zones, review the following prerequisite:

* The app routing add-on can be configured to automatically create records on one or more Azure global and private DNS zones for hosts defined on Ingress resources. All global Azure DNS zones need to be in the same resource group, and all private Azure DNS zones need to be in the same resource group. If you don't have an Azure DNS zone, you can [create one][create-an-azure-dns-zone].


### Create a public Azure DNS zone

> [!NOTE]
> If you already have an Azure DNS Zone, you can skip this step.

1. Create an Azure DNS zone using the [`az network dns zone create`][az-network-dns-zone-create] command.

    ```azurecli-interactive
    az network dns zone create --resource-group <ResourceGroupName> --name <ZoneName>
    ```

### Attach Azure DNS zone to the application routing add-on

> [!NOTE]
> The `az aks approuting zone add` command uses the permissions of the user running the command to create the Azure DNS Zone role assignment. This role is assigned to the add-on's managed identity. For more   information on AKS managed identities, see [Summary of managed identities][summary-msi].

1. Retrieve the resource ID for the DNS zone using the [`az network dns zone show`][az-network-dns-zone-show] command and set the output to a variable named *ZONEID*.

    ```azurecli-interactive
    ZONEID=$(az network dns zone show --resource-group <ResourceGroupName> --name <ZoneName> --query "id" --output tsv)
    ```

1. Update the add-on to enable the integration with Azure DNS using the [`az aks approuting zone`][az-aks-approuting-zone] command. You can pass a comma-separated list of DNS zone resource IDs.

    ```azurecli-interactive
    az aks approuting zone add --resource-group <ResourceGroupName> --name <ClusterName> --ids=${ZONEID} --attach-zones
    ```

## Create the Ingress that uses a host name and a certificate from Azure Key Vault

The application routing add-on creates an Ingress class on the cluster named *webapprouting.kubernetes.azure.com*. When you create an Ingress object with this class, it activates the add-on.

1. Get the certificate URI to use in the Ingress from Azure Key Vault using the [`az keyvault certificate show`][az-keyvault-certificate-show] command.

    ```azurecli-interactive
    az keyvault certificate show --vault-name <KeyVaultName> --name <KeyVaultCertificateName> --query "id" --output tsv
    ```

   The following example output shows the certificate URI returned from the command:

    ```output
    https://KeyVaultName.vault.azure.net/certificates/KeyVaultCertificateName/ea62e42260f04f17a9309d6b87aceb44
    ```

2. Copy the following YAML manifest into a new file named **ingress.yaml** and save the file to your local computer.

   Update *`<Hostname>`* with the name of your DNS host and *`<KeyVaultCertificateUri>`* with the URI returned from the command to query Azure Key Vault in step 1 above. The string value for `*<KeyVaultCertificateUri>*` should only include `https://yourkeyvault.vault.azure.net/certificates/certname`. The *Certificate Version* at the end of the URI string should be omitted in order to get the current version.

   The *`secretName`* key in the `tls` section defines the name of the secret that contains the certificate for this Ingress resource. This certificate is presented in the browser when a client browses to the URL specified in the `<Hostname>` key. Make sure that the value of `secretName` is equal to `keyvault-` followed by the value of the Ingress resource name (from `metadata.name`). In the example YAML, `secretName` needs to be equal to `keyvault-<your Ingress name>`.

    ```yml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      annotations:
        kubernetes.azure.com/tls-cert-keyvault-uri: <KeyVaultCertificateUri>
      name: aks-helloworld
      namespace: hello-web-app-routing
    spec:
      ingressClassName: webapprouting.kubernetes.azure.com
      rules:
      - host: <Hostname>
        http:
          paths:
          - backend:
              service:
                name: aks-helloworld
                port:
                  number: 80
            path: /
            pathType: Prefix
      tls:
      - hosts:
        - <Hostname>
        secretName: keyvault-<your ingress name>
    ```

3. Create the cluster resources using the [`kubectl apply`][kubectl-apply] command.

    ```bash
    kubectl apply -f ingress.yaml -n hello-web-app-routing
    ```

    The following example output shows the created resource:

    ```output
    Ingress.networking.k8s.io/aks-helloworld created
    ```

## Verify the managed Ingress was created

You can verify the managed Ingress was created using the [`kubectl get ingress`][kubectl-get] command.

```bash
kubectl get ingress -n hello-web-app-routing
```

The following example output shows the created managed Ingress:

```output
NAME             CLASS                                HOSTS               ADDRESS       PORTS     AGE
aks-helloworld   webapprouting.kubernetes.azure.com   myapp.contoso.com   20.51.92.19   80, 443   4m
```

## Next steps

Learn about monitoring the Ingress-nginx controller metrics included with the application routing add-on with [with Prometheus in Grafana][prometheus-in-grafana] as part of analyzing the performance and usage of your application.

<!-- LINKS - external -->
[kubectl-apply]: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#apply
[kubectl-get]: https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#get

<!-- LINKS - internal -->
[summary-msi]: use-managed-identity.md#summary-of-managed-identities
[rbac-owner]: ../role-based-access-control/built-in-roles.md#owner
[rbac-classic]: ../role-based-access-control/rbac-and-directory-admin-roles.md#classic-subscription-administrator-roles
[app-routing-add-on-basic-configuration]: app-routing.md
[csi-secrets-store-autorotation]: csi-secrets-store-configuration-options.md#enable-and-disable-auto-rotation
[azure-key-vault-overview]: ../key-vault/general/overview.md
[az-aks-approuting-update]: /cli/azure/aks/approuting#az-aks-approuting-update
[az-aks-approuting-zone]: /cli/azure/aks/approuting/zone
[az-network-dns-zone-show]: /cli/azure/network/dns/zone#az-network-dns-zone-show
[az-network-dns-zone-create]: /cli/azure/network/dns/zone#az-network-dns-zone-create
[az-keyvault-certificate-import]: /cli/azure/keyvault/certificate#az-keyvault-certificate-import
[az-keyvault-create]: /cli/azure/keyvault#az-keyvault-create
[authorization-systems]: ../key-vault/general/rbac-access-policy.md
[az-aks-install-cli]: /cli/azure/aks#az-aks-install-cli
[az-aks-get-credentials]: /cli/azure/aks#az-aks-get-credentials
[create-and-export-a-self-signed-ssl-certificate]: #create-and-export-a-self-signed-ssl-certificate
[create-an-azure-dns-zone]: #create-a-public-azure-dns-zone
[azure-dns-overview]: ../dns/dns-overview.md
[az-keyvault-certificate-show]: /cli/azure/keyvault/certificate#az-keyvault-certificate-show
[prometheus-in-grafana]: app-routing-nginx-prometheus.md
