# Running ComfyUI on Container Apps with Serverless GPU (A100 & T4)

This repository contains the code and instructions to run ComfyUI on Azure Container Apps (ACA) with serverless GPU (A100 & T4). The infrastructure is provisioned using Terraform, and the ComfyUI application is deployed as a containerized workload on ACA.

## Prerequisites

- An Azure account with sufficient permissions to create resources.
- Terraform installed on your local machine.

## Infrastructure Provisioning

1. Clone the repository and navigate to the project directory.
2. Initialize Terraform and apply the configuration to provision the necessary Azure resources, including a resource group, virtual network, log analytics workspace, container app environment, storage account, and container app for downloading models.

```bash
terraform init
terraform apply
```

## ComfyUI Deployment

The ComfyUI application is deployed as a containerized workload on Azure Container Apps. The deployment includes a job that downloads the necessary models for ComfyUI to function properly.

1. The `aca_job_download_models.tf` file defines a job that runs a container with the necessary commands to download the models for ComfyUI. The job is configured to run on Consumption worksload profile and has a timeout of 1200 seconds.

2. The `download-models-comfyui.sh` script contains the commands to download the models from Hugging Face and save them to the appropriate directory in the ComfyUI application.

## Monitoring and Analytics

The Azure Log Analytics workspace is set up to collect logs and metrics from the container app environment. You can use Azure Monitor to view and analyze the logs and metrics for your ComfyUI deployment.

## Important Notes

The storage account key is required to create the storage link in your Container Apps environment. Container Apps does not support identity-based access to Azure file shares. Src: https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts-azure-files?tabs=bash#set-up-a-storage-account

Because of an issue with the Terraform provider, it won't create the Serverless GPU (A100 & T4) workload profiles. You will need to create them manually in the Azure Portal after running `terraform apply`.

To mount NFS Azure Files, you must use a Container Apps environment with a custom VNet. The Storage account must be configured to allow access from the VNet. Src: https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts?tabs=nfs&pivots=azure-resource-manager#configuration-1

🔍 SMB vs NFS — What’s the Difference?
SMB (Server Message Block) and NFS (Network File System) are two protocols used to provide shared file storage over a network.
They serve similar purposes but have different strengths, performance characteristics, and typical use cases.

| Feature | **SMB (CIFS)** | **NFS** |
|--------|-----------------|---------|
| **Origin** | Windows ecosystem | Unix/Linux ecosystem |
| **Typical OS support** | Windows (native), Linux (supported) | Linux/Unix (native), Windows (supported with extras) |
| **Protocol versions** | SMB 1.0 → 2.x → 3.x | NFS v3, v4.0, v4.1 |
| **Performance** | Slightly heavier, more overhead | Very fast, lightweight for Linux workloads |
| **Security** | Stronger (Kerberos, SMB3 encryption) | NFSv4 offers Kerberos & ACLs |
| **Authentication** | Active Directory, NTLM, Kerberos | AUTH_SYS, Kerberos |
| **File locking** | Mandatory locking | Advisory locking |
| **Best use cases** | Windows applications, Office files, user profiles | Linux workloads, Kubernetes pods, HPC, data processing |
| **Azure equivalent** | Azure Files (SMB) | Azure Files (NFS), Azure NetApp Files (NFS) |