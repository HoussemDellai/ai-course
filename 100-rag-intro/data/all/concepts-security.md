---
title: Concepts - Security in Azure Kubernetes Services (AKS)
description: Learn about security in Azure Kubernetes Service (AKS), including master and node communication, network policies, and Kubernetes secrets.
author: miwithro
ms.topic: conceptual
ms.subservice: aks-security
ms.custom: build-2023
ms.date: 03/18/2024
ms.author: miwithro
---

# Security concepts for applications and clusters in Azure Kubernetes Service (AKS)

Container security protects the entire end-to-end pipeline from build to the application workloads running in Azure Kubernetes Service (AKS).

The Secure Supply Chain includes the build environment and registry.

Kubernetes includes security components, such as *pod security standards* and *Secrets*. Azure includes components like Active Directory, Microsoft Defender for Containers, Azure Policy, Azure Key Vault, network security groups, and orchestrated cluster upgrades. AKS combines these security components to:

* Provide a complete authentication and authorization story.
* Apply AKS Built-in Azure Policy to secure your applications.
* End-to-End insight from build through your application with Microsoft Defender for Containers.
* Keep your AKS cluster running the latest OS security updates and Kubernetes releases.
* Provide secure pod traffic and access to sensitive credentials.

This article introduces the core concepts that secure your applications in AKS.

## Build Security

As the entry point for the Supply Chain, it's important to conduct static analysis of image builds before they are promoted down the pipeline. This includes vulnerability and compliance assessment. It's not about failing a build because it has a vulnerability, as that breaks development. It's about looking at the **Vendor Status** to segment based on vulnerabilities that are actionable by the development teams. Also use **Grace Periods** to allow developers time to remediate identified issues.

## Registry Security

Assessing the vulnerability state of the image in the Registry detects drift and also catches images that didn't come from your build environment. Use [Notary V2](https://github.com/notaryproject/notaryproject) to attach signatures to your images to ensure deployments are coming from a trusted location.

## Cluster security

In AKS, the Kubernetes master components are part of the managed service provided, managed, and maintained by Microsoft. Each AKS cluster has its own single-tenanted, dedicated Kubernetes master to provide the API Server, Scheduler, etc. For more information, see [Vulnerability management for Azure Kubernetes Service][microsoft-vulnerability-management-aks].

By default, the Kubernetes API server uses a public IP address and a fully qualified domain name (FQDN). You can limit access to the API server endpoint using [authorized IP ranges][authorized-ip-ranges]. You can also create a fully [private cluster][private-clusters] to limit API server access to your virtual network.

You can control access to the API server using Kubernetes role-based access control (Kubernetes RBAC) and Azure RBAC. For more information, see [Microsoft Entra integration with AKS][aks-aad].

## Node security

AKS nodes are Azure virtual machines (VMs) that you manage and maintain.

* Linux nodes run optimized versions of Ubuntu or Azure Linux.
* Windows Server nodes run an optimized Windows Server 2019 release using the `containerd` or Docker container runtime.

When an AKS cluster is created or scaled up, the nodes are automatically deployed with the latest OS security updates and configurations.

> [!NOTE]
> AKS clusters running:
> * Kubernetes version 1.19 and higher - Linux node pools use `containerd` as its container runtime. Windows Server 2019 node pools use `containerd` as its container runtime, which is currently in preview. For more information, see [Add a Windows Server node pool with `containerd`][aks-add-np-containerd].
> * Kubernetes version 1.19 and earlier - Linux node pools use Docker as its container runtime. Windows Server 2019 node pools use Docker for the default container runtime.

For more information about the security upgrade process for Linux and Windows worker nodes, see [Security patching nodes][aks-vulnerability-management-nodes].

AKS clusters running Azure Generation 2 VMs includes support for [Trusted Launch][trusted-launch] (preview), which protects against advanced and persistent attack techniques by combining technologies that can be independently enabled, like secure boot and virtualized version of trusted platform module (vTPM). Administrators can deploy AKS worker nodes with verified and signed bootloaders, OS kernels, and drivers to ensure integrity of the entire boot chain of the underlying VM.

### Node authorization

Node authorization is a special-purpose authorization mode that specifically authorizes kubelet API requests to protect against East-West attacks.  Node authorization is enabled by default on AKS 1.24 + clusters.

### Node deployment

Nodes are deployed onto a private virtual network subnet, with no public IP addresses assigned. For troubleshooting and management purposes, SSH is enabled by default and only accessible using the internal IP address. Disabling SSH during cluster and node pool creation, or for an existing cluster or node pool, is in preview. See [Manage SSH access][manage-ssh-access] for more information. 

### Node storage

To provide storage, the nodes use Azure Managed Disks. For most VM node sizes, Azure Managed Disks are Premium disks backed by high-performance SSDs. The data stored on managed disks is automatically encrypted at rest within the Azure platform. To improve redundancy, Azure Managed Disks are securely replicated within the Azure datacenter.

### Hostile multitenant workloads

Currently, Kubernetes environments aren't safe for hostile multitenant usage. Extra security features, like *Pod Security Policies* or Kubernetes RBAC for nodes, efficiently block exploits. For true security when running hostile multitenant workloads, only trust a hypervisor. The security domain for Kubernetes becomes the entire cluster, not an individual node.

For these types of hostile multitenant workloads, you should use physically isolated clusters. For more information on ways to isolate workloads, see [Best practices for cluster isolation in AKS][cluster-isolation].

### Compute isolation

Because of compliance or regulatory requirements, certain workloads may require a high degree of isolation from other customer workloads. For these workloads, Azure provides:

* [Kernel isolated containers][azure-confidential-containers] to use as the agent nodes in an AKS cluster. These containers are completely isolated to a specific hardware type and isolated from the Azure Host fabric, the host operating system, and the hypervisor. They are dedicated to a single customer. Select [one of the isolated VMs sizes][isolated-vm-size] as the **node size** when creating an AKS cluster or adding a node pool.
* [Confidential Containers][confidential-containers] (preview), also based on Kata Confidential Containers, encrypts container memory and prevents data in memory during computation from being in clear text, readable format, and tampering. It helps isolate your containers from other container groups/pods, as well as VM node OS kernel. Confidential Containers (preview) uses hardware based memory encryption (SEV-SNP).
* [Pod Sandboxing][pod-sandboxing] (preview) provides an isolation boundary between the container application and the shared kernel and compute resources (CPU, memory, and network) of the container host.

## Network security

For connectivity and security with on-premises networks, you can deploy your AKS cluster into existing Azure virtual network subnets. These virtual networks connect back to your on-premises network using Azure Site-to-Site VPN or Express Route. Define Kubernetes ingress controllers with private, internal IP addresses to limit services access to the internal network connection.

### Azure network security groups

To filter virtual network traffic flow, Azure uses network security group rules. These rules define the source and destination IP ranges, ports, and protocols allowed or denied access to resources. Default rules are created to allow TLS traffic to the Kubernetes API server. You create services with load balancers, port mappings, or ingress routes. AKS automatically modifies the network security group for traffic flow.

If you provide your own subnet for your AKS cluster (whether using Azure CNI or Kubenet), **do not** modify the NIC-level network security group managed by AKS. Instead, create more subnet-level network security groups to modify the flow of traffic. Make sure they don't interfere with necessary traffic managing the cluster, such as load balancer access, communication with the control plane, or [egress][aks-limit-egress-traffic].

### Kubernetes network policy

To limit network traffic between pods in your cluster, AKS offers support for [Kubernetes network policies][network-policy]. With network policies, you can allow or deny specific network paths within the cluster based on namespaces and label selectors.

## Application Security

To protect pods running on AKS, consider [Microsoft Defender for Containers][microsoft-defender-for-containers] to detect and restrict cyber attacks against your applications running in your pods.  Run continual scanning to detect drift in the vulnerability state of your application and implement a "blue/green/canary" process to patch and replace the vulnerable images. 

## Kubernetes Secrets

With a Kubernetes *Secret*, you inject sensitive data into pods, such as access credentials or keys.

1. Create a Secret using the Kubernetes API.
1. Define your pod or deployment and request a specific Secret.
    * Secrets are only provided to nodes with a scheduled pod that requires them.
    * The Secret is stored in *tmpfs*, not written to disk.
1. When you delete the last pod on a node requiring a Secret, the Secret is deleted from the node's *tmpfs*.
   * Secrets are stored within a given namespace and are only accessible from pods within the same namespace.

Using Secrets reduces the sensitive information defined in the pod or service YAML manifest. Instead, you request the Secret stored in Kubernetes API Server as part of your YAML manifest. This approach only provides the specific pod access to the Secret.

> [!NOTE]
> The raw secret manifest files contain the secret data in base64 format. For more information, see the [official documentation][secret-risks]. Treat these files as sensitive information, and never commit them to source control.

Kubernetes secrets are stored in *etcd*, a distributed key-value store. AKS fully manages the *etcd* store and [data is encrypted at rest within the Azure platform][encryption-atrest].

## Next steps

To get started with securing your AKS clusters, see [Upgrade an AKS cluster][aks-upgrade-cluster].

For associated best practices, see [Best practices for cluster security and upgrades in AKS][operator-best-practices-cluster-security] and [Best practices for pod security in AKS][developer-best-practices-pod-security].

For more information on core Kubernetes and AKS concepts, see:

- [Kubernetes / AKS clusters and workloads][aks-concepts-clusters-workloads]
- [Kubernetes / AKS identity][aks-concepts-identity]
- [Kubernetes / AKS virtual networks][aks-concepts-network]
- [Kubernetes / AKS storage][aks-concepts-storage]
- [Kubernetes / AKS scale][aks-concepts-scale]

<!-- LINKS - External -->
[secret-risks]: https://kubernetes.io/docs/concepts/configuration/secret/#risks
[encryption-atrest]: ../security/fundamentals/encryption-atrest.md

<!-- LINKS - Internal -->
[microsoft-defender-for-containers]: ../defender-for-cloud/defender-for-containers-introduction.md
[azure-confidential-containers]: ../confidential-computing/confidential-containers.md
[confidential-containers]: confidential-containers-overview.md
[pod-sandboxing]: use-pod-sandboxing.md
[isolated-vm-size]: ../virtual-machines/isolation.md
[aks-upgrade-cluster]: upgrade-cluster.md
[aks-aad]: ./managed-azure-ad.md
[aks-add-np-containerd]: create-node-pools.md
[aks-concepts-clusters-workloads]: concepts-clusters-workloads.md
[aks-concepts-identity]: concepts-identity.md
[aks-concepts-scale]: concepts-scale.md
[aks-concepts-storage]: concepts-storage.md
[aks-concepts-network]: concepts-network.md
[aks-limit-egress-traffic]: limit-egress-traffic.md
[cluster-isolation]: operator-best-practices-cluster-isolation.md
[operator-best-practices-cluster-security]: operator-best-practices-cluster-security.md
[developer-best-practices-pod-security]:developer-best-practices-pod-security.md
[authorized-ip-ranges]: api-server-authorized-ip-ranges.md
[private-clusters]: private-clusters.md
[network-policy]: use-network-policies.md
[microsoft-vulnerability-management-aks]: concepts-vulnerability-management.md
[aks-vulnerability-management-nodes]: concepts-vulnerability-management.md#worker-nodes
[manage-ssh-access]: manage-ssh-node-access.md
[trusted-launch]: use-trusted-launch.md
